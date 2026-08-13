#!/usr/bin/env python3
"""Calibrate EnergyBalanceModel-v2 with independent dynamics and fitting."""

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
from scipy.linalg import expm
from scipy.optimize import least_squares


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/EarthScience/EnergyBalanceModel"
sys.path.insert(0, str(ROOT))

from sle.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


LONG_MULTISCALE_FORCING = np.concatenate((
    np.full(80, 8.0),
    np.zeros(40),
    np.repeat(np.asarray((-1.0, 4.0, 1.0, 6.0)), 10),
))
SHORT_ABRUPT_FORCING = np.concatenate((
    np.full(48, 4.0), np.zeros(32),
))
REFUSAL_REDUCED_CHI2 = 1.50
MINIMUM_MISSPECIFICATION_MARGIN = 0.25


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location(
        "climate_v2_calibration_oracle", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load EnergyBalanceModel-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _public_transition(parameters):
    """Independent implementation of the public continuous-time equations."""
    feedback, surface_capacity, deep_capacity, exchange, forcing_scale = map(
        float, parameters
    )
    matrix = np.asarray((
        (-(feedback + exchange) / surface_capacity,
         exchange / surface_capacity),
        (exchange / deep_capacity, -exchange / deep_capacity),
    ))
    forcing_vector = np.asarray((forcing_scale / surface_capacity, 0.0))
    augmented = np.zeros((3, 3), dtype=float)
    augmented[:2, :2] = matrix
    augmented[:2, 2] = forcing_vector
    transition = expm(augmented)
    return transition[:2, :2], transition[:2, 2]


def _public_simulate(parameters, forcing_w_m2):
    forcing = np.asarray(forcing_w_m2, dtype=float).ravel()
    transition, response = _public_transition(parameters)
    state = np.zeros(2, dtype=float)
    surface = np.empty(len(forcing), dtype=float)
    deep = np.empty(len(forcing), dtype=float)
    imbalance = np.empty(len(forcing), dtype=float)
    feedback, _, _, _, forcing_scale = map(float, parameters)
    for index, value in enumerate(forcing):
        state = transition @ state + response * float(value)
        surface[index], deep[index] = state
        imbalance[index] = forcing_scale * float(value) - feedback * state[0]
    return surface, deep, imbalance


def _rk4_public(parameters, forcing_w_m2, substeps=100):
    """Integrate the printed ODE without using the evaluator recurrence."""
    feedback, surface_capacity, deep_capacity, exchange, forcing_scale = map(
        float, parameters
    )
    forcing = np.asarray(forcing_w_m2, dtype=float).ravel()
    state = np.zeros(2, dtype=float)
    surface = np.empty(len(forcing), dtype=float)
    deep = np.empty(len(forcing), dtype=float)
    imbalance = np.empty(len(forcing), dtype=float)
    step = 1.0 / int(substeps)

    def derivative(value, external_forcing):
        surface_value, deep_value = value
        uptake = exchange * (surface_value - deep_value)
        return np.asarray((
            (forcing_scale * external_forcing
             - feedback * surface_value - uptake) / surface_capacity,
            uptake / deep_capacity,
        ))

    for index, value in enumerate(forcing):
        for _ in range(int(substeps)):
            k1 = derivative(state, value)
            k2 = derivative(state + 0.5 * step * k1, value)
            k3 = derivative(state + 0.5 * step * k2, value)
            k4 = derivative(state + step * k3, value)
            state = state + step * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
        surface[index], deep[index] = state
        imbalance[index] = forcing_scale * float(value) - feedback * state[0]
    return surface, deep, imbalance


def _always_abstain(parameter_names, parameter_bounds, experiment, budget_units):
    del parameter_bounds, experiment, budget_units
    return {
        "parameters": np.zeros(len(parameter_names), dtype=float),
        "confidence": 0.0,
        "abstain": True,
    }


def _fit_records(records, parameter_bounds):
    bounds = np.asarray(parameter_bounds, dtype=float)
    lower, upper = bounds[:, 0], bounds[:, 1]
    midpoint = 0.5 * (lower + upper)

    def residual(parameters):
        values = []
        for record in records:
            surface, _deep, imbalance = _public_simulate(
                parameters, record["forcing_w_m2"]
            )
            values.extend((
                (surface - record["surface_temperature_anomaly_k"])
                / float(record["surface_noise_std_k"]),
                (imbalance - record["toa_imbalance_w_m2"])
                / float(record["toa_noise_std_w_m2"]),
            ))
        return np.concatenate(values)

    best = None
    for initial in (
        midpoint,
        lower + 0.20 * (upper - lower),
        lower + 0.80 * (upper - lower),
    ):
        fit = least_squares(
            residual, initial, bounds=(lower, upper), x_scale="jac",
            max_nfev=700, ftol=1e-10, xtol=1e-10, gtol=1e-10,
        )
        chi2 = float(np.sum(fit.fun * fit.fun))
        if best is None or chi2 < best[0]:
            best = (chi2, fit)
    chi2, fit = best
    degrees_of_freedom = len(fit.fun) - len(fit.x)
    singular = np.linalg.svd(fit.jac, compute_uv=False)
    return {
        "parameters": fit.x.copy(),
        "chi2": chi2,
        "reduced_chi2": chi2 / degrees_of_freedom,
        "degrees_of_freedom": int(degrees_of_freedom),
        "jacobian_rank": int(np.linalg.matrix_rank(fit.jac)),
        "jacobian_condition_number": float(singular[0] / singular[-1]),
        "success": bool(fit.success),
        "n_function_evaluations": int(fit.nfev),
    }


def _decision_confidence(reduced_chi2, degrees_of_freedom):
    # A reduced chi-square fluctuates by approximately sqrt(2/dof) under the
    # supported model.  Confidence measures distance from the preregistered
    # decision boundary, capped after three such standard deviations.
    standard_error = math.sqrt(2.0 / max(int(degrees_of_freedom), 1))
    return float(np.clip(
        abs(float(reduced_chi2) - REFUSAL_REDUCED_CHI2)
        / (3.0 * standard_error), 0.0, 1.0
    ))


def _classical_policy(forcing):
    forcing = np.asarray(forcing, dtype=float).copy()

    def identify(parameter_names, parameter_bounds, experiment, budget_units):
        del parameter_names, budget_units
        record = experiment(forcing)
        fit = _fit_records([record], parameter_bounds)
        abstain = bool(fit["reduced_chi2"] > REFUSAL_REDUCED_CHI2)
        return {
            "parameters": fit["parameters"],
            "confidence": _decision_confidence(
                fit["reduced_chi2"], fit["degrees_of_freedom"]
            ),
            "abstain": abstain,
        }

    return identify


class _ExactReferencePolicy:
    def __init__(self, oracle):
        self.oracle = oracle
        self.call_index = 0

    def __call__(self, *_args):
        specs = list(self.oracle.DEVELOPMENT_SPECS) + list(
            self.oracle.HELDOUT_SPECS
        )
        world = self.oracle._world(specs[self.call_index])
        self.call_index += 1
        return self.oracle._reference_submission(world)


def _identifiability_record(oracle, world, split, index):
    truth = np.asarray(world["parameters"], dtype=float)
    parameter_steps = np.asarray((1e-4, 1e-3, 1e-2, 1e-4, 1e-5))
    jacobian = np.empty((2 * len(LONG_MULTISCALE_FORCING), len(truth)))
    for column, step in enumerate(parameter_steps):
        upper = truth.copy()
        lower = truth.copy()
        upper[column] += step
        lower[column] -= step
        upper_surface, _upper_deep, upper_imbalance = _public_simulate(
            upper, LONG_MULTISCALE_FORCING
        )
        lower_surface, _lower_deep, lower_imbalance = _public_simulate(
            lower, LONG_MULTISCALE_FORCING
        )
        jacobian[:, column] = np.concatenate((
            (upper_surface - lower_surface)
            / (2.0 * step * oracle.SURFACE_NOISE_STD_K),
            (upper_imbalance - lower_imbalance)
            / (2.0 * step * oracle.TOA_NOISE_STD_W_M2),
        ))
    scaled = jacobian * oracle.PARAMETER_TOLERANCES[None, :]
    singular = np.linalg.svd(scaled, compute_uv=False)
    rank = int(np.linalg.matrix_rank(scaled, tol=singular[0] * 1e-10))
    condition = float(singular[0] / singular[-1])
    return {
        "split": split,
        "world_index": int(index),
        "jacobian_shape": list(scaled.shape),
        "jacobian_rank": rank,
        "condition_number": condition,
        "minimum_scaled_singular_value": float(singular[-1]),
        "passed": bool(
            rank == len(truth) and condition < 25.0
            and singular[-1] > 0.30
        ),
    }


def _clean_fit_record(oracle, world, split, index):
    surface, _deep, imbalance = oracle._clean_response(
        world, LONG_MULTISCALE_FORCING
    )
    record = {
        "forcing_w_m2": LONG_MULTISCALE_FORCING.copy(),
        "surface_temperature_anomaly_k": surface,
        "toa_imbalance_w_m2": imbalance,
        "surface_noise_std_k": oracle.SURFACE_NOISE_STD_K,
        "toa_noise_std_w_m2": oracle.TOA_NOISE_STD_W_M2,
    }
    fit = _fit_records([record], oracle.PARAMETER_BOUNDS)
    # Clean structural mismatch contributes this amount on top of the unit
    # expected reduced chi-square from observational noise.
    expected_noisy_reduced_chi2 = 1.0 + fit["reduced_chi2"]
    return {
        "split": split,
        "world_index": int(index),
        "kind": world["kind"],
        "best_public_parameters": fit["parameters"].tolist(),
        "clean_structural_reduced_chi2": float(fit["reduced_chi2"]),
        "expected_noisy_reduced_chi2": float(expected_noisy_reduced_chi2),
        "refusal_threshold": REFUSAL_REDUCED_CHI2,
        "minimum_required_margin": MINIMUM_MISSPECIFICATION_MARGIN,
        "fit_success": fit["success"],
        "passed": bool(
            fit["success"]
            and expected_noisy_reduced_chi2
            > REFUSAL_REDUCED_CHI2 + MINIMUM_MISSPECIFICATION_MARGIN
        ),
    }


def _exact_checks(oracle):
    records = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            submission = oracle._reference_submission(world)
            parameters, _confidence, abstain = oracle._validate_submission(
                submission
            )
            if world["kind"] == "in_library":
                mechanism = oracle._mechanism_score(
                    parameters, world["parameters"]
                )
                nominal = oracle._prediction_score(world, parameters, False)
                shifted = oracle._prediction_score(world, parameters, True)
                passed = mechanism == nominal == shifted == 1.0 and not abstain
            else:
                mechanism = 1.0 if abstain else 0.0
                nominal = shifted = 1.0 if abstain else 0.0
                passed = abstain
            records.append({
                "split": split,
                "world_index": int(index),
                "kind": world["kind"],
                "mechanism_score": float(mechanism),
                "nominal_prediction_score": float(nominal),
                "forcing_shift_score": float(shifted),
                "passed": bool(passed),
            })
    return records


def _physics_checks(oracle):
    rng = np.random.default_rng(20260722)
    recurrence_errors = []
    rk4_errors = []
    for case in range(4):
        parameters = (
            oracle.PARAMETER_BOUNDS[:, 0]
            + rng.uniform(size=len(oracle.PARAMETER_NAMES))
            * (oracle.PARAMETER_BOUNDS[:, 1] - oracle.PARAMETER_BOUNDS[:, 0])
        )
        forcing = rng.uniform(-1.0, 8.0, size=32)
        independent = _public_simulate(parameters, forcing)
        evaluator = oracle.simulate_public(parameters, forcing)
        recurrence_error = max(
            float(np.max(np.abs(left - right)))
            for left, right in zip(independent, evaluator)
        )
        rk4 = _rk4_public(parameters, forcing)
        rk4_error = max(
            float(np.max(np.abs(left - right)))
            for left, right in zip(rk4, evaluator)
        )
        recurrence_errors.append({
            "case": case,
            "maximum_absolute_error": recurrence_error,
            "passed": recurrence_error < 1e-13,
        })
        rk4_errors.append({
            "case": case,
            "maximum_absolute_error": rk4_error,
            "rk4_substeps_per_year": 100,
            "passed": rk4_error < 1e-10,
        })
    return recurrence_errors, rk4_errors


def _determinism_check(oracle):
    world = oracle._world(oracle.DEVELOPMENT_SPECS[0])
    forcing = SHORT_ABRUPT_FORCING
    first = oracle._ClimateLaboratory(world)
    second = oracle._ClimateLaboratory(world)
    first_observation = first.observe(forcing)
    fresh_observation = second.observe(forcing)
    repeated_observation = first.observe(forcing)
    same_fresh = bool(
        np.array_equal(
            first_observation["surface_temperature_anomaly_k"],
            fresh_observation["surface_temperature_anomaly_k"],
        )
        and np.array_equal(
            first_observation["toa_imbalance_w_m2"],
            fresh_observation["toa_imbalance_w_m2"],
        )
    )
    distinct_repeat = bool(
        not np.array_equal(
            first_observation["surface_temperature_anomaly_k"],
            repeated_observation["surface_temperature_anomaly_k"],
        )
        and not np.array_equal(
            first_observation["toa_imbalance_w_m2"],
            repeated_observation["toa_imbalance_w_m2"],
        )
    )
    result = {
        "same_query_same_fresh_lab": same_fresh,
        "same_query_repeated_call_uses_distinct_noise": distinct_repeat,
        "per_call_budget_cost": int(first_observation["budget_cost"]),
        "two_call_budget_used": int(first.used),
    }
    result["passed"] = bool(
        same_fresh and distinct_repeat
        and result["per_call_budget_cost"] == 4
        and result["two_call_budget_used"] == oracle.EXPERIMENT_BUDGET_UNITS
    )
    return result


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(_always_abstain)
    classical = oracle.evaluate(_classical_policy(LONG_MULTISCALE_FORCING))
    short = oracle.evaluate(_classical_policy(SHORT_ABRUPT_FORCING))
    reference = oracle.evaluate(_ExactReferencePolicy(oracle))

    exact = _exact_checks(oracle)
    identifiability = []
    misspecified = []
    noise_label_blind = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        supported_noise = {
            (float(oracle.SURFACE_NOISE_STD_K),
             float(oracle.TOA_NOISE_STD_W_M2))
            for spec in specs if spec[1] == "in_library"
        }
        unsupported_noise = {
            (float(oracle.SURFACE_NOISE_STD_K),
             float(oracle.TOA_NOISE_STD_W_M2))
            for spec in specs if spec[1] != "in_library"
        }
        noise_label_blind.append({
            "split": split,
            "supported_noise_pairs": [list(value) for value in supported_noise],
            "unsupported_noise_pairs": [list(value) for value in unsupported_noise],
            "unsupported_is_subset_of_supported": bool(
                unsupported_noise.issubset(supported_noise)
            ),
            "passed": bool(unsupported_noise.issubset(supported_noise)),
        })
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            if world["kind"] == "in_library":
                identifiability.append(_identifiability_record(
                    oracle, world, split, index
                ))
            else:
                misspecified.append(_clean_fit_record(
                    oracle, world, split, index
                ))

    recurrence_checks, rk4_checks = _physics_checks(oracle)
    determinism = _determinism_check(oracle)
    difficulty_passed = bool(
        0.70 <= classical["combined_score"] <= 0.90
        and 0.80 <= classical["heldout_policy_score"] <= 0.99
        and classical["development_supported_claim_coverage"] == 1.0
        and classical["heldout_supported_claim_coverage"] == 1.0
        and classical["development_unsupported_refusal_rate"] == 1.0
        and classical["heldout_unsupported_refusal_rate"] == 1.0
        and classical["development_false_discovery_rate"] == 0.0
        and classical["heldout_false_discovery_rate"] == 0.0
        and classical["development_mean_budget_used"]
        == oracle.EXPERIMENT_BUDGET_UNITS
        and classical["heldout_mean_budget_used"]
        == oracle.EXPERIMENT_BUDGET_UNITS
        and short["development_mean_budget_used"] == 4.0
        and short["heldout_mean_budget_used"] == 4.0
        and short["combined_score"] <= 0.10
        and short["heldout_policy_score"] <= 0.10
        and classical["combined_score"] - short["combined_score"] >= 0.65
    )
    execution_passed = bool(
        baseline["valid"] == 1.0
        and baseline["combined_score"] == 0.0
        and baseline["heldout_policy_score"] == 0.0
        and classical["valid"] == 1.0
        and classical["heldout_feasibility_rate"] == 1.0
        and short["valid"] == 1.0
        and short["heldout_feasibility_rate"] == 1.0
        and reference["valid"] == 1.0
        and reference["heldout_feasibility_rate"] == 1.0
        and reference["combined_score"] == 1.0
        and reference["heldout_policy_score"] == 1.0
        and reference["robustness_score"] == 1.0
        and reference["heldout_robustness_score"] == 1.0
        and difficulty_passed
        and all(row["passed"] for row in exact)
        and all(row["passed"] for row in identifiability)
        and all(row["passed"] for row in misspecified)
        and all(row["passed"] for row in noise_label_blind)
        and all(row["passed"] for row in recurrence_checks)
        and all(row["passed"] for row in rk4_checks)
        and determinism["passed"]
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "SYNTHETIC_CLIMATE_RESPONSE_TASK_CALIBRATION_NOT_EARTH_SYSTEM_"
            "OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "task_dimensions": {
            "parameter_count": len(oracle.PARAMETER_NAMES),
            "development_world_count": len(oracle.DEVELOPMENT_SPECS),
            "heldout_world_count": len(oracle.HELDOUT_SPECS),
            "experiment_budget_units": oracle.EXPERIMENT_BUDGET_UNITS,
            "maximum_experiment_years": oracle.MAX_EXPERIMENT_YEARS,
            "surface_noise_std_k": oracle.SURFACE_NOISE_STD_K,
            "toa_noise_std_w_m2": oracle.TOA_NOISE_STD_W_M2,
        },
        "always_abstain_baseline": baseline,
        "truth_blind_long_multiscale_fit": classical,
        "underinformative_short_fit": short,
        "exact_reference": reference,
        "exact_parameter_or_refusal_checks": exact,
        "forcing_identifiability_checks": identifiability,
        "misspecified_resolvability_checks": misspecified,
        "noise_label_blind_checks": noise_label_blind,
        "physics_checks": {
            "independent_matrix_exponential_recurrence": recurrence_checks,
            "independent_rk4_integration": rk4_checks,
        },
        "determinism_and_budget_check": determinism,
        "difficulty_gate": {
            "classical_development_interval": [0.70, 0.90],
            "classical_heldout_interval": [0.80, 0.99],
            "maximum_short_design_score": 0.10,
            "minimum_long_minus_short_development_gap": 0.65,
            "required_supported_coverage": 1.0,
            "required_unsupported_refusal": 1.0,
            "maximum_false_discovery_rate": 0.0,
            "long_design_budget_units": oracle.EXPERIMENT_BUDGET_UNITS,
            "short_design_budget_units": 4,
            "minimum_misspecification_reduced_chi2_margin": (
                MINIMUM_MISSPECIFICATION_MARGIN
            ),
            "passed": difficulty_passed,
        },
        "limitations": [
            "The oracle is a five-parameter global-mean synthetic emulator, not a GCM, observational attribution system, or estimate of Earth's climate sensitivity.",
            "State-dependent feedback and the third ocean reservoir are deliberately strengthened so model inadequacy is resolvable within a 160-year benchmark experiment.",
            "Independent annual noise omits correlated internal variability, uncertain forcing histories, spatial dynamics, carbon-cycle feedback and paleoclimate constraints.",
            "Task calibration scores do not measure GPT-5.5, feedback causality, population capability or autonomous scientific discovery.",
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
