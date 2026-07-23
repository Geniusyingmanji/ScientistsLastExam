#!/usr/bin/env python3
"""Calibrate ConvectionDiffusionOpt-v2 with truth-blind identification and design."""

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
from scipy.optimize import least_squares, minimize
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import spsolve


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/HeatTransfer/ConvectionDiffusionOpt"
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


# The first experiment deliberately probes only the horizontal midline.  It is a valid, high-
# signal assay, but its near-symmetry leaves the transverse transport parameters ill-conditioned.
# The second off-axis two-dimensional assay breaks that ambiguity.  This gives the active-design
# task a real two-stage information structure instead of letting one dense generic grid saturate it.
SENSOR_GRID = np.asarray([
    (x, 0.50) for x in np.linspace(0.08, 0.92, 24)
])
SECOND_SENSOR_GRID = np.asarray([
    (x, y) for x in np.linspace(0.15, 0.85, 5)
    for y in np.linspace(0.15, 0.85, 4)
])
EXPERIMENT_PLAN = (
    (np.asarray(((0.20, 0.50), (0.50, 0.50), (0.80, 0.50))),
     np.asarray((1.50, 1.25, 1.40)), SENSOR_GRID),
    (np.asarray(((0.73, 0.72),)), np.asarray((1.80,)), SECOND_SENSOR_GRID),
)
REFUSAL_REDUCED_CHI2 = 5.0
NULL_SIGNAL_TO_NOISE_THRESHOLD = 4.0


def _load_oracle():
    spec = importlib.util.spec_from_file_location(
        "convection_diffusion_v2_calibration_oracle",
        TASK / "verification/evaluator.py",
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load ConvectionDiffusionOpt-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _always_abstain(grid_shape, parameter_names, parameter_bounds,
                    design_specification, experiment, budget_units):
    del grid_shape, parameter_bounds, design_specification, experiment, budget_units
    return {
        "parameters": np.zeros(len(parameter_names)),
        "source_positions": np.zeros((4, 2)),
        "source_strengths": np.zeros(4),
        "confidence": 0.0,
        "abstain": True,
    }


def _fit_parameters(oracle, records, parameter_bounds, *, multistart=True):
    bounds = np.asarray(parameter_bounds, dtype=float)
    lower, upper = bounds[:, 0], bounds[:, 1]
    midpoint = 0.5 * (lower + upper)

    def residual(parameters):
        values = []
        for record in records:
            field = oracle.solve_public(
                parameters, record["source_positions"], record["source_strengths"]
            )
            predicted = oracle._bilinear_sample(field, record["sensor_positions"])
            values.extend(
                (predicted - record["temperature"])
                / float(record["temperature_noise_std"])
            )
        return np.asarray(values)

    initial_values = [midpoint]
    if multistart:
        initial_values.extend((
            lower + 0.20 * (upper - lower),
            lower + 0.80 * (upper - lower),
        ))
    fits = []
    for initial in initial_values:
        fit = least_squares(
            residual, initial, bounds=(lower, upper), x_scale="jac",
            max_nfev=120 if multistart else 60,
            ftol=1e-9 if multistart else 1e-8,
            xtol=1e-9 if multistart else 1e-8,
            gtol=1e-9 if multistart else 1e-8,
        )
        fits.append(fit)
    fit = min(fits, key=lambda row: float(np.sum(row.fun * row.fun)))
    degrees_of_freedom = max(1, len(fit.fun) - len(fit.x))
    signal_to_noise = math.sqrt(float(np.mean(np.concatenate([
        np.asarray(record["temperature"]) for record in records
    ]) ** 2))) / float(np.mean([
        record["temperature_noise_std"] for record in records
    ]))
    return {
        "parameters": fit.x.copy(),
        "reduced_chi2": float(np.sum(fit.fun * fit.fun) / degrees_of_freedom),
        "degrees_of_freedom": int(degrees_of_freedom),
        "jacobian_rank": int(np.linalg.matrix_rank(fit.jac)),
        "jacobian_condition_number": float(np.linalg.cond(fit.jac)),
        "signal_to_noise": float(signal_to_noise),
        "success": bool(fit.success),
        "n_function_evaluations": int(fit.nfev),
    }


def _optimize_design(oracle, parameters, specification):
    target = np.asarray(specification["target_temperature"], dtype=float)
    target_scale = max(1e-12, math.sqrt(float(np.mean(target * target))))
    margin = float(specification["source_margin"])
    minimum_separation = float(specification["minimum_source_separation"])
    lower_strength, upper_strength = map(
        float, specification["source_strength_bounds"]
    )
    total_limit = float(specification["total_source_strength_limit"])

    def objective(vector):
        positions = vector[:8].reshape((4, 2))
        strengths = vector[8:]
        predicted = oracle.solve_public(parameters, positions, strengths)
        relative_mse = float(np.mean((predicted - target) ** 2)) / target_scale**2
        excess = max(0.0, float(np.sum(strengths)) - total_limit + 0.01)
        distances = np.linalg.norm(
            positions[:, None, :] - positions[None, :, :], axis=2
        ) + np.eye(4)
        separation = np.maximum(0.0, minimum_separation + 0.005 - distances)
        return relative_mse + 2000.0 * excess**2 + 2000.0 * float(
            np.sum(separation**2)
        )

    rng = np.random.default_rng(20260723)
    starts = [
        np.concatenate((
            np.asarray(((0.20, 0.20), (0.20, 0.80),
                        (0.80, 0.20), (0.80, 0.80))).ravel(),
            np.full(4, 1.50),
        ))
    ]
    for _ in range(4):
        starts.append(np.concatenate((
            rng.uniform(margin + 0.04, 1.0 - margin - 0.04, size=(4, 2)).ravel(),
            rng.uniform(0.8, 1.9, size=4),
        )))
    bounds = (
        [(margin, 1.0 - margin)] * 8
        + [(lower_strength, upper_strength)] * 4
    )
    fits = [
        minimize(
            objective, initial, method="L-BFGS-B", bounds=bounds,
            options={"maxiter": 300, "ftol": 1e-11, "gtol": 1e-7, "maxls": 30},
        )
        for initial in starts
    ]
    fit = min(fits, key=lambda row: float(row.fun))
    positions = fit.x[:8].reshape((4, 2))
    strengths = fit.x[8:].copy()
    if np.sum(strengths) > total_limit:
        strengths *= (total_limit - 0.001) / np.sum(strengths)
    return positions, strengths


def _classical_policy(oracle, use_both_experiments=True):
    def policy(grid_shape, parameter_names, parameter_bounds,
               design_specification, experiment, budget_units):
        del grid_shape, parameter_names, budget_units
        plan = EXPERIMENT_PLAN if use_both_experiments else EXPERIMENT_PLAN[:1]
        records = [experiment(*row) for row in plan]
        fit = _fit_parameters(oracle, records, parameter_bounds)
        null = fit["signal_to_noise"] < NULL_SIGNAL_TO_NOISE_THRESHOLD
        misspecified = fit["reduced_chi2"] > REFUSAL_REDUCED_CHI2
        abstain = bool(null or misspecified)
        if abstain:
            positions = np.zeros((4, 2))
            strengths = np.zeros(4)
        else:
            positions, strengths = _optimize_design(
                oracle, fit["parameters"], design_specification
            )
        separation = abs(
            math.log(max(fit["reduced_chi2"], 1e-12) / REFUSAL_REDUCED_CHI2)
        )
        confidence = float(np.clip(separation / 3.0, 0.0, 1.0))
        if null:
            confidence = float(np.clip(
                (NULL_SIGNAL_TO_NOISE_THRESHOLD - fit["signal_to_noise"])
                / NULL_SIGNAL_TO_NOISE_THRESHOLD, 0.0, 1.0
            ))
        return {
            "parameters": fit["parameters"],
            "source_positions": positions,
            "source_strengths": strengths,
            "confidence": confidence,
            "abstain": abstain,
        }
    return policy


class _ReferencePolicy:
    def __init__(self, oracle):
        self.oracle = oracle
        self.index = 0

    def __call__(self, *_args):
        specs = list(self.oracle.DEVELOPMENT_SPECS) + list(self.oracle.HELDOUT_SPECS)
        world = self.oracle._world(specs[self.index])
        self.index += 1
        return self.oracle._reference_submission(world)


def _independent_solve(parameters, positions, strengths, grid_n):
    """Independent loop assembly of the printed homogeneous PDE."""
    n = int(grid_n)
    spacing = 1.0 / (n - 1)
    kx, ky, vx, vy, loss = map(float, parameters)
    source = np.zeros((n, n), dtype=float)
    coordinates = np.linspace(0.0, 1.0, n)
    xx, yy = np.meshgrid(coordinates, coordinates, indexing="ij")
    for position, strength in zip(positions, strengths):
        source += float(strength) * np.exp(
            -0.5 * ((xx - position[0]) ** 2 + (yy - position[1]) ** 2)
            / 0.055**2
        )
    source[[0, -1], :] = 0.0
    source[:, [0, -1]] = 0.0
    matrix = lil_matrix((n * n, n * n))
    rhs = source.ravel().copy()
    for i in range(n):
        for j in range(n):
            row = i * n + j
            if i in (0, n - 1) or j in (0, n - 1):
                matrix[row, row] = 1.0
                rhs[row] = 0.0
                continue
            matrix[row, row] = (
                2.0 * kx / spacing**2 + 2.0 * ky / spacing**2
                + abs(vx) / spacing + abs(vy) / spacing + loss
            )
            matrix[row, (i - 1) * n + j] = -kx / spacing**2 - max(vx, 0.0) / spacing
            matrix[row, (i + 1) * n + j] = -kx / spacing**2 + min(vx, 0.0) / spacing
            matrix[row, i * n + j - 1] = -ky / spacing**2 - max(vy, 0.0) / spacing
            matrix[row, i * n + j + 1] = -ky / spacing**2 + min(vy, 0.0) / spacing
    return np.asarray(spsolve(matrix.tocsc(), rhs)).reshape((n, n))


def _identifiability_checks(oracle):
    records = []
    for split, specs in (("development", oracle.DEVELOPMENT_SPECS),
                         ("heldout", oracle.HELDOUT_SPECS)):
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            if world["kind"] != "in_library":
                continue
            laboratory = oracle._ThermalLaboratory(world)
            observations = [laboratory.observe(*row) for row in EXPERIMENT_PLAN]
            fit = _fit_parameters(oracle, observations, oracle.PARAMETER_BOUNDS)
            scaled_error = (
                fit["parameters"] - world["parameters"]
            ) / oracle.PARAMETER_ADMISSION_TOLERANCES
            records.append({
                "split": split,
                "world_index": int(index),
                "maximum_scaled_parameter_error": float(np.max(np.abs(scaled_error))),
                "reduced_chi2": fit["reduced_chi2"],
                "jacobian_rank": fit["jacobian_rank"],
                "jacobian_condition_number": fit["jacobian_condition_number"],
                "signal_to_noise": fit["signal_to_noise"],
                "passed": bool(
                    fit["jacobian_rank"] == len(oracle.PARAMETER_NAMES)
                    and np.max(np.abs(scaled_error)) < 2.25
                    and fit["reduced_chi2"] < REFUSAL_REDUCED_CHI2
                ),
            })
    return records


def _single_experiment_ambiguity_checks(oracle):
    records = []
    for split, specs in (("development", oracle.DEVELOPMENT_SPECS),
                         ("heldout", oracle.HELDOUT_SPECS)):
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            if world["kind"] != "in_library":
                continue
            laboratory = oracle._ThermalLaboratory(world)
            observation = laboratory.observe(*EXPERIMENT_PLAN[0])
            fit = _fit_parameters(
                oracle, [observation], oracle.PARAMETER_BOUNDS, multistart=False
            )
            scaled_error = (
                fit["parameters"] - world["parameters"]
            ) / oracle.PARAMETER_ADMISSION_TOLERANCES
            mechanism = oracle._mechanism_quality(
                fit["parameters"], world["parameters"]
            )
            records.append({
                "split": split,
                "world_index": int(index),
                "maximum_scaled_parameter_error": float(
                    np.max(np.abs(scaled_error))
                ),
                "mechanism_quality": float(mechanism),
                "reduced_chi2": fit["reduced_chi2"],
                "jacobian_rank": fit["jacobian_rank"],
                "jacobian_condition_number": fit["jacobian_condition_number"],
                "passed": bool(
                    fit["jacobian_rank"] == len(oracle.PARAMETER_NAMES)
                    and fit["jacobian_condition_number"] > 1.0e3
                    and mechanism < 0.80
                ),
            })
    return records


def _unsupported_checks(oracle):
    records = []
    for split, specs in (("development", oracle.DEVELOPMENT_SPECS),
                         ("heldout", oracle.HELDOUT_SPECS)):
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            if world["kind"] == "in_library":
                continue
            laboratory = oracle._ThermalLaboratory(world)
            observations = [laboratory.observe(*row) for row in EXPERIMENT_PLAN]
            fit = _fit_parameters(oracle, observations, oracle.PARAMETER_BOUNDS)
            resolvable = (
                fit["signal_to_noise"] < NULL_SIGNAL_TO_NOISE_THRESHOLD
                if world["kind"] == "null"
                else fit["reduced_chi2"] > REFUSAL_REDUCED_CHI2 + 5.0
            )
            records.append({
                "split": split,
                "world_index": int(index),
                "kind": world["kind"],
                "reduced_chi2": fit["reduced_chi2"],
                "signal_to_noise": fit["signal_to_noise"],
                "passed": bool(resolvable),
            })
    return records


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(_always_abstain)
    classical = oracle.evaluate(_classical_policy(oracle, True))
    underinformative = oracle.evaluate(_classical_policy(oracle, False))
    reference = oracle.evaluate(_ReferencePolicy(oracle))
    identifiability = _identifiability_checks(oracle)
    single_experiment_ambiguity = _single_experiment_ambiguity_checks(oracle)
    unsupported = _unsupported_checks(oracle)

    rng = np.random.default_rng(20260723)
    independent_checks = []
    for case in range(4):
        parameters = (
            oracle.PARAMETER_BOUNDS[:, 0]
            + rng.uniform(size=len(oracle.PARAMETER_NAMES))
            * (oracle.PARAMETER_BOUNDS[:, 1] - oracle.PARAMETER_BOUNDS[:, 0])
        )
        positions = rng.uniform(0.10, 0.90, size=(3, 2))
        strengths = rng.uniform(0.2, 1.6, size=3)
        production = oracle.solve_public(parameters, positions, strengths, 19)
        independent = _independent_solve(parameters, positions, strengths, 19)
        error = float(np.max(np.abs(production - independent)))
        independent_checks.append({
            "case": case, "maximum_absolute_error": error,
            "passed": error < 1e-12,
        })

    invalid_candidates = {
        "nonfinite": lambda *_args: {
            "parameters": np.full(5, np.nan),
            "source_positions": np.full((4, 2), np.nan),
            "source_strengths": np.full(4, np.nan),
            "confidence": 0.5, "abstain": False,
        },
        "bad_shape": lambda *_args: {
            "parameters": np.zeros(4), "source_positions": np.zeros((3, 2)),
            "source_strengths": np.zeros(3), "confidence": 0.5,
            "abstain": False,
        },
        "out_of_bounds": lambda *_args: {
            "parameters": np.full(5, 10.0),
            "source_positions": np.full((4, 2), 0.5),
            "source_strengths": np.full(4, 10.0),
            "confidence": 0.5, "abstain": False,
        },
    }
    invalid = {name: oracle.evaluate(candidate) for name, candidate in invalid_candidates.items()}
    difficulty_passed = bool(
        0.80 < classical["combined_score"] < 0.97
        and 0.80 < classical["heldout_policy_score"] < 0.97
        and classical["development_supported_claim_coverage"] == 1.0
        and classical["heldout_supported_claim_coverage"] == 1.0
        and classical["development_false_discovery_rate"] == 0.0
        and classical["heldout_false_discovery_rate"] == 0.0
        and classical["development_correct_refusal_rate"] == 1.0
        and classical["heldout_correct_refusal_rate"] == 1.0
        and classical["development_mean_budget_units"] == oracle.EXPERIMENT_BUDGET_UNITS
        and classical["heldout_mean_budget_units"] == oracle.EXPERIMENT_BUDGET_UNITS
        and underinformative["development_mean_budget_units"] == 7.0
        and underinformative["heldout_mean_budget_units"] == 7.0
        and underinformative["combined_score"] < 0.10
        and underinformative["heldout_policy_score"] < 0.10
        and classical["combined_score"] - underinformative["combined_score"] > 0.80
        and classical["heldout_policy_score"]
        - underinformative["heldout_policy_score"] > 0.80
    )
    invalid_passed = all(
        row["valid"] == 0.0 and row["combined_score"] == 0.0
        and row["raw_score"] == 0.0 for row in invalid.values()
    )
    execution_passed = bool(
        oracle.CONVECTION_DIFFUSION_V2
        and baseline["valid"] == 1.0 and baseline["combined_score"] == 0.0
        and reference["valid"] == 1.0 and reference["combined_score"] == 1.0
        and reference["heldout_policy_score"] == 1.0
        and reference["robustness_score"] == 1.0
        and reference["heldout_robustness_score"] == 1.0
        and classical["valid"] == 1.0 and classical["heldout_feasibility_rate"] == 1.0
        and underinformative["valid"] == 1.0
        and difficulty_passed and invalid_passed
        and all(row["passed"] for row in identifiability)
        and all(row["passed"] for row in single_experiment_ambiguity)
        and all(row["passed"] for row in unsupported)
        and all(row["passed"] for row in independent_checks)
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "SYNTHETIC_ACTIVE_CONVECTION_DIFFUSION_TASK_CALIBRATION_NOT_"
            "CONTINUUM_DEVICE_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "task_dimensions": {
            "grid_shape": list(oracle.GRID_SHAPE),
            "parameter_count": len(oracle.PARAMETER_NAMES),
            "design_source_count": oracle.N_DESIGN_SOURCES,
            "development_world_count": len(oracle.DEVELOPMENT_SPECS),
            "heldout_world_count": len(oracle.HELDOUT_SPECS),
            "shift_count": len(oracle.SHIFT_SPECS),
            "experiment_budget_units": oracle.EXPERIMENT_BUDGET_UNITS,
        },
        "always_abstain_baseline": baseline,
        "truth_blind_two_experiment_policy": classical,
        "truth_blind_one_experiment_policy": underinformative,
        "exact_mechanism_replayable_design_reference": reference,
        "identifiability_checks": identifiability,
        "single_experiment_ambiguity_checks": single_experiment_ambiguity,
        "unsupported_resolvability_checks": unsupported,
        "independent_equation_checks": independent_checks,
        "invalid_artifact_checks": invalid,
        "difficulty_gate": {
            "classical_development_interval": [0.80, 0.97],
            "classical_heldout_interval": [0.80, 0.97],
            "maximum_single_experiment_score": 0.10,
            "minimum_two_minus_one_gap": 0.80,
            "two_experiment_budget": oracle.EXPERIMENT_BUDGET_UNITS,
            "one_experiment_budget": 7,
            "requires_two_experiment_advantage": True,
            "passed": difficulty_passed,
        },
        "limitations": [
            "The oracle is a synthetic steady finite-difference laboratory, not a continuum convergence proof, conjugate heat-transfer model or physical device.",
            "Spatial heterogeneity is deliberately strengthened so model inadequacy is resolvable under the finite observation budget.",
            "The four-source witnesses are reproducible local-search results, not certificates of global optimality.",
            "Repository-visible worlds require server-held procedural worlds and independent heat-transfer review before population or discovery claims.",
            "Task calibration does not measure GPT-5.5, causal feedback learning or autonomous scientific discovery.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = calibrate()
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
