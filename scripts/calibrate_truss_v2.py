#!/usr/bin/env python3
"""Calibrate Truss-v2 with independent FEM residuals and feasible witnesses."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, minimize

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/StructuralEngineering/TrussWeightMinimization"
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("truss_v2_calibration_oracle", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load Truss-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _policy_for(oracle, key):
    """Return stored witnesses using only complete public instance data."""
    def design_truss(nodes, members, _fixed_dofs, _load_cases, youngs_modulus,
                     _density, _tension_allowable, _compression_allowable,
                     _displacement_limit, _area_min, _area_max,
                     _inertia_coefficient):
        for instance in oracle.INSTANCES:
            if (
                instance["nodes"].shape == np.asarray(nodes).shape
                and instance["members"].shape == np.asarray(members).shape
                and np.array_equal(instance["members"], members)
                and np.allclose(instance["nodes"], nodes, atol=0.0, rtol=0.0)
                and float(instance["youngs_modulus"]) == float(youngs_modulus)
            ):
                return instance[key].copy()
        raise ValueError("unknown public truss instance")
    return design_truss


def _all_max(_nodes, members, _fixed_dofs, _load_cases, _youngs_modulus,
             _density, _tension_allowable, _compression_allowable,
             _displacement_limit, _area_min, area_max, _inertia_coefficient):
    return np.full(len(members), area_max, dtype=float)


def _independent_case(instance, design_areas, loads, shift=None):
    """Second direct-stiffness implementation used only for calibration checks."""
    shift = shift or {
        "load_scale": 1.0, "youngs_modulus_scale": 1.0,
        "allowable_scale": 1.0, "area_scale": 1.0,
    }
    nodes = np.asarray(instance["nodes"], dtype=float)
    members = np.asarray(instance["members"], dtype=int)
    areas = np.asarray(design_areas, dtype=float) * float(shift["area_scale"])
    modulus = float(instance["youngs_modulus"]) * float(
        shift["youngs_modulus_scale"]
    )
    delta = nodes[members[:, 1]] - nodes[members[:, 0]]
    lengths = np.sqrt(np.sum(delta * delta, axis=1))
    directions = delta / lengths[:, None]
    stiffness = np.zeros((2 * len(nodes), 2 * len(nodes)), dtype=float)
    for index, (left, right) in enumerate(members):
        cx, cy = directions[index]
        vector = np.asarray((cx, cy, -cx, -cy), dtype=float)
        dofs = np.asarray((2 * left, 2 * left + 1, 2 * right, 2 * right + 1))
        stiffness[np.ix_(dofs, dofs)] += (
            modulus * areas[index] / lengths[index] * np.outer(vector, vector)
        )
    fixed = np.asarray(instance["fixed_dofs"], dtype=int)
    free = np.setdiff1d(np.arange(2 * len(nodes)), fixed)
    force = np.asarray(loads, dtype=float).reshape(-1) * float(shift["load_scale"])
    displacement = np.zeros(2 * len(nodes), dtype=float)
    displacement[free] = np.linalg.solve(
        stiffness[np.ix_(free, free)], force[free]
    )
    stresses = np.empty(len(members), dtype=float)
    for index, (left, right) in enumerate(members):
        relative = displacement[2 * right:2 * right + 2] - displacement[
            2 * left:2 * left + 2
        ]
        stresses[index] = (
            modulus * float(np.dot(directions[index], relative)) / lengths[index]
        )
    tension = float(instance["tension_allowable"]) * float(shift["allowable_scale"])
    compression = float(instance["compression_allowable"]) * float(
        shift["allowable_scale"]
    )
    stress_ratio = np.where(stresses >= 0.0, stresses / tension, -stresses / compression)
    displacement_ratio = np.abs(displacement[free]) / float(
        instance["displacement_limit"]
    )
    axial_force = stresses * areas
    buckling_capacity = (
        math.pi**2 * modulus * float(instance["inertia_coefficient"])
        * areas**2 / lengths**2
    )
    buckling_ratio = np.maximum(-axial_force, 0.0) / buckling_capacity
    return float(max(
        np.max(stress_ratio), np.max(displacement_ratio), np.max(buckling_ratio)
    ))


def _independent_constraint_residuals(instance, design_areas, robust):
    """Return every physical constraint residual from the independent FEM.

    Keeping individual stress, displacement and buckling constraints avoids the nonsmooth
    maximum-utilization envelope used only for reporting and makes multistart reproduction
    fast enough to run as part of the calibration command.
    """
    nominal = {
        "load_scale": 1.0, "youngs_modulus_scale": 1.0,
        "allowable_scale": 1.0, "area_scale": 1.0,
    }
    shifts = instance["shift_specs"] if robust else (nominal,)
    nodes = np.asarray(instance["nodes"], dtype=float)
    members = np.asarray(instance["members"], dtype=int)
    intended_areas = np.asarray(design_areas, dtype=float)
    delta = nodes[members[:, 1]] - nodes[members[:, 0]]
    lengths = np.sqrt(np.sum(delta * delta, axis=1))
    directions = delta / lengths[:, None]
    fixed = np.asarray(instance["fixed_dofs"], dtype=int)
    free = np.setdiff1d(np.arange(2 * len(nodes)), fixed)
    residuals = []
    for shift in shifts:
        areas = intended_areas * float(shift["area_scale"])
        modulus = float(instance["youngs_modulus"]) * float(
            shift["youngs_modulus_scale"]
        )
        tension = float(instance["tension_allowable"]) * float(
            shift["allowable_scale"]
        )
        compression = float(instance["compression_allowable"]) * float(
            shift["allowable_scale"]
        )
        stiffness = np.zeros((2 * len(nodes), 2 * len(nodes)), dtype=float)
        for index, (left, right) in enumerate(members):
            cx, cy = directions[index]
            vector = np.asarray((cx, cy, -cx, -cy), dtype=float)
            dofs = np.asarray((2 * left, 2 * left + 1, 2 * right, 2 * right + 1))
            stiffness[np.ix_(dofs, dofs)] += (
                modulus * areas[index] / lengths[index] * np.outer(vector, vector)
            )
        reduced = stiffness[np.ix_(free, free)]
        for loads in instance["load_cases"]:
            force = np.asarray(loads, dtype=float).reshape(-1) * float(
                shift["load_scale"]
            )
            displacement = np.zeros(2 * len(nodes), dtype=float)
            displacement[free] = np.linalg.solve(reduced, force[free])
            stresses = np.empty(len(members), dtype=float)
            for index, (left, right) in enumerate(members):
                relative = (
                    displacement[2 * right:2 * right + 2]
                    - displacement[2 * left:2 * left + 2]
                )
                stresses[index] = (
                    modulus * float(np.dot(directions[index], relative))
                    / lengths[index]
                )
            axial_force = stresses * areas
            buckling_capacity = (
                math.pi**2 * modulus * float(instance["inertia_coefficient"])
                * areas**2 / lengths**2
            )
            residuals.extend((1.0 - stresses / tension).tolist())
            residuals.extend((1.0 + stresses / compression).tolist())
            residuals.extend((
                1.0 - displacement[free] / float(instance["displacement_limit"])
            ).tolist())
            residuals.extend((
                1.0 + displacement[free] / float(instance["displacement_limit"])
            ).tolist())
            residuals.extend((1.0 + axial_force / buckling_capacity).tolist())
    return np.asarray(residuals, dtype=float)


def _reproduce_multistart(oracle, instance, robust):
    """Actually rerun the documented local solve from five deterministic starts."""
    # Attach shifts only to the private calibration view, keeping oracle instances unchanged.
    calibration_instance = dict(instance)
    calibration_instance["shift_specs"] = oracle.SHIFT_SPECS
    member_count = len(instance["members"])
    lower = float(instance["area_min"])
    upper = float(instance["area_max"])
    baseline_weight = float(instance["baseline_weight"])
    stored = instance[
        "robust_reference_areas" if robust else "nominal_reference_areas"
    ]
    rng = np.random.default_rng(
        8200 + member_count + (100 if robust else 0)
    )
    starts = [
        np.full(member_count, upper),
        np.minimum(upper, np.asarray(stored) * 1.02),
        np.full(member_count, 0.80 * upper + 0.20 * lower),
        rng.uniform(0.55 * upper, 0.95 * upper, member_count),
        rng.uniform(0.55 * upper, 0.95 * upper, member_count),
    ]
    records = []
    for index, start in enumerate(starts):
        result = minimize(
            lambda areas: float(
                instance["density"] * np.dot(instance["lengths"], areas)
                / baseline_weight
            ),
            start,
            method="SLSQP",
            bounds=Bounds(
                np.full(member_count, lower), np.full(member_count, upper)
            ),
            constraints={
                "type": "ineq",
                "fun": lambda areas: (
                    _independent_constraint_residuals(
                        calibration_instance, areas, robust
                    ) - 5.0e-4
                ),
            },
            options={"ftol": 1.0e-11, "maxiter": 1500, "disp": False},
        )
        areas = np.asarray(result.x, dtype=float)
        residual = float(np.min(_independent_constraint_residuals(
            calibration_instance, areas, robust
        )))
        weight = float(instance["density"] * np.dot(instance["lengths"], areas))
        records.append({
            "start_index": index,
            "optimizer_success": bool(result.success),
            "optimizer_status": int(result.status),
            "optimizer_message": str(result.message),
            "iterations": int(result.nit),
            "weight_lbs": weight,
            "minimum_independent_residual": residual,
            "feasible": bool(
                residual >= 5.0e-4 - 1.0e-7
                and np.all(areas >= lower - 1.0e-9)
                and np.all(areas <= upper + 1.0e-9)
            ),
        })
    feasible = [row for row in records if row["feasible"]]
    stored_weight = float(instance[
        "robust_reference_weight" if robust else "nominal_reference_weight"
    ])
    best_weight = min(row["weight_lbs"] for row in feasible) if feasible else math.inf
    return {
        "condition": "robust" if robust else "nominal",
        "start_count": len(starts),
        "feasible_start_count": len(feasible),
        "stored_reference_weight_lbs": stored_weight,
        "rerun_best_weight_lbs": best_weight,
        "relative_weight_difference": abs(best_weight - stored_weight) / stored_weight,
        "runs": records,
        "passed": bool(
            len(feasible) == len(starts)
            and abs(best_weight - stored_weight) / stored_weight <= 5.0e-4
        ),
    }


def _reference_checks(oracle):
    checks = []
    for instance in oracle.INSTANCES:
        baseline_nominal = [
            _independent_case(instance, instance["baseline_areas"], loads)
            for loads in instance["load_cases"]
        ]
        baseline_shifted = [
            _independent_case(
                instance, instance["baseline_areas"], loads, shift
            )
            for shift in oracle.SHIFT_SPECS for loads in instance["load_cases"]
        ]
        nominal = [
            _independent_case(instance, instance["nominal_reference_areas"], loads)
            for loads in instance["load_cases"]
        ]
        nominal_shifted = [
            _independent_case(
                instance, instance["nominal_reference_areas"], loads, shift
            )
            for shift in oracle.SHIFT_SPECS for loads in instance["load_cases"]
        ]
        robust = [
            _independent_case(
                instance, instance["robust_reference_areas"], loads, shift
            )
            for shift in oracle.SHIFT_SPECS for loads in instance["load_cases"]
        ]
        baseline_oracle_cases = [
            oracle._case_analysis(
                instance, instance["baseline_areas"], loads
            ) for loads in instance["load_cases"]
        ]
        # Translation invariance of member extensions is checked without re-solving equilibrium.
        translation_error = 0.0
        for member in instance["members"]:
            left, right = map(int, member)
            displacement = np.arange(2 * len(instance["nodes"]), dtype=float) / 1000.0
            direction = (
                instance["nodes"][right] - instance["nodes"][left]
            ) / instance["lengths"][list(map(tuple, instance["members"])).index(tuple(member))]
            extension = float(np.dot(
                direction,
                displacement[2 * right:2 * right + 2]
                - displacement[2 * left:2 * left + 2],
            ))
            translated = displacement.reshape(-1, 2) + np.asarray((4.0, -7.0))
            translated_extension = float(np.dot(
                direction, translated[right] - translated[left]
            ))
            translation_error = max(
                translation_error, abs(extension - translated_extension)
            )
        checks.append({
            "name": instance["name"],
            "member_count": len(instance["members"]),
            "unique_member_count": len({
                tuple(sorted(map(int, row))) for row in instance["members"]
            }),
            "baseline_weight_lbs": instance["baseline_weight"],
            "nominal_reference_weight_lbs": instance["nominal_reference_weight"],
            "robust_reference_weight_lbs": instance["robust_reference_weight"],
            "baseline_max_nominal_utilization": max(baseline_nominal),
            "baseline_max_shifted_utilization": max(baseline_shifted),
            "nominal_reference_max_utilization": max(nominal),
            "nominal_reference_max_shifted_utilization": max(nominal_shifted),
            "robust_reference_max_shifted_utilization": max(robust),
            "rigid_translation_extension_error": translation_error,
            "maximum_stiffness_symmetry_error": max(
                row["stiffness_symmetry_error"] for row in baseline_oracle_cases
            ),
            "maximum_force_equilibrium_error_lbs": max(
                row["force_equilibrium_error_lbs"] for row in baseline_oracle_cases
            ),
            "passed": bool(
                len(instance["members"]) == len({
                    tuple(sorted(map(int, row))) for row in instance["members"]
                })
                and max(baseline_nominal + baseline_shifted) <= 1.0 + 1e-10
                and max(nominal) <= 1.0 + 1e-10
                and max(nominal_shifted) > 1.05
                and max(robust) <= 1.0 + 1e-10
                and instance["nominal_reference_weight"]
                < instance["robust_reference_weight"]
                < instance["baseline_weight"]
                and translation_error <= 1e-12
                and max(row["stiffness_symmetry_error"]
                        for row in baseline_oracle_cases) <= 1e-10
                and max(row["force_equilibrium_error_lbs"]
                        for row in baseline_oracle_cases) <= 1e-6
            ),
        })
    return checks


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(_all_max)
    nominal = oracle.evaluate(_policy_for(oracle, "nominal_reference_areas"))
    robust = oracle.evaluate(_policy_for(oracle, "robust_reference_areas"))
    nonfinite = oracle.evaluate(
        lambda _nodes, members, *_args: np.full(len(members), np.nan)
    )
    out_of_bounds = oracle.evaluate(
        lambda _nodes, members, *_args: np.full(len(members), -1.0)
    )
    wrong_length = oracle.evaluate(lambda *_args: np.ones(1))
    checks = _reference_checks(oracle)
    multistart = [
        _reproduce_multistart(oracle, instance, robust)
        for instance in oracle.INSTANCES for robust in (False, True)
    ]
    for invalid in (nonfinite, out_of_bounds, wrong_length):
        json.dumps(invalid, allow_nan=False)
    execution_passed = bool(
        baseline["valid"] == 1.0 and baseline["combined_score"] == 0.0
        and baseline["mean_shifted_case_feasibility_rate"] == 1.0
        and nominal["valid"] == 1.0 and nominal["combined_score"] > 0.999999
        and nominal["robustness_score"] == 0.0
        and robust["valid"] == 1.0 and robust["robustness_score"] > 0.999999
        and 0.30 < robust["combined_score"] < 0.95
        and all(row["valid"] == 0.0 and row["combined_score"] == 0.0
                for row in (nonfinite, out_of_bounds, wrong_length))
        and all(row["passed"] for row in checks)
        and all(row["passed"] for row in multistart)
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": "SCIENTIFIC_CALIBRATION_NOT_MODEL_PERFORMANCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "reference_method": {
            "description": (
                "Five-start SLSQP sizing with explicit independent stress, displacement and "
                "Euler-buckling residuals; committed witnesses impose a 5e-4 utilization "
                "margin and are re-evaluated by a separately implemented FEM here."
            ),
            "global_optimality_claimed": False,
            "normalization_clips_better_feasible_candidates": True,
        },
        "baseline": baseline,
        "nominal_reference_policy": nominal,
        "robust_reference_policy": robust,
        "nonfinite_rejection": nonfinite,
        "out_of_bounds_rejection": out_of_bounds,
        "wrong_length_rejection": wrong_length,
        "independent_reference_checks": checks,
        "multistart_reproduction": multistart,
    }
    finalize_report_trust(report, execution_passed)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = calibrate()
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
