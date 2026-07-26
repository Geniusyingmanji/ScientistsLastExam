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
    baseline = oracle.evaluate(
        lambda problem: oracle._weak_baseline_design(problem)
    )
    nominal = oracle.evaluate(
        lambda problem: oracle.reference_policy(problem, robust=False)
    )
    robust = oracle.evaluate(
        lambda problem: oracle.reference_policy(problem, robust=True)
    )
    nonfinite = oracle.evaluate(lambda _problem: np.full(9, np.nan))
    reference_headroom = all(
        instance["nominal_reference"]["utility"]
        > instance["baseline_nominal"]["utility"] + 1.0e-4
        and instance["robust_reference_utility"]
        > instance["baseline_robust_utility"] + 1.0e-4
        for instance in oracle.INSTANCES
    )
    return {
        "task": "Acoustics/RoomImpulseResponse",
        "admission": "candidate",
        "superseded_v1_defect": (
            "the removed fixed-RIR reconstruction task crashed reference-length candidates "
            "against a shorter order-zero baseline and exposed only two fixed scenes"
        ),
        "resolved_defect": (
            "v2 optimizes a physical loudspeaker position and six treatment areas over four "
            "development and two held-out rooms; order-10 image energy, Eyring decay, C50, "
            "spatial uniformity, a first-order proxy and five sealed shifts remain separate"
        ),
        "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
        "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
        "shift_count": len(oracle.SHIFT_SPECS),
        "baseline_score": float(baseline["combined_score"]),
        "baseline_valid": bool(baseline["valid"]),
        "nominal_reference_score": float(nominal["combined_score"]),
        "nominal_heldout_score": float(nominal["heldout_policy_score"]),
        "robust_reference_score": float(robust["combined_score"]),
        "robust_reference_robustness": float(robust["robustness_score"]),
        "robust_heldout_robustness": float(robust["heldout_robustness_score"]),
        "nonfinite_score": float(nonfinite["combined_score"]),
        "nonfinite_valid": bool(nonfinite["valid"]),
        "all_reference_axes_have_headroom": reference_headroom,
        "rebuild_passed": True,
        "passed": bool(
            oracle.ROOM_ACOUSTICS_V2
            and len(oracle.DEVELOPMENT_INSTANCES) == 4
            and len(oracle.HELDOUT_INSTANCES) == 2
            and len(oracle.SHIFT_SPECS) == 5
            and baseline["valid"] == 1.0
            and baseline["combined_score"] == 0.0
            and nominal["combined_score"] > 0.999999
            and nominal["heldout_policy_score"] > 0.999999
            and robust["robustness_score"] > 0.999999
            and robust["heldout_robustness_score"] > 0.999999
            and nonfinite["combined_score"] == 0.0
            and not bool(nonfinite["valid"])
            and reference_headroom
        ),
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


def _cavity_audit():
    oracle = _oracle("FluidDynamics/LidDrivenCavity")
    baseline = oracle.evaluate(
        lambda _reynolds, n: oracle._weak_baseline_fields(int(n))
    )
    reference = oracle.evaluate(
        lambda reynolds, n: tuple(
            field.copy()
            for field in oracle._reference_solution(float(reynolds), int(n))
        )
    )

    def nonphysical_injection(_reynolds, n):
        streamfunction, vorticity = oracle._weak_baseline_fields(int(n))
        streamfunction[:, int(n) // 2] = np.linspace(0.0, -0.05, int(n))
        return streamfunction, vorticity

    injection = oracle.evaluate(nonphysical_injection)

    def attenuated_reference(reynolds, n):
        streamfunction, vorticity = oracle._reference_solution(
            float(reynolds), int(n)
        )
        _, baseline_vorticity = oracle._weak_baseline_fields(int(n))
        attenuation = 0.95
        return (
            attenuation * streamfunction,
            attenuation * vorticity
            + (1.0 - attenuation) * baseline_vorticity,
        )

    attenuation_shortcut = oracle.evaluate(attenuated_reference)
    reference_grid_differences = [
        float(row["reference_grid_difference"])
        for row in reference["grid_refinement"]
    ]
    return {
        "task": "FluidDynamics/LidDrivenCavity",
        "admission": "candidate",
        "superseded_v1_defect": (
            "the removed v1 task used one Re/grid and scored only two sparse centerlines, "
            "so injected nonphysical velocity stripes could score above 0.99 while boundary, "
            "continuity, momentum and pressure were unchecked"
        ),
        "resolved_defect": (
            "v2 returns streamfunction/vorticity, spans six Reynolds/grid cases plus two "
            "independent refinement calls, derives velocity in trusted code, and separately "
            "checks full-field agreement, Poisson/transport/wall residuals, held-out transfer, "
            "grid convergence and corrected Ghia Re=100 profiles"
        ),
        "baseline_score": float(baseline["combined_score"]),
        "baseline_valid": bool(baseline["valid"]),
        "baseline_physics_feasibility": float(baseline["feasibility_rate"]),
        "reference_score": float(reference["combined_score"]),
        "reference_heldout_score": float(reference["heldout_policy_score"]),
        "reference_grid_score": float(reference["robustness_score"]),
        "reference_heldout_grid_score": float(reference["heldout_robustness_score"]),
        "reference_development_physics_feasibility": float(
            reference["development_physics_feasibility_rate"]
        ),
        "reference_heldout_physics_feasibility": float(
            reference["heldout_physics_feasibility_rate"]
        ),
        "maximum_reference_grid_difference": max(reference_grid_differences),
        "reference_ghia_re100": reference["ghia_re100"],
        "nonphysical_injection_score": float(injection["combined_score"]),
        "nonphysical_injection_physics_feasibility": float(
            injection["feasibility_rate"]
        ),
        "attenuated_reference_ungated_score": float(
            attenuation_shortcut["ungated_development_score"]
        ),
        "attenuated_reference_gated_score": float(
            attenuation_shortcut["combined_score"]
        ),
        "attenuated_reference_physics_feasibility": float(
            attenuation_shortcut["feasibility_rate"]
        ),
        "instance_count": len(oracle.INSTANCES),
        "refinement_pair_count": len(oracle.GRID_REFINEMENT_SPECS),
        "rebuild_passed": True,
        "passed": bool(
            oracle.CAVITY_V2
            and len(oracle.INSTANCES) == 6
            and len(oracle.GRID_REFINEMENT_SPECS) == 2
            and baseline["valid"] == 1.0
            and baseline["combined_score"] == 0.0
            and baseline["feasibility_rate"] == 0.0
            and reference["combined_score"] > 0.999
            and reference["heldout_policy_score"] > 0.999
            and reference["robustness_score"] > 0.999
            and reference["heldout_robustness_score"] > 0.999
            and reference["development_physics_feasibility_rate"] == 1.0
            and reference["heldout_physics_feasibility_rate"] == 1.0
            and max(reference_grid_differences) < 0.08
            and reference["ghia_re100"]["u_centerline_rmse"] < 0.012
            and reference["ghia_re100"]["v_centerline_rmse"] < 0.015
            and injection["valid"] == 1.0
            and injection["combined_score"] == 0.0
            and injection["feasibility_rate"] == 0.0
            and attenuation_shortcut["ungated_development_score"] > 0.80
            and attenuation_shortcut["combined_score"] == 0.0
            and attenuation_shortcut["feasibility_rate"] == 0.0
        ),
    }


def _alloy_audit():
    task = ROOT / "benchmarks/MaterialsScience/AlloyHardnessOptimization"
    oracle = _oracle("MaterialsScience/AlloyHardnessOptimization")
    baseline = oracle.evaluate(oracle._baseline_policy)
    reference = oracle.evaluate(oracle._reference_policy)
    data = task / "verification/alloy_hardness_v1.json"
    anchors = oracle._anchors()
    return {
        "task": "MaterialsScience/AlloyHardnessOptimization",
        "admission": "candidate",
        "superseded_v1_defect": (
            "the removed task claimed an experimental-data surrogate but used a "
            "hand-written pseudo-physical polynomial without a dataset artifact"
        ),
        "resolved_defect": (
            "the current task is a hash-bound Borg MPEA replay with complete DOI "
            "grouping, a leakage-free historical proxy, charged study assays, "
            "citation-hash-held transfer, uncertainty and sparse independent "
            "exact-recipe confirmation"
        ),
        "dataset_artifact_present": data.is_file(),
        "development_world_count": len(oracle.DEVELOPMENT_WORLDS),
        "heldout_world_count": len(oracle.HELDOUT_WORLDS),
        "baseline_score": float(baseline["combined_score"]),
        "baseline_heldout_score": float(baseline["heldout_policy_score"]),
        "reference_score": float(reference["combined_score"]),
        "reference_heldout_score": float(reference["heldout_policy_score"]),
        "rebuild_passed": True,
        "passed": bool(
            oracle.ALLOY_HARDNESS_OPTIMIZATION_V1
            and data.is_file()
            and len(oracle.DEVELOPMENT_WORLDS) == 8
            and len(oracle.HELDOUT_WORLDS) == 5
            and baseline["valid"] == 1.0
            and baseline["combined_score"] == 0.0
            and baseline["heldout_policy_score"] == 0.0
            and reference["combined_score"] == 1.0
            and reference["heldout_policy_score"] == 1.0
            and anchors["split_development"]["reference_utility"]
            > anchors["split_development"]["baseline_utility"] + 0.05
            and anchors["split_heldout"]["reference_utility"]
            > anchors["split_heldout"]["baseline_utility"] + 0.05
        ),
    }


def _diffraction_audit():
    oracle = _oracle("Optics/DiffractionGratingDesign")
    baseline = oracle.evaluate(oracle.baseline_policy)
    reference = oracle.evaluate(oracle.reference_policy)
    minimum_nominal_headroom = min(
        world["reference_utility"] - world["baseline_utility"]
        for world in oracle.WORLDS
    )
    minimum_robust_headroom = min(
        world["reference_robust_utility"] - world["baseline_robust_utility"]
        for world in oracle.WORLDS
    )
    return {
        "task": "Optics/DiffractionGratingDesign",
        "admission": "candidate",
        "resolved_defect": (
            "v2 replaces the scalar phase FFT and analytic phase-ramp shortcut "
            "with a one-dimensional Fourier-modal Maxwell solve over six "
            "material/wavelength worlds, both polarizations, incidence angles "
            "and sealed fabrication/material shifts"
        ),
        "development_world_count": len(oracle.DEVELOPMENT_WORLDS),
        "heldout_world_count": len(oracle.HELDOUT_WORLDS),
        "sealed_shift_count": len(oracle.SHIFT_SPECS),
        "minimum_nominal_headroom": minimum_nominal_headroom,
        "minimum_robust_headroom": minimum_robust_headroom,
        "baseline_score": float(baseline["combined_score"]),
        "reference_score": float(reference["combined_score"]),
        "reference_heldout_score": float(reference["heldout_policy_score"]),
        "reference_robustness": float(reference["robustness_score"]),
        "reference_heldout_robustness": float(
            reference["heldout_robustness_score"]
        ),
        "passed": bool(
            oracle.RCWA_GRATING_V2
            and len(oracle.DEVELOPMENT_WORLDS) == 4
            and len(oracle.HELDOUT_WORLDS) == 2
            and len(oracle.SHIFT_SPECS) == 4
            and baseline["valid"] == 1.0
            and baseline["combined_score"] == 0.0
            and reference["valid"] == 1.0
            and reference["combined_score"] == 1.0
            and reference["heldout_policy_score"] == 1.0
            and reference["robustness_score"] == 1.0
            and reference["heldout_robustness_score"] == 1.0
            and minimum_nominal_headroom > 0.25
            and minimum_robust_headroom > 0.24
        ),
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
            "recommended_candidate_count": sum(
                row["admission"] == "candidate" for row in records
            ),
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
