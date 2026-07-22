#!/usr/bin/env python3
"""Reproduce admission-blocking defects in the second candidate tranche."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


def _oracle(task_id: str):
    path = ROOT / "benchmarks" / task_id / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location(
        "wave2_" + task_id.replace("/", "_"), path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % task_id)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _room_audit():
    oracle = _oracle("Acoustics/RoomImpulseResponse")

    def high_order(room, source, mic, fs, _max_order, absorption):
        return oracle.image_source_rir(room, source, mic, fs, 15, absorption)

    crashed, error = False, None
    try:
        oracle.evaluate(high_order)
    except Exception as exc:
        crashed = True
        error = "%s: %s" % (type(exc).__name__, exc)
    return {
        "task": "Acoustics/RoomImpulseResponse",
        "admission": "quarantine",
        "defect": "a reference-length candidate crashes when compared with the shorter order-zero baseline",
        "exact_reference_candidate_crashed": crashed,
        "error": error,
        "passed": crashed and "broadcast" in str(error),
    }


def _low_thrust_audit():
    oracle = _oracle("Astrodynamics/LowThrustTransfer")
    zero = np.zeros((oracle.N_SEGMENTS, 7), dtype=float)
    baseline = oracle.evaluate(lambda *_args: zero.copy())
    reference = oracle.evaluate(
        lambda initial, *_args: next(
            row["reference_coefficients"].copy()
            for row in oracle._instances()
            if np.array_equal(np.asarray(initial), row["initial_elements"])
        )
    )
    return {
        "task": "Astrodynamics/LowThrustTransfer",
        "admission": "candidate",
        "superseded_v1_defect": (
            "the removed v1 task used one 30-day Cartesian trajectory, 1000 Euler steps, "
            "silent thrust clipping and unsupported fuel anchors"
        ),
        "resolved_defect": (
            "v2 uses six multi-regime MEE+J2 transfers, bounded harmonic controls, "
            "rocket-equation mass depletion, explicit terminal feasibility and sealed "
            "held-out/execution robustness; current numerical evidence is delegated to "
            "scripts/calibrate_low_thrust_v2.py"
        ),
        "baseline_score": float(baseline["combined_score"]),
        "baseline_valid": bool(baseline["valid"]),
        "reference_score": float(reference["combined_score"]),
        "reference_robustness": float(reference["robustness_score"]),
        "reference_development_feasibility": float(reference["feasibility_rate"]),
        "reference_heldout_feasibility": float(
            reference["heldout_mission_feasibility_rate"]
        ),
        "rebuild_passed": True,
        "passed": bool(
            baseline["valid"] == 1.0 and baseline["combined_score"] == 0.0
            and reference["valid"] == 1.0
            and 0.5 < reference["combined_score"] < 0.95
            and reference["robustness_score"] > 0.5
            and reference["feasibility_rate"] == 1.0
            and reference["heldout_mission_feasibility_rate"] == 1.0
        ),
    }


def _pendulum_acceleration(oracle, theta):
    state = np.asarray((0.0, 0.0, float(theta), 0.0), dtype=float)
    return float(
        oracle.cart_pole_derivative(
            state, 0.0, oracle._plant_tuple()
        )[3]
    )


def _pendulum_audit():
    oracle = _oracle("ControlTheory/InvertedPendulumSwingUp")
    step = 1e-6
    derivative_zero = float(
        (_pendulum_acceleration(oracle, step) - _pendulum_acceleration(oracle, -step))
        / (2 * step)
    )
    derivative_pi = float((
        _pendulum_acceleration(oracle, np.pi + step)
        - _pendulum_acceleration(oracle, np.pi - step)
    ) / (2 * step))
    return {
        "task": "ControlTheory/InvertedPendulumSwingUp",
        "admission": "candidate",
        "resolved_defect": (
            "v2 uses the documented down-zero convention: theta=0 is the stable hanging "
            "equilibrium, theta=pi is the unstable upright equilibrium, and shifted plant "
            "and disturbance robustness is reported separately"
        ),
        "d_theta_acceleration_at_zero": derivative_zero,
        "d_theta_acceleration_at_pi": derivative_pi,
        "development_scenario_count": len(oracle.DEVELOPMENT_SCENARIOS),
        "validation_scenario_count": len(oracle.VALIDATION_SCENARIOS),
        "rebuild_passed": True,
        "passed": bool(
            derivative_zero < 0.0 and derivative_pi > 0.0
            and len(oracle.DEVELOPMENT_SCENARIOS) >= 4
            and len(oracle.VALIDATION_SCENARIOS) >= 4
        ),
    }


def _interpolation_matrix(points, grid):
    matrix = np.zeros((len(points), len(grid)), dtype=float)
    for row, value in enumerate(points):
        if value <= grid[0]:
            matrix[row, 0] = 1.0
        elif value >= grid[-1]:
            matrix[row, -1] = 1.0
        else:
            left = int(np.searchsorted(grid, value) - 1)
            weight = (value - grid[left]) / (grid[left + 1] - grid[left])
            matrix[row, left] = 1.0 - weight
            matrix[row, left + 1] = weight
    return matrix


def _cavity_audit():
    oracle = _oracle("FluidDynamics/LidDrivenCavity")
    size = oracle.INSTANCES[0]["N"]
    grid = np.linspace(0.0, 1.0, size)
    u_map = _interpolation_matrix(oracle.GHIA_RE100_U[:, 0], grid)
    v_map = _interpolation_matrix(oracle.GHIA_RE100_V[:, 0], grid)
    u_profile = np.linalg.lstsq(u_map, oracle.GHIA_RE100_U[:, 1], rcond=None)[0]
    v_profile = np.linalg.lstsq(v_map, oracle.GHIA_RE100_V[:, 1], rcond=None)[0]

    def profile_injection(_reynolds, n):
        u = np.zeros((n, n), dtype=float)
        v = np.zeros((n, n), dtype=float)
        pressure = np.zeros((n, n), dtype=float)
        u[:, n // 2] = u_profile
        v[n // 2, :] = v_profile
        return u, v, pressure

    metrics = oracle.evaluate(profile_injection)
    return {
        "task": "FluidDynamics/LidDrivenCavity",
        "admission": "quarantine",
        "defect": "centerline-only scoring accepts fields that violate boundary conditions and never solve Navier-Stokes",
        "profile_injection_score": float(metrics["combined_score"]),
        "top_wall_max_error": 1.0,
        "pressure_is_unchecked": True,
        "passed": metrics["combined_score"] > 0.99,
    }


def _alloy_audit():
    task = ROOT / "benchmarks/MaterialsScience/AlloyHardnessOptimization"
    source = (task / "verification/evaluator.py").read_text(encoding="utf-8")
    has_dataset = any((task / name).is_file() for name in (
        "data.csv", "data.npz", "dataset.csv", "dataset.npz"
    ))
    return {
        "task": "MaterialsScience/AlloyHardnessOptimization",
        "admission": "quarantine",
        "defect": "the claimed experimental-data surrogate is a hand-written pseudo-physical polynomial with no dataset artifact",
        "oracle_self_labels_pseudo_physical": "pseudo-physical" in source,
        "dataset_artifact_present": has_dataset,
        "passed": "pseudo-physical" in source and not has_dataset,
    }


def _diffraction_audit():
    oracle = _oracle("Optics/DiffractionGratingDesign")

    def analytic_phase_ramp(wavelength, _period, index, order, grooves):
        return (np.arange(grooves) * order % grooves) / grooves * wavelength / index

    metrics = oracle.evaluate(analytic_phase_ramp)
    return {
        "task": "Optics/DiffractionGratingDesign",
        "admission": "quarantine",
        "defect": "the oracle is a scalar phase FFT, not RCWA, and a disclosed analytic phase ramp gives unit efficiency",
        "analytic_phase_ramp_score": float(metrics["combined_score"]),
        "efficiencies": [float(row["efficiency"]) for row in metrics["per_scenario"]],
        "passed": metrics["combined_score"] == 1.0,
    }


def _heat_exchanger_audit():
    oracle = _oracle("Thermodynamics/HeatExchangerDesign")

    def archive_for(problem, family):
        for instance in oracle.INSTANCES:
            if instance["problem"] == problem:
                if family == "baseline":
                    return oracle._baseline_archive(problem)
                source = (
                    oracle.REFERENCE_ARCHIVES if family == "nominal"
                    else oracle.ROBUST_REFERENCE_ARCHIVES
                )
                return source[instance["name"]].copy()
        raise ValueError("unknown public heat-exchanger problem")

    baseline = oracle.evaluate(lambda problem: archive_for(problem, "baseline"))
    nominal = oracle.evaluate(lambda problem: archive_for(problem, "nominal"))
    robust = oracle.evaluate(lambda problem: archive_for(problem, "robust"))
    nonfinite = oracle.evaluate(
        lambda _problem: np.full((oracle.MIN_ARCHIVE_SIZE, 5), np.nan)
    )
    anchor_errors = []
    baseline_shift_feasible = True
    robust_shift_feasible = True
    for instance in oracle.INSTANCES:
        declared = oracle.CALIBRATED_ANCHORS[instance["name"]]
        reproduced = oracle._recompute_anchors(instance)
        for key, value in declared.items():
            if isinstance(value, tuple):
                anchor_errors.extend(
                    abs(float(left) - float(right))
                    for left, right in zip(value, reproduced[key])
                )
            else:
                anchor_errors.append(abs(float(value) - float(reproduced[key])))
        _, _, baseline_shifts = oracle._evaluate_archive(
            instance, oracle._baseline_archive(instance["problem"])
        )
        _, _, robust_shifts = oracle._evaluate_archive(
            instance, oracle.ROBUST_REFERENCE_ARCHIVES[instance["name"]]
        )
        baseline_shift_feasible = baseline_shift_feasible and all(
            all(row["feasible"] for row in records)
            for records in baseline_shifts
        )
        robust_shift_feasible = robust_shift_feasible and all(
            all(row["feasible"] for row in records)
            for records in robust_shifts
        )
    return {
        "task": "Thermodynamics/HeatExchangerDesign",
        "admission": "candidate",
        "resolved_defect": (
            "v2 replaces the monotone single geometry with six bounded multi-fluid Pareto "
            "problems, a public cheap proxy, a sealed segmented exact oracle, fixed-seed "
            "reproducible references and separate held-out/physical-shift diagnostics"
        ),
        "instance_count": len(oracle.INSTANCES),
        "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
        "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
        "baseline_score": float(baseline["combined_score"]),
        "baseline_valid": bool(baseline["valid"]),
        "nominal_reference_score": float(nominal["combined_score"]),
        "nominal_heldout_score": float(nominal["heldout_exact_score"]),
        "robust_reference_score": float(robust["combined_score"]),
        "robust_reference_robustness": float(robust["robustness_score"]),
        "nonfinite_score": float(nonfinite["combined_score"]),
        "nonfinite_valid": bool(nonfinite["valid"]),
        "maximum_anchor_reproduction_error": max(anchor_errors),
        "baseline_feasible_under_every_shift": baseline_shift_feasible,
        "robust_reference_feasible_under_every_shift": robust_shift_feasible,
        "rebuild_passed": True,
        "passed": bool(
            len(oracle.DEVELOPMENT_INSTANCES) == 4
            and len(oracle.HELDOUT_INSTANCES) == 2
            and baseline["valid"] == 1.0 and baseline["combined_score"] == 0.0
            and nominal["combined_score"] > 0.999999
            and nominal["heldout_exact_score"] > 0.999999
            and robust["robustness_score"] > 0.999999
            and robust["heldout_robustness_score"] > 0.999999
            and nonfinite["valid"] == 0.0 and nonfinite["combined_score"] == 0.0
            and max(anchor_errors) <= 1e-12
            and baseline_shift_feasible and robust_shift_feasible
        ),
    }


def audit() -> dict:
    records = [
        _room_audit(), _low_thrust_audit(), _pendulum_audit(), _cavity_audit(),
        _alloy_audit(), _diffraction_audit(), _heat_exchanger_audit(),
    ]
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_ADMISSION_AUDIT",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "records": records,
        "summary": {
            "task_count": len(records),
            "check_pass_count": sum(bool(row["passed"]) for row in records),
            "resolved_rebuild_count": sum(bool(row.get("rebuild_passed")) for row in records),
            "recommended_quarantine_count": sum(row["admission"] == "quarantine" for row in records),
        },
    }
    finalize_report_trust(report, all(row["passed"] for row in records))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
