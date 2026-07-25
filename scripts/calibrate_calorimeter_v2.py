#!/usr/bin/env python3
"""Calibrate CalorimeterDesign-v2 equations, anchors and robustness tradeoffs."""

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
from scipy.integrate import quad
from scipy.optimize import differential_evolution
from scipy.special import gammaln
from scipy.stats import gamma as gamma_distribution


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/ParticlePhysics/CalorimeterDesign"
sys.path.insert(0, str(ROOT))

from frontier_science.evaluate import evaluate_candidate  # noqa: E402
from frontier_science.metric_visibility import search_visible_metrics  # noqa: E402
from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)
from frontier_science.registry import find_task  # noqa: E402


NOMINAL_SEED_BASE = 7100
ROBUST_SEED_BASE = 8100
POPULATION_MULTIPLIER = 9
MAXIMUM_ITERATIONS = 48
OPTIMIZER_TOLERANCE = 2.0e-7
REFERENCE_UTILITY_TOLERANCE = 2.0e-6


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location(
        "calorimeter_v2_calibration_oracle", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load CalorimeterDesign-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _independent_shape(energy_gev, problem):
    return 1.0 + float(problem["shower_profile_b"]) * (
        math.log(
            float(energy_gev) / float(problem["critical_energy_gev"])
        ) - 0.5
    )


def _independent_density(depth_x0, energy_gev, problem):
    depth = float(depth_x0)
    if depth <= 0.0:
        return 0.0
    shape = _independent_shape(energy_gev, problem)
    rate = float(problem["shower_profile_b"])
    return math.exp(
        shape * math.log(rate)
        + (shape - 1.0) * math.log(depth)
        - rate * depth
        - float(gammaln(shape))
    )


def _independent_cdf(depth_x0, energy_gev, problem):
    return float(gamma_distribution.cdf(
        float(depth_x0),
        a=_independent_shape(energy_gev, problem),
        scale=1.0 / float(problem["shower_profile_b"]),
    ))


def _independent_nominal_metrics(passive, active, problem):
    """Reimplement public nominal equations without oracle model helpers."""
    passive = np.asarray(passive, dtype=float)
    active = np.asarray(active, dtype=float)
    x0_passive = float(problem["radiation_length_pb_mm"])
    x0_active = float(problem["radiation_length_scintillator_mm"])

    def signal_and_containment(energy):
        depth = 0.0
        deposits = []
        for passive_mm, active_mm in zip(passive, active):
            depth += float(passive_mm) / x0_passive
            start = depth
            depth += float(active_mm) / x0_active
            end = depth
            deposits.append(
                _independent_cdf(end, energy, problem)
                - _independent_cdf(start, energy, problem)
            )
        containment = _independent_cdf(depth, energy, problem)
        return np.asarray(deposits, dtype=float), containment, depth

    calibration_deposits, _, _ = signal_and_containment(
        float(problem["calibration_energy_gev"])
    )
    calibration_signal = float(np.sum(calibration_deposits))
    rows = []
    for energy in problem["energies_gev"]:
        deposits, containment, total_depth = signal_and_containment(energy)
        signal = float(np.sum(deposits))
        effective_passive_x0 = float(np.sum(
            deposits * passive / x0_passive
        ) / np.sum(deposits))
        stochastic = float(problem["sampling_scale"]) * math.sqrt(
            effective_passive_x0 / signal
        )
        sampling = stochastic / math.sqrt(float(energy))
        photostatistics = 1.0 / math.sqrt(
            float(energy)
            * signal
            * float(problem["light_yield_pe_per_active_gev"])
        )
        electronics = (
            float(problem["electronics_noise_active_gev"])
            / (float(energy) * signal)
        )
        constant = float(problem["constant_term"])
        leakage = (
            float(problem["leakage_fluctuation_scale"])
            * (1.0 - containment)
        )
        resolution = math.sqrt(
            sampling**2
            + photostatistics**2
            + electronics**2
            + constant**2
            + leakage**2
        )
        rows.append({
            "energy_gev": float(energy),
            "signal_fraction": signal,
            "containment": containment,
            "total_depth_x0": total_depth,
            "effective_passive_thickness_x0": effective_passive_x0,
            "stochastic_coefficient": stochastic,
            "sampling_resolution": sampling,
            "photostatistics_resolution": photostatistics,
            "electronics_resolution": electronics,
            "constant_resolution": constant,
            "leakage_resolution": leakage,
            "resolution": resolution,
            "response_ratio": signal / calibration_signal,
        })
    resolutions = np.asarray([row["resolution"] for row in rows])
    response_error = np.asarray([row["response_ratio"] - 1.0 for row in rows])
    mean_resolution = float(np.sqrt(np.mean(resolutions**2)))
    linearity_rms = float(np.sqrt(np.mean(response_error**2)))
    maximum_nonlinearity = float(np.max(np.abs(response_error)))
    minimum_containment = float(min(row["containment"] for row in rows))
    loss = (
        0.62 * mean_resolution / 0.08
        + 0.18 * linearity_rms / 0.08
        + 0.08 * maximum_nonlinearity / 0.15
        + 0.12 * (1.0 - minimum_containment) / 0.08
    )
    return {
        "utility": math.exp(-loss),
        "loss": loss,
        "mean_resolution": mean_resolution,
        "linearity_rms": linearity_rms,
        "maximum_nonlinearity": maximum_nonlinearity,
        "minimum_containment": minimum_containment,
        "energy_metrics": rows,
    }


def _reference_quality(oracle, problem, option, parameters, robust):
    try:
        passive, active = oracle._family_design(
            problem, option, parameters
        )
        geometry = oracle._geometry_metrics(
            passive, active, problem, option
        )
        if not geometry["feasible"]:
            return 0.0
        nominal = oracle._metrics_for_design(
            passive, active, problem
        )["utility"]
        if not robust:
            return float(nominal)
        shifts = [
            oracle._shifted_option_metrics(
                passive, active, problem, option, shift
            )["utility"]
            for shift in oracle.SHIFT_SPECS
        ]
        return float(min(nominal, *shifts))
    except Exception:
        return 0.0


def _regenerate_reference(oracle, instance, instance_index, option, robust):
    problem = instance["problem"]
    seed = (
        (ROBUST_SEED_BASE if robust else NOMINAL_SEED_BASE)
        + instance_index * 10 + option
    )
    result = differential_evolution(
        lambda values: -_reference_quality(
            oracle, problem, option, values, robust
        ),
        oracle._family_parameter_bounds(problem, option),
        seed=seed,
        popsize=POPULATION_MULTIPLIER,
        maxiter=MAXIMUM_ITERATIONS,
        tol=OPTIMIZER_TOLERANCE,
        polish=True,
        workers=1,
        updating="immediate",
    )
    return {
        "seed": seed,
        "maximum_iterations": MAXIMUM_ITERATIONS,
        "population_multiplier": POPULATION_MULTIPLIER,
        "function_evaluations": int(result.nfev),
        "success": bool(result.success),
        "message": str(result.message),
        "parameters": [float(value) for value in result.x],
        "utility": float(-result.fun),
    }


def _physics_checks(oracle, instance):
    problem = instance["problem"]
    energies = tuple(map(float, problem["energies_gev"]))
    depths = (0.25, 2.0, 8.0, 16.0, 28.0, 45.0)
    maximum_cdf_quadrature_error = 0.0
    maximum_density_relative_error = 0.0
    for energy in energies:
        for depth in depths:
            integrated, _ = quad(
                lambda value: _independent_density(
                    value, energy, problem
                ),
                0.0,
                depth,
                epsabs=2.0e-13,
                epsrel=2.0e-13,
                limit=300,
            )
            oracle_cdf = float(oracle._shower_cdf(depth, energy))
            independent_cdf = _independent_cdf(depth, energy, problem)
            maximum_cdf_quadrature_error = max(
                maximum_cdf_quadrature_error,
                abs(integrated - oracle_cdf),
                abs(independent_cdf - oracle_cdf),
            )
            oracle_density = float(oracle._shower_density(depth, energy))
            independent_density = _independent_density(
                depth, energy, problem
            )
            maximum_density_relative_error = max(
                maximum_density_relative_error,
                abs(independent_density - oracle_density)
                / max(abs(oracle_density), 1.0e-15),
            )

    shower_maxima = [oracle._shower_maximum_x0(value) for value in energies]
    sorted_energy_maxima = [
        oracle._shower_maximum_x0(value) for value in sorted(energies)
    ]
    maximum_at_formula_error = 0.0
    for energy in energies:
        maximum = float(oracle._shower_maximum_x0(energy))
        epsilon = 1.0e-5
        left = float(oracle._shower_density(maximum - epsilon, energy))
        center = float(oracle._shower_density(maximum, energy))
        right = float(oracle._shower_density(maximum + epsilon, energy))
        maximum_at_formula_error = max(
            maximum_at_formula_error,
            max(left - center, right - center, 0.0),
        )

    passive, active = instance["nominal_reference_designs"][1]
    oracle_metrics = oracle._metrics_for_design(passive, active, problem)
    independent = _independent_nominal_metrics(passive, active, problem)
    scalar_keys = (
        "utility",
        "loss",
        "mean_resolution",
        "linearity_rms",
        "maximum_nonlinearity",
        "minimum_containment",
    )
    maximum_nominal_scalar_error = max(
        abs(float(oracle_metrics[key]) - float(independent[key]))
        for key in scalar_keys
    )
    maximum_energy_scalar_error = 0.0
    energy_keys = (
        "signal_fraction",
        "containment",
        "effective_passive_thickness_x0",
        "stochastic_coefficient",
        "sampling_resolution",
        "photostatistics_resolution",
        "electronics_resolution",
        "constant_resolution",
        "leakage_resolution",
        "resolution",
        "response_ratio",
    )
    for oracle_row, independent_row in zip(
        oracle_metrics["energy_metrics"], independent["energy_metrics"]
    ):
        maximum_energy_scalar_error = max(
            maximum_energy_scalar_error,
            *(
                abs(float(oracle_row[key]) - float(independent_row[key]))
                for key in energy_keys
            ),
        )

    containment_depths = np.linspace(2.0, 42.0, 81)
    containment_monotonic = all(
        np.all(np.diff(oracle._shower_cdf(
            containment_depths, energy
        )) >= -1.0e-14)
        for energy in energies
    )
    stochastic_identity_error = max(
        abs(
            float(row["sampling_resolution"]) * math.sqrt(
                float(row["energy_gev"])
            ) - float(row["stochastic_coefficient"])
        )
        for row in oracle_metrics["energy_metrics"]
    )
    total_passive_mm = float(np.sum(passive))
    lead_mass_identity_error = abs(
        oracle._lead_mass_kg_m2(passive)
        - total_passive_mm * 1.0e-3 * oracle.PB_DENSITY_KG_M3
    )
    starts, ends, total_depth = oracle._material_intervals(passive, active)
    radiation_length_identity_error = abs(
        total_depth
        - float(np.sum(passive)) / oracle.X0_PB_MM
        - float(np.sum(active)) / oracle.X0_SCINTILLATOR_MM
    )
    intervals_ordered = bool(
        np.all(ends > starts)
        and np.all(starts[1:] > ends[:-1])
    )
    passed = bool(
        maximum_cdf_quadrature_error <= 3.0e-11
        and maximum_density_relative_error <= 3.0e-12
        and all(np.diff(sorted_energy_maxima) > 0.0)
        and maximum_at_formula_error <= 1.0e-13
        and maximum_nominal_scalar_error <= 3.0e-12
        and maximum_energy_scalar_error <= 3.0e-12
        and containment_monotonic
        and stochastic_identity_error <= 3.0e-15
        and lead_mass_identity_error <= 3.0e-12
        and radiation_length_identity_error <= 3.0e-12
        and intervals_ordered
    )
    return {
        "name": instance["name"],
        "split": instance["split"],
        "energy_menu_gev": list(energies),
        "shower_maxima_x0": [float(value) for value in shower_maxima],
        "maximum_cdf_or_quadrature_error": maximum_cdf_quadrature_error,
        "maximum_density_relative_error": maximum_density_relative_error,
        "maximum_at_formula_error": maximum_at_formula_error,
        "maximum_independent_nominal_scalar_error": (
            maximum_nominal_scalar_error
        ),
        "maximum_independent_energy_scalar_error": (
            maximum_energy_scalar_error
        ),
        "containment_monotonic_with_depth": containment_monotonic,
        "stochastic_one_over_sqrt_energy_identity_error": (
            stochastic_identity_error
        ),
        "lead_mass_identity_error_kg_m2": lead_mass_identity_error,
        "radiation_length_identity_error": radiation_length_identity_error,
        "active_intervals_strictly_ordered": intervals_ordered,
        "passed": passed,
    }


def _reference_record(oracle, instance, instance_index):
    problem = instance["problem"]
    options = []
    for option in range(oracle.ARCHIVE_SIZE):
        nominal_parameters = instance["nominal_reference_parameters"][option]
        robust_parameters = instance["robust_reference_parameters"][option]
        declared_nominal = _reference_quality(
            oracle, problem, option, nominal_parameters, False
        )
        declared_robust = _reference_quality(
            oracle, problem, option, robust_parameters, True
        )
        recalibrated_nominal = _regenerate_reference(
            oracle, instance, instance_index, option, False
        )
        recalibrated_robust = _regenerate_reference(
            oracle, instance, instance_index, option, True
        )
        baseline = instance["baseline_options"][option]
        nominal_design = instance["nominal_reference_designs"][option]
        robust_design = instance["robust_reference_designs"][option]
        nominal_geometry = oracle._geometry_metrics(
            *nominal_design, problem, option
        )
        robust_geometry = oracle._geometry_metrics(
            *robust_design, problem, option
        )
        nominal_shift_geometry_rate = float(np.mean([
            oracle._shifted_option_metrics(
                *nominal_design, problem, option, shift
            )["geometry_feasible"]
            for shift in oracle.SHIFT_SPECS
        ]))
        robust_shift_geometry_rate = float(np.mean([
            oracle._shifted_option_metrics(
                *robust_design, problem, option, shift
            )["geometry_feasible"]
            for shift in oracle.SHIFT_SPECS
        ]))
        nominal_gap = recalibrated_nominal["utility"] - declared_nominal
        robust_gap = recalibrated_robust["utility"] - declared_robust
        passed = bool(
            declared_nominal
            > float(baseline["nominal"]["utility"]) + 1.0e-4
            and declared_robust
            > float(baseline["robust_utility"]) + 1.0e-4
            and nominal_geometry["feasible"]
            and robust_geometry["feasible"]
            and nominal_shift_geometry_rate < 1.0
            and robust_shift_geometry_rate == 1.0
            and nominal_gap <= REFERENCE_UTILITY_TOLERANCE
            and robust_gap <= REFERENCE_UTILITY_TOLERANCE
        )
        options.append({
            "option_index": option,
            "cost_cap": float(problem["option_cost_caps"][option]),
            "baseline_nominal_utility": float(
                baseline["nominal"]["utility"]
            ),
            "baseline_robust_utility": float(
                baseline["robust_utility"]
            ),
            "declared_nominal_parameters": list(nominal_parameters),
            "declared_nominal_utility": declared_nominal,
            "recalibrated_nominal": recalibrated_nominal,
            "recalibrated_minus_declared_nominal_utility": nominal_gap,
            "declared_robust_parameters": list(robust_parameters),
            "declared_robust_utility": declared_robust,
            "recalibrated_robust": recalibrated_robust,
            "recalibrated_minus_declared_robust_utility": robust_gap,
            "nominal_cost_utilization": float(
                nominal_geometry["cost_utilization"]
            ),
            "robust_cost_utilization": float(
                robust_geometry["cost_utilization"]
            ),
            "nominal_shift_geometry_feasibility_rate": (
                nominal_shift_geometry_rate
            ),
            "robust_shift_geometry_feasibility_rate": (
                robust_shift_geometry_rate
            ),
            "passed": passed,
        })
    return {
        "name": instance["name"],
        "split": instance["split"],
        "n_layers": int(problem["n_layers"]),
        "energy_menu_gev": list(problem["energies_gev"]),
        "options": options,
        "passed": all(row["passed"] for row in options),
    }


def _invalid_artifact_checks(oracle):
    def baseline(problem):
        return oracle._weak_baseline_design(problem)

    factories = {
        "nonfinite": lambda problem: {
            "passive_thicknesses_mm": np.full(
                (oracle.ARCHIVE_SIZE, problem["n_layers"]), np.nan
            ),
            "active_thicknesses_mm": np.full(
                (oracle.ARCHIVE_SIZE, problem["n_layers"]), 2.0
            ),
        },
        "wrong_shape": lambda problem: {
            "passive_thicknesses_mm": np.zeros(
                (oracle.ARCHIVE_SIZE, problem["n_layers"] - 1)
            ),
            "active_thicknesses_mm": np.zeros(
                (oracle.ARCHIVE_SIZE, problem["n_layers"] - 1)
            ),
        },
        "out_of_bounds": lambda problem: {
            **baseline(problem),
            "active_thicknesses_mm": np.full(
                (oracle.ARCHIVE_SIZE, problem["n_layers"]), 99.0
            ),
        },
        "duplicate_archive": lambda problem: {
            "passive_thicknesses_mm": np.repeat(
                baseline(problem)["passive_thicknesses_mm"][:1],
                oracle.ARCHIVE_SIZE,
                axis=0,
            ),
            "active_thicknesses_mm": np.repeat(
                baseline(problem)["active_thicknesses_mm"][:1],
                oracle.ARCHIVE_SIZE,
                axis=0,
            ),
        },
        "complex": lambda problem: {
            key: value.astype(complex) + 1.0e-3j
            for key, value in baseline(problem).items()
        },
        "unexpected_field": lambda problem: {
            **baseline(problem), "unexpected_diagnostic": 1.0,
        },
    }
    records = {}
    for name, factory in factories.items():
        metrics = oracle.evaluate(factory)
        records[name] = {
            "combined_score": metrics["combined_score"],
            "raw_score": metrics["raw_score"],
            "valid": metrics["valid"],
            "feasibility_rate": metrics["feasibility_rate"],
            "candidate_instance_valid_rate": metrics[
                "candidate_instance_valid_rate"
            ],
            "passed": bool(
                metrics["combined_score"] == 0.0
                and metrics["raw_score"] == 0.0
                and metrics["valid"] == 0.0
                and metrics["feasibility_rate"] == 0.0
                and metrics["candidate_instance_valid_rate"] == 0.0
            ),
        }
    return records


def _compact(metrics):
    keys = (
        "combined_score",
        "valid",
        "feasibility_rate",
        "raw_score",
        "robustness_score",
        "development_validation_gap",
        "heldout_policy_score",
        "heldout_robustness_score",
        "heldout_feasibility_rate",
        "development_mean_resolution",
        "heldout_mean_resolution",
        "development_linearity_rms",
        "heldout_linearity_rms",
        "development_minimum_containment",
        "heldout_minimum_containment",
        "development_mean_cost_utilization",
        "heldout_mean_cost_utilization",
        "development_shift_geometry_feasibility_rate",
        "heldout_shift_geometry_feasibility_rate",
        "candidate_instance_call_count",
        "candidate_instance_valid_rate",
        "error_message",
    )
    return {key: metrics[key] for key in keys if key in metrics}


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(oracle._weak_baseline_design)
    baseline_replay = oracle.evaluate(oracle._weak_baseline_design)
    nominal = oracle.evaluate(
        lambda problem: oracle.reference_policy(problem, robust=False)
    )
    robust = oracle.evaluate(
        lambda problem: oracle.reference_policy(problem, robust=True)
    )
    deterministic = bool(
        json.dumps(baseline, sort_keys=True, allow_nan=False)
        == json.dumps(baseline_replay, sort_keys=True, allow_nan=False)
    )
    physics = [
        _physics_checks(oracle, instance) for instance in oracle.INSTANCES
    ]
    references = [
        _reference_record(oracle, instance, index)
        for index, instance in enumerate(oracle.INSTANCES)
    ]
    invalid = _invalid_artifact_checks(oracle)

    spec = find_task(
        "ParticlePhysics/CalorimeterDesign", include_uncertified=True
    )
    secure_baseline = evaluate_candidate(
        spec, spec.initial_program_path, timeout_s=120
    )
    visible = search_visible_metrics(nominal)
    forbidden_visible = {
        "robustness_score",
        "heldout_policy_score",
        "development_mean_resolution",
        "development_linearity_rms",
        "per_instance",
    }
    public_problem_keys = set().union(*(
        set(instance["problem"]) for instance in oracle.INSTANCES
    ))
    forbidden_problem_keys = {
        "name",
        "split",
        "shift",
        "reference",
        "baseline_design",
        "nominal_reference_parameters",
        "robust_reference_parameters",
    }

    difficulty_passed = bool(
        baseline["combined_score"] == 0.0
        and baseline["robustness_score"] == 0.0
        and baseline["heldout_policy_score"] == 0.0
        and nominal["combined_score"] > 0.999999
        and nominal["heldout_policy_score"] > 0.999999
        and nominal["robustness_score"] == 0.0
        and nominal["heldout_robustness_score"] == 0.0
        and nominal["development_shift_geometry_feasibility_rate"] < 0.60
        and robust["combined_score"] > 0.70
        and robust["combined_score"] < 0.90
        and robust["heldout_policy_score"] > 0.65
        and robust["heldout_policy_score"] < 0.90
        and robust["robustness_score"] > 0.999999
        and robust["heldout_robustness_score"] > 0.999999
        and robust["development_shift_geometry_feasibility_rate"] == 1.0
        and robust["development_mean_cost_utilization"]
        < nominal["development_mean_cost_utilization"] - 0.015
        and nominal["development_mean_resolution"]
        < baseline["development_mean_resolution"] - 0.02
    )
    execution_passed = bool(
        oracle.CALORIMETER_V2
        and len(oracle.DEVELOPMENT_INSTANCES) == 4
        and len(oracle.HELDOUT_INSTANCES) == 2
        and len(oracle.SHIFT_SPECS) == 5
        and baseline["valid"] == 1.0
        and nominal["valid"] == 1.0
        and robust["valid"] == 1.0
        and deterministic
        and all(row["passed"] for row in physics)
        and all(row["passed"] for row in references)
        and all(row["passed"] for row in invalid.values())
        and secure_baseline["valid"] == 1.0
        and secure_baseline["combined_score"] == 0.0
        and secure_baseline["candidate_instance_call_count"] == 6
        and _compact(secure_baseline) == _compact(baseline)
        and forbidden_visible.isdisjoint(visible)
        and forbidden_problem_keys.isdisjoint(public_problem_keys)
        and difficulty_passed
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "TRANSPARENT_REDUCED_ORDER_SAMPLING_CALORIMETER_TASK_"
            "CALIBRATION_NOT_GEANT4_TEST_BEAM_OR_DETECTOR_VALIDATION"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
        },
        "task_dimensions": {
            "development_instance_count": len(
                oracle.DEVELOPMENT_INSTANCES
            ),
            "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
            "archive_size": oracle.ARCHIVE_SIZE,
            "shift_count": len(oracle.SHIFT_SPECS),
            "layer_count_range": [
                min(row["problem"]["n_layers"] for row in oracle.INSTANCES),
                max(row["problem"]["n_layers"] for row in oracle.INSTANCES),
            ],
            "incident_energy_range_gev": [
                min(min(row["problem"]["energies_gev"])
                    for row in oracle.INSTANCES),
                max(max(row["problem"]["energies_gev"])
                    for row in oracle.INSTANCES),
            ],
            "total_regime_option_count": (
                len(oracle.INSTANCES) * oracle.ARCHIVE_SIZE
            ),
        },
        "reference_method": {
            "family": (
                "bounded total absorber depth, exponential passive slope/"
                "curvature, active-budget fraction and Gaussian-plus-slope "
                "active allocation"
            ),
            "optimizer": "SciPy differential_evolution plus polish",
            "nominal_seed_base": NOMINAL_SEED_BASE,
            "robust_seed_base": ROBUST_SEED_BASE,
            "seed_formula": "base + 10 * instance_index + option_index",
            "population_multiplier": POPULATION_MULTIPLIER,
            "maximum_iterations": MAXIMUM_ITERATIONS,
            "tolerance": OPTIMIZER_TOLERANCE,
            "reference_utility_tolerance": REFERENCE_UTILITY_TOLERANCE,
            "global_optimality_claimed": False,
            "normalization_clips_better_feasible_candidates": True,
        },
        "weak_baseline": _compact(baseline),
        "secure_sandbox_baseline": _compact(secure_baseline),
        "nominal_reference_policy": _compact(nominal),
        "robust_reference_policy": _compact(robust),
        "independent_physics_checks": physics,
        "reference_regeneration": references,
        "invalid_artifact_checks": invalid,
        "determinism_check": {
            "exact_json_replay": deterministic,
            "passed": deterministic,
        },
        "metric_and_problem_sealing": {
            "visible_metric_keys": sorted(visible),
            "forbidden_visible_keys": sorted(forbidden_visible),
            "forbidden_visible_keys_absent": (
                forbidden_visible.isdisjoint(visible)
            ),
            "forbidden_problem_keys": sorted(forbidden_problem_keys),
            "forbidden_problem_keys_absent": (
                forbidden_problem_keys.isdisjoint(public_problem_keys)
            ),
        },
        "difficulty_gate": {
            "nominal_reference_is_unit_normalized": (
                nominal["combined_score"] > 0.999999
                and nominal["heldout_policy_score"] > 0.999999
            ),
            "nominal_reference_is_shift_brittle": (
                nominal["robustness_score"] == 0.0
                and nominal[
                    "development_shift_geometry_feasibility_rate"
                ] < 0.60
            ),
            "robust_reference_preserves_all_shift_envelopes": (
                robust["development_shift_geometry_feasibility_rate"] == 1.0
                and robust["heldout_shift_geometry_feasibility_rate"] == 1.0
            ),
            "robust_reference_nominal_tradeoff": {
                "development_score": robust["combined_score"],
                "heldout_score": robust["heldout_policy_score"],
                "development_cost_utilization_delta_from_nominal": (
                    robust["development_mean_cost_utilization"]
                    - nominal["development_mean_cost_utilization"]
                ),
            },
            "passed": difficulty_passed,
        },
        "limitations": [
            "The deterministic reduced-order longitudinal model is not GEANT4, a test-beam measurement or an engineering detector validation.",
            "The model omits lateral development, detailed interfaces, non-compensation, saturation, cross-talk, structural mechanics and event-level fluctuations beyond its explicit resolution terms.",
            "The nominal and robust references are reproducible members of a seven-parameter family, not certificates of global optimality or experimental state of the art.",
            "Repository-visible fixed regimes require future server-held detector families, independent detector-physics review and leakage/contamination auditing.",
            "Detector claims require event-level transport simulation, electronics simulation, manufacturing studies and test-beam replication.",
            "Task calibration does not measure GPT-5.5, feedback causality, population performance or autonomous scientific discovery.",
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
