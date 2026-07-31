#!/usr/bin/env python3
"""Calibrate LidDrivenCavity-v2 physics, references and shortcut rejection."""

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


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Engineering/LidDrivenCavity"
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("cavity_v2_calibration", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load LidDrivenCavity-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _velocity(streamfunction):
    """Independently derive the velocity field from a streamfunction."""
    psi = np.asarray(streamfunction, dtype=float)
    h = 1.0 / (psi.shape[0] - 1)
    u = np.zeros_like(psi)
    v = np.zeros_like(psi)
    u[1:-1, 1:-1] = (
        psi[2:, 1:-1] - psi[:-2, 1:-1]
    ) / (2.0 * h)
    v[1:-1, 1:-1] = -(
        psi[1:-1, 2:] - psi[1:-1, :-2]
    ) / (2.0 * h)
    u[-1, 1:-1] = 1.0
    return u, v


def _independent_equation_check(streamfunction, vorticity, reynolds):
    """Recompute every public finite-difference equation without oracle helpers."""
    psi = np.asarray(streamfunction, dtype=float)
    omega = np.asarray(vorticity, dtype=float)
    n = psi.shape[0]
    h = 1.0 / (n - 1)
    laplacian_psi = (
        psi[2:, 1:-1] + psi[:-2, 1:-1]
        + psi[1:-1, 2:] + psi[1:-1, :-2]
        - 4.0 * psi[1:-1, 1:-1]
    )
    source = h * h * omega[1:-1, 1:-1]
    poisson = laplacian_psi + source
    poisson_scale = math.sqrt(float(np.mean(
        laplacian_psi**2 + source**2
    ))) + 1.0e-12

    u, v = _velocity(psi)
    diffusion = (
        omega[2:, 1:-1] + omega[:-2, 1:-1]
        + omega[1:-1, 2:] + omega[1:-1, :-2]
        - 4.0 * omega[1:-1, 1:-1]
    )
    convection = float(reynolds) * h * 0.5 * (
        u[1:-1, 1:-1]
        * (omega[1:-1, 2:] - omega[1:-1, :-2])
        + v[1:-1, 1:-1]
        * (omega[2:, 1:-1] - omega[:-2, 1:-1])
    )
    transport = diffusion - convection
    transport_scale = math.sqrt(float(np.mean(
        diffusion**2 + convection**2
    ))) + 1.0e-12

    expected = np.zeros_like(omega)
    expected[0, 1:-1] = -2.0 * psi[1, 1:-1] / h**2
    expected[-1, 1:-1] = -2.0 * psi[-2, 1:-1] / h**2 - 2.0 / h
    expected[1:-1, 0] = -2.0 * psi[1:-1, 1] / h**2
    expected[1:-1, -1] = -2.0 * psi[1:-1, -2] / h**2
    observed_walls = np.concatenate((
        omega[0, 1:-1], omega[-1, 1:-1],
        omega[1:-1, 0], omega[1:-1, -1],
    ))
    expected_walls = np.concatenate((
        expected[0, 1:-1], expected[-1, 1:-1],
        expected[1:-1, 0], expected[1:-1, -1],
    ))
    wall_psi = np.concatenate((
        psi[0], psi[-1], psi[1:-1, 0], psi[1:-1, -1],
    ))
    wall_error = max(
        float(np.max(np.abs(wall_psi))) / 0.01,
        math.sqrt(float(np.mean((observed_walls - expected_walls) ** 2)))
        / (2.0 / h),
    )

    divergence = (
        (u[2:-2, 3:-1] - u[2:-2, 1:-3])
        + (v[3:-1, 2:-2] - v[1:-3, 2:-2])
    ) / (2.0 * h)
    return {
        "poisson_relative_residual": float(
            math.sqrt(float(np.mean(poisson**2))) / poisson_scale
        ),
        "transport_relative_residual": float(
            math.sqrt(float(np.mean(transport**2))) / transport_scale
        ),
        "boundary_relative_error": float(wall_error),
        "maximum_absolute_scaled_poisson_residual": float(
            np.max(np.abs(poisson))
        ),
        "maximum_absolute_scaled_transport_residual": float(
            np.max(np.abs(transport))
        ),
        "maximum_absolute_discrete_divergence": float(
            np.max(np.abs(divergence))
        ),
        "finite": bool(np.all(np.isfinite(psi)) and np.all(np.isfinite(omega))),
        "maximum_absolute_streamfunction": float(np.max(np.abs(psi))),
        "maximum_absolute_vorticity": float(np.max(np.abs(omega))),
    }


def _resample(field, target_n):
    values = np.asarray(field, dtype=float)
    source = np.linspace(0.0, 1.0, values.shape[0])
    target = np.linspace(0.0, 1.0, int(target_n))
    rows = np.asarray([np.interp(target, source, row) for row in values])
    return np.asarray([
        np.interp(target, source, rows[:, column])
        for column in range(int(target_n))
    ]).T


def _grid_difference(coarse_psi, fine_psi, target_n):
    coarse_u, coarse_v = _velocity(coarse_psi)
    fine_u, fine_v = _velocity(fine_psi)
    coarse_u = _resample(coarse_u, target_n)
    coarse_v = _resample(coarse_v, target_n)
    fine_u = _resample(fine_u, target_n)
    fine_v = _resample(fine_v, target_n)
    scale = math.sqrt(float(np.mean(fine_u**2 + fine_v**2))) + 1.0e-12
    return float(math.sqrt(float(np.mean(
        (coarse_u - fine_u) ** 2 + (coarse_v - fine_v) ** 2
    ))) / scale)


def _ghia_check(oracle, streamfunction):
    u, v = _velocity(streamfunction)
    grid = np.linspace(0.0, 1.0, u.shape[0])
    middle = u.shape[0] // 2
    u_error = (
        np.interp(oracle.GHIA_RE100_U[:, 0], grid, u[:, middle])
        - oracle.GHIA_RE100_U[:, 1]
    )
    v_error = (
        np.interp(oracle.GHIA_RE100_V[:, 0], grid, v[middle, :])
        - oracle.GHIA_RE100_V[:, 1]
    )
    return {
        "u_centerline_rmse": float(np.sqrt(np.mean(u_error**2))),
        "v_centerline_rmse": float(np.sqrt(np.mean(v_error**2))),
        "u_centerline_max_error": float(np.max(np.abs(u_error))),
        "v_centerline_max_error": float(np.max(np.abs(v_error))),
    }


def _summary(metrics):
    keys = (
        "combined_score", "valid", "feasibility_rate", "robustness_score",
        "ungated_development_score", "ungated_robustness_score",
        "heldout_policy_score", "heldout_robustness_score",
        "ungated_heldout_policy_score", "ungated_heldout_robustness_score",
        "heldout_artifact_valid_rate",
        "development_physics_feasibility_rate",
        "heldout_physics_feasibility_rate",
        "development_grid_feasibility_rate",
        "heldout_grid_feasibility_rate", "candidate_call_count",
        "candidate_call_valid_rate",
    )
    return {key: metrics[key] for key in keys}


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(
        lambda _reynolds, n: oracle._weak_baseline_fields(int(n))
    )

    def reference_policy(reynolds, n):
        return tuple(
            field.copy()
            for field in oracle._reference_solution(float(reynolds), int(n))
        )

    reference = oracle.evaluate(reference_policy)

    def stripe_injection(_reynolds, n):
        psi, omega = oracle._weak_baseline_fields(int(n))
        psi[:, int(n) // 2] = np.linspace(0.0, -0.05, int(n))
        return psi, omega

    injection = oracle.evaluate(stripe_injection)

    def attenuated_reference(reynolds, n):
        psi, omega = reference_policy(reynolds, n)
        _baseline_psi, baseline_omega = oracle._weak_baseline_fields(int(n))
        attenuation = 0.95
        return (
            attenuation * psi,
            attenuation * omega + (1.0 - attenuation) * baseline_omega,
        )

    attenuation_shortcut = oracle.evaluate(attenuated_reference)

    invalid_factories = {
        "wrong_shape": lambda n: (
            np.zeros((n - 1, n)), np.zeros((n, n))
        ),
        "nonfinite": lambda n: (
            np.full((n, n), np.nan), np.zeros((n, n))
        ),
        "streamfunction_bound": lambda n: (
            np.full((n, n), 2.01), np.zeros((n, n))
        ),
        "vorticity_bound": lambda n: (
            np.zeros((n, n)), np.full((n, n), 12.01 * n)
        ),
        "wrong_container": lambda n: np.zeros((n, n)),
    }
    invalid = {}
    for name, factory in invalid_factories.items():
        metrics = oracle.evaluate(
            lambda _reynolds, n, factory=factory: factory(int(n))
        )
        invalid[name] = {
            "combined_score": metrics["combined_score"],
            "valid": metrics["valid"],
            "feasibility_rate": metrics["feasibility_rate"],
            "candidate_call_valid_rate": metrics["candidate_call_valid_rate"],
        }

    scenarios = list(oracle.INSTANCES) + [
        {
            "name": spec["name"] + "_fine",
            "split": spec["split"],
            "Re": spec["Re"],
            "N": spec["fine_N"],
        }
        for spec in oracle.GRID_REFINEMENT_SPECS
    ]
    fields = {}
    equation_checks = []
    maximum_oracle_diagnostic_difference = 0.0
    for scenario in scenarios:
        psi, omega = reference_policy(scenario["Re"], scenario["N"])
        fields[scenario["name"]] = (psi, omega)
        independent = _independent_equation_check(
            psi, omega, scenario["Re"]
        )
        oracle_poisson, oracle_transport = oracle._relative_residuals(
            psi, omega, scenario["Re"]
        )
        oracle_boundary = oracle._boundary_error(psi, omega)
        maximum_oracle_diagnostic_difference = max(
            maximum_oracle_diagnostic_difference,
            abs(independent["poisson_relative_residual"] - oracle_poisson),
            abs(independent["transport_relative_residual"] - oracle_transport),
            abs(independent["boundary_relative_error"] - oracle_boundary),
        )
        equation_checks.append({
            "name": scenario["name"],
            "split": scenario["split"],
            "Re": float(scenario["Re"]),
            "N": int(scenario["N"]),
            **independent,
        })

    refinement_checks = []
    evaluator_refinements = {
        row["name"]: row for row in reference["grid_refinement"]
    }
    for spec in oracle.GRID_REFINEMENT_SPECS:
        coarse_psi = fields[spec["coarse_name"]][0]
        fine_psi = fields[spec["name"] + "_fine"][0]
        difference_21 = _grid_difference(coarse_psi, fine_psi, 21)
        difference_65 = _grid_difference(coarse_psi, fine_psi, 65)
        reported = float(
            evaluator_refinements[spec["name"]]["reference_grid_difference"]
        )
        refinement_checks.append({
            "name": spec["name"],
            "split": spec["split"],
            "coarse_N": int(fields[spec["coarse_name"]][0].shape[0]),
            "fine_N": int(spec["fine_N"]),
            "independent_relative_velocity_difference_21": difference_21,
            "independent_relative_velocity_difference_65": difference_65,
            "evaluator_reported_difference": reported,
            "absolute_reproduction_error": abs(difference_21 - reported),
        })

    ghia = _ghia_check(oracle, fields["dev_re100"][0])
    equation_passed = all(
        row["finite"]
        and row["poisson_relative_residual"] < 1.0e-6
        and row["transport_relative_residual"] < 1.0e-6
        and row["boundary_relative_error"] < 1.0e-10
        and row["maximum_absolute_scaled_poisson_residual"] < 2.0e-7
        and row["maximum_absolute_scaled_transport_residual"] < 2.0e-7
        and row["maximum_absolute_discrete_divergence"] < 1.0e-12
        for row in equation_checks
    )
    refinement_passed = all(
        row["independent_relative_velocity_difference_21"] < 0.08
        and row["independent_relative_velocity_difference_65"] < 0.08
        and row["absolute_reproduction_error"] < 1.0e-12
        for row in refinement_checks
    )
    invalid_passed = all(
        row["valid"] == 0.0
        and row["combined_score"] == 0.0
        and row["feasibility_rate"] == 0.0
        and row["candidate_call_valid_rate"] == 0.0
        for row in invalid.values()
    )
    execution_passed = bool(
        oracle.CAVITY_V2
        and len(oracle.INSTANCES) == 6
        and len(oracle.GRID_REFINEMENT_SPECS) == 2
        and baseline["valid"] == 1.0
        and baseline["combined_score"] == 0.0
        and baseline["feasibility_rate"] == 0.0
        and reference["valid"] == 1.0
        and reference["combined_score"] > 0.999
        and reference["robustness_score"] > 0.999
        and reference["heldout_policy_score"] > 0.999
        and reference["heldout_robustness_score"] > 0.999
        and reference["development_physics_feasibility_rate"] == 1.0
        and reference["heldout_physics_feasibility_rate"] == 1.0
        and injection["valid"] == 1.0
        and injection["combined_score"] == 0.0
        and injection["feasibility_rate"] == 0.0
        and attenuation_shortcut["ungated_development_score"] > 0.80
        and attenuation_shortcut["combined_score"] == 0.0
        and attenuation_shortcut["feasibility_rate"] == 0.0
        and invalid_passed
        and equation_passed
        and maximum_oracle_diagnostic_difference < 1.0e-12
        and refinement_passed
        and ghia["u_centerline_rmse"] < 0.012
        and ghia["v_centerline_rmse"] < 0.015
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "CONTROLLED_STEADY_LAMINAR_CFD_TASK_CALIBRATION_NOT_TURBULENCE_"
            "EXPERIMENTAL_VALIDATION_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "task_dimensions": {
            "development_case_count": sum(
                row["split"] == "development" for row in oracle.INSTANCES
            ),
            "heldout_case_count": sum(
                row["split"] == "heldout" for row in oracle.INSTANCES
            ),
            "refinement_call_count": len(oracle.GRID_REFINEMENT_SPECS),
            "total_candidate_call_count": 8,
            "reynolds_range": [
                min(row["Re"] for row in oracle.INSTANCES),
                max(row["Re"] for row in oracle.INSTANCES),
            ],
        },
        "public_feasibility_tolerances": {
            "poisson_relative_residual": oracle.POISSON_FEASIBILITY_TOLERANCE,
            "transport_relative_residual": oracle.TRANSPORT_FEASIBILITY_TOLERANCE,
            "boundary_relative_error": oracle.BOUNDARY_FEASIBILITY_TOLERANCE,
        },
        "weak_baseline": _summary(baseline),
        "trusted_reference_policy": _summary(reference),
        "nonphysical_stripe_injection": _summary(injection),
        "attenuated_near_reference_shortcut": _summary(attenuation_shortcut),
        "invalid_artifact_checks": invalid,
        "independent_equation_checks": equation_checks,
        "maximum_oracle_diagnostic_reproduction_error": (
            maximum_oracle_diagnostic_difference
        ),
        "independent_grid_refinement_checks": refinement_checks,
        "independent_ghia_re100_check": ghia,
        "difficulty_and_integrity_gate": {
            "weak_baseline_valid_but_zero": bool(
                baseline["valid"] == 1.0
                and baseline["combined_score"] == 0.0
                and baseline["feasibility_rate"] == 0.0
            ),
            "reference_full_and_heldout_scores_above_0_999": bool(
                reference["combined_score"] > 0.999
                and reference["robustness_score"] > 0.999
                and reference["heldout_policy_score"] > 0.999
                and reference["heldout_robustness_score"] > 0.999
            ),
            "nonphysical_injection_zero": bool(
                injection["combined_score"] == 0.0
                and injection["feasibility_rate"] == 0.0
            ),
            "near_reference_similarity_cannot_bypass_physics_gate": bool(
                attenuation_shortcut["ungated_development_score"] > 0.80
                and attenuation_shortcut["combined_score"] == 0.0
                and attenuation_shortcut["feasibility_rate"] == 0.0
            ),
            "invalid_artifacts_fail_closed": invalid_passed,
            "independent_equations_passed": equation_passed,
            "independent_grid_refinement_passed": refinement_passed,
            "literature_profile_passed": bool(
                ghia["u_centerline_rmse"] < 0.012
                and ghia["v_centerline_rmse"] < 0.015
            ),
            "passed": execution_passed,
        },
        "reference_method": {
            "description": (
                "Deterministic second-order streamfunction-vorticity Newton-Krylov "
                "Reynolds continuation, checked here by separately implemented equations, "
                "discrete incompressibility, grid transfer and published Re=100 profiles."
            ),
            "continuum_exactness_claimed": False,
            "global_solver_optimality_claimed": False,
            "experimental_truth_claimed": False,
        },
        "limitations": [
            "The model is a two-dimensional steady laminar square cavity on modest second-order uniform grids.",
            "Public deterministic Reynolds/grid inputs permit case-specific branching; server-held procedural cases are still required before certification.",
            "The Ghia comparison is sparse literature validation, not an independent high-order full-field solution or experiment.",
            "Task-calibration scores do not measure GPT-5.5, feedback causality, population capability or autonomous scientific discovery.",
        ],
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
