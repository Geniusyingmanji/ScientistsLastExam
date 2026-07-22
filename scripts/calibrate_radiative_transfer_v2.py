#!/usr/bin/env python3
"""Calibrate RadiativeTransferFit-v2 with independent physics and fitting."""

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
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/AtmosphericScience/RadiativeTransferFit"
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


FIXED_NADIR_CHANNELS = np.asarray((12, 0, 23, 18, 21, 16, 11, 1, 20, 15, 10, 2))
FIXED_SLANT_CHANNELS = np.asarray((23, 22, 14, 18, 9, 13))
FIXED_NADIR_VIEW = 1.0
FIXED_SLANT_VIEW = 0.45
FIT_LOWER = np.asarray((-12.0, -12.0, -12.0, -12.0, 0.65))
FIT_UPPER = np.asarray((12.0, 12.0, 12.0, 12.0, 1.35))
NULL_PARAMETERS = np.asarray((0.0, 0.0, 0.0, 0.0, 1.0))
PARAMETER_SCALES = np.asarray((5.0, 5.0, 5.0, 5.0, 0.10))


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location(
        "radiative_transfer_v2_calibration_oracle", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load RadiativeTransferFit-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _always_abstain(public_model, observe, budget_units):
    del public_model, budget_units
    observe(np.asarray((0, 6, 12, 18)), 1.0)
    return {
        "temperature_anomaly_knots_K": np.zeros(4),
        "optical_depth_scale": 1.0,
        "support": np.zeros(5, dtype=int),
        "confidence": 0.0,
        "abstain": True,
    }


def _public_planck(temperature_K, wavenumber_cm):
    h = 6.62607015e-34
    c = 299792458.0
    k = 1.380649e-23
    sigma_m = 100.0 * np.asarray(wavenumber_cm, dtype=float)
    temperature = np.asarray(temperature_K, dtype=float)
    return (
        2.0 * h * c**2 * sigma_m**3
        / np.expm1(h * c * sigma_m / (k * temperature)) * 100.0
    )


def _public_forward(public_model, parameters, channels, views):
    """Independent implementation of the equations printed in Task.md."""
    values = np.asarray(parameters, dtype=float)
    indices = np.asarray(channels, dtype=int).ravel()
    view_array = np.broadcast_to(np.asarray(views, dtype=float), indices.shape)
    profile = (
        np.asarray(public_model["reference_temperature_K"], dtype=float)
        + np.asarray(public_model["temperature_basis"], dtype=float) @ values[:4]
    )
    wavenumbers = np.asarray(public_model["channel_wavenumbers_cm"], dtype=float)
    optical_depths = np.asarray(
        public_model["base_layer_optical_depths"], dtype=float
    )
    result = np.empty(len(indices))
    for row, (channel, view) in enumerate(zip(indices, view_array)):
        radiance = float(_public_planck(profile[0], wavenumbers[channel]))
        for temperature, optical_depth in zip(
            profile, values[4] * optical_depths[channel]
        ):
            transmittance = math.exp(-float(optical_depth) / float(view))
            emission = float(_public_planck(temperature, wavenumbers[channel]))
            radiance = radiance * transmittance + emission * (1.0 - transmittance)
        result[row] = radiance
    return result


def _fit_records(public_model, records):
    channels = np.concatenate([row["channel_indices"] for row in records])
    views = np.concatenate([
        np.full(len(row["channel_indices"]), row["view_cosine"])
        for row in records
    ])
    observed = np.concatenate([row["radiances"] for row in records])
    noise = np.concatenate([
        np.full(len(row["radiances"]), row["radiance_noise_std"])
        for row in records
    ])

    def residual(parameters):
        return (
            _public_forward(public_model, parameters, channels, views) - observed
        ) / noise

    fit = least_squares(
        residual, NULL_PARAMETERS, bounds=(FIT_LOWER, FIT_UPPER),
        max_nfev=600, xtol=1e-11, ftol=1e-11, gtol=1e-11,
    )
    chi2 = float(np.sum(residual(fit.x) ** 2))
    degrees_of_freedom = len(observed) - len(NULL_PARAMETERS)
    null_chi2 = float(np.sum(residual(NULL_PARAMETERS) ** 2))
    bic_gain = null_chi2 - (
        chi2 + len(NULL_PARAMETERS) * math.log(len(observed))
    )
    return {
        "parameters": fit.x,
        "reduced_chi2": chi2 / degrees_of_freedom,
        "chi2": chi2,
        "null_chi2": null_chi2,
        "bic_gain_over_null": bic_gain,
        "degrees_of_freedom": degrees_of_freedom,
        "jacobian_rank": int(np.linalg.matrix_rank(fit.jac)),
        "success": bool(fit.success),
        "n_function_evaluations": int(fit.nfev),
    }


def classical_discover_atmosphere(public_model, observe, budget_units):
    del budget_units
    records = [
        observe(FIXED_NADIR_CHANNELS, FIXED_NADIR_VIEW),
        observe(FIXED_SLANT_CHANNELS, FIXED_SLANT_VIEW),
    ]
    fit = _fit_records(public_model, records)
    abstain = bool(
        fit["reduced_chi2"] > 3.0 or fit["bic_gain_over_null"] < 5.0
    )
    parameters = fit["parameters"].copy()
    support = np.concatenate((
        np.abs(parameters[:4]) >= 0.75,
        (abs(parameters[4] - 1.0) >= 0.025,),
    ))
    if abstain:
        parameters = NULL_PARAMETERS.copy()
        support[:] = False
        confidence = 0.0
    else:
        parameters[:4] = np.where(support[:4], parameters[:4], 0.0)
        if not support[4]:
            parameters[4] = 1.0
        confidence = float(np.clip(1.0 - fit["reduced_chi2"] / 3.0, 0.0, 1.0))
    return {
        "temperature_anomaly_knots_K": parameters[:4],
        "optical_depth_scale": float(parameters[4]),
        "support": support.astype(int),
        "confidence": confidence,
        "abstain": abstain,
    }


def _fixed_design():
    channels = np.concatenate((FIXED_NADIR_CHANNELS, FIXED_SLANT_CHANNELS))
    views = np.concatenate((
        np.full(len(FIXED_NADIR_CHANNELS), FIXED_NADIR_VIEW),
        np.full(len(FIXED_SLANT_CHANNELS), FIXED_SLANT_VIEW),
    ))
    return channels, views


def _identifiability_record(oracle, world, split, index):
    channels, views = _fixed_design()
    parameters = world["parameters"]
    steps = np.asarray((0.05, 0.05, 0.05, 0.05, 0.001))
    jacobian = np.empty((len(channels), oracle.N_PARAMETERS))
    for column, step in enumerate(steps):
        upper = parameters.copy()
        lower = parameters.copy()
        upper[column] += step
        lower[column] -= step
        jacobian[:, column] = (
            oracle.forward_radiances(upper, channels, views)
            - oracle.forward_radiances(lower, channels, views)
        ) / (2.0 * step)
    scaled = jacobian * PARAMETER_SCALES[None, :] / world["noise"]
    singular = np.linalg.svd(scaled, compute_uv=False)
    rank = int(np.linalg.matrix_rank(scaled, tol=singular[0] * 1e-10))
    condition = float(singular[0] / singular[-1])
    return {
        "split": split,
        "world_index": int(index),
        "jacobian_shape": list(jacobian.shape),
        "jacobian_rank": rank,
        "condition_number": condition,
        "minimum_scaled_singular_value": float(singular[-1]),
        "passed": bool(rank == oracle.N_PARAMETERS and condition < 100.0),
    }


def _clean_fixed_records(oracle, world):
    records = []
    for channels, view in (
        (FIXED_NADIR_CHANNELS, FIXED_NADIR_VIEW),
        (FIXED_SLANT_CHANNELS, FIXED_SLANT_VIEW),
    ):
        radiances = oracle._world_radiances(
            world, channels, np.full(len(channels), view)
        )
        records.append({
            "channel_indices": channels.copy(),
            "view_cosine": float(view),
            "radiances": radiances,
            "radiance_noise_std": float(world["noise"]),
        })
    return records


def _misspecified_fit_record(oracle, world, split, index):
    public_model = {
        key: value.copy() if isinstance(value, np.ndarray) else value
        for key, value in oracle.PUBLIC_MODEL.items()
    }
    fit = _fit_records(public_model, _clean_fixed_records(oracle, world))
    return {
        "split": split,
        "world_index": int(index),
        "kind": world["kind"],
        "best_public_parameters": fit["parameters"].tolist(),
        "reduced_chi2": float(fit["reduced_chi2"]),
        "jacobian_rank": int(fit["jacobian_rank"]),
        "fit_success": bool(fit["success"]),
        "refusal_threshold": 3.0,
        "passed": bool(
            fit["success"] and fit["jacobian_rank"] == oracle.N_PARAMETERS
            and fit["reduced_chi2"] > 3.0
        ),
    }


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(_always_abstain)
    classical = oracle.evaluate(classical_discover_atmosphere)
    exact_checks = []
    identifiability = []
    misspecified = []
    noise_checks = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        supported_noise = {float(spec[2]) for spec in specs if spec[3] == "in_library"}
        unsupported_noise = {float(spec[2]) for spec in specs if spec[3] != "in_library"}
        noise_checks.append({
            "split": split,
            "supported_noise_std": sorted(supported_noise),
            "unsupported_noise_std": sorted(unsupported_noise),
            "unsupported_is_subset_of_supported": unsupported_noise.issubset(supported_noise),
            "passed": unsupported_noise.issubset(supported_noise),
        })
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            submission = oracle._reference_submission(world)
            parameters, support, _confidence, abstain = oracle._validate_submission(submission)
            mechanism = oracle._mechanism_metrics(world, parameters, support, abstain)
            prediction = oracle._radiance_prediction_score(world, parameters, False)
            shifted = oracle._radiance_prediction_score(world, parameters, True)
            exact_checks.append({
                "split": split,
                "world_index": int(index),
                "kind": world["kind"],
                "mechanism_score": float(mechanism["mechanism_score"]),
                "radiance_prediction_score": float(prediction),
                "radiance_view_shift_score": float(shifted),
                "passed": bool(
                    abs(mechanism["mechanism_score"] - 1.0) < 1e-12
                    and (
                        world["kind"] != "in_library"
                        or (abs(prediction - 1.0) < 1e-12 and abs(shifted - 1.0) < 1e-12)
                    )
                ),
            })
            if world["kind"] == "in_library":
                identifiability.append(_identifiability_record(
                    oracle, world, split, index
                ))
            elif world["kind"] in {"absorber", "cloud"}:
                misspecified.append(_misspecified_fit_record(
                    oracle, world, split, index
                ))

    # Independent equation and limiting-case checks.
    rng = np.random.default_rng(20260722)
    test_parameters = np.asarray((3.2, -2.1, 1.4, -0.8, 1.13))
    test_channels = rng.choice(oracle.N_CHANNELS, size=12, replace=False)
    test_views = rng.uniform(0.45, 1.0, size=12)
    independent = _public_forward(
        oracle.PUBLIC_MODEL, test_parameters, test_channels, test_views
    )
    evaluator = oracle.forward_radiances(
        test_parameters, test_channels, test_views
    )
    maximum_equation_error = float(np.max(np.abs(independent - evaluator)))
    isothermal_errors = []
    for temperature in (200.0, 250.0, 300.0):
        for channel in (0, 12, 23):
            for view in (0.45, 1.0):
                optical = oracle.BASE_LAYER_OPTICAL_DEPTHS[channel]
                expected = float(oracle.planck_radiance(
                    temperature, oracle.CHANNEL_WAVENUMBERS_CM[channel]
                ))
                radiance = expected
                for depth in optical:
                    transmittance = math.exp(-float(depth) / view)
                    radiance = radiance * transmittance + expected * (1.0 - transmittance)
                isothermal_errors.append(abs(radiance - expected))

    world = oracle._world(oracle.DEVELOPMENT_SPECS[0])
    first = oracle._SoundingLaboratory(world)
    second = oracle._SoundingLaboratory(world)
    deterministic_one = first.observe(np.asarray((0, 6, 12, 18)), 1.0)
    deterministic_two = second.observe(np.asarray((0, 6, 12, 18)), 1.0)
    repeated = first.observe(np.asarray((0, 6, 12, 18)), 1.0)
    determinism = {
        "same_query_same_fresh_lab": bool(np.array_equal(
            deterministic_one["radiances"], deterministic_two["radiances"]
        )),
        "same_query_repeated_call_uses_distinct_noise": bool(not np.array_equal(
            deterministic_one["radiances"], repeated["radiances"]
        )),
        "per_call_budget_cost": int(deterministic_one["budget_cost"]),
        "two_call_budget_units": int(first.used),
    }
    determinism["passed"] = bool(
        determinism["same_query_same_fresh_lab"]
        and determinism["same_query_repeated_call_uses_distinct_noise"]
        and determinism["per_call_budget_cost"] == 4
        and determinism["two_call_budget_units"] == 8
    )

    execution_passed = bool(
        baseline["valid"] == 1.0
        and baseline["combined_score"] == 0.0
        and baseline["robustness_score"] == 0.0
        and 0.30 <= classical["combined_score"] <= 0.80
        and 0.20 <= classical["robustness_score"] <= 0.75
        and classical["combined_score"] > classical["robustness_score"] + 0.05
        and classical["development_radiance_prediction_score"]
        > classical["combined_score"] + 0.15
        and classical["development_false_discovery_rate"] == 0.0
        and classical["heldout_false_discovery_rate"] == 0.0
        and all(row["passed"] for row in exact_checks)
        and all(row["passed"] for row in identifiability)
        and all(row["passed"] for row in misspecified)
        and all(row["passed"] for row in noise_checks)
        and maximum_equation_error < 1e-14
        and max(isothermal_errors) < 1e-14
        and determinism["passed"]
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": "SYNTHETIC_RADIATIVE_TRANSFER_TASK_CALIBRATION_NOT_SATELLITE_OR_AUTONOMOUS_DISCOVERY_EVIDENCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "task_dimensions": {
            "layer_count": oracle.N_LAYERS,
            "channel_count": oracle.N_CHANNELS,
            "parameter_count": oracle.N_PARAMETERS,
            "development_world_count": len(oracle.DEVELOPMENT_SPECS),
            "heldout_world_count": len(oracle.HELDOUT_SPECS),
            "measurement_budget_units": oracle.EXPERIMENT_BUDGET_UNITS,
        },
        "always_abstain_baseline": baseline,
        "truth_blind_classical_fit": classical,
        "exact_mechanism_or_refusal_checks": exact_checks,
        "sounding_identifiability_checks": identifiability,
        "misspecified_resolvability_checks": misspecified,
        "noise_label_blind_checks": noise_checks,
        "physics_checks": {
            "independent_public_equation": {
                "maximum_absolute_radiance_error": maximum_equation_error,
                "passed": maximum_equation_error < 1e-14,
            },
            "isothermal_recurrence": {
                "maximum_absolute_radiance_error": max(isothermal_errors),
                "passed": max(isothermal_errors) < 1e-14,
            },
            "temperature_basis_partition_of_unity_error": float(np.max(np.abs(
                np.sum(oracle.TEMPERATURE_BASIS, axis=1) - 1.0
            ))),
        },
        "determinism_and_budget_check": determinism,
        "difficulty_gate": {
            "classical_development_interval": [0.30, 0.80],
            "classical_heldout_interval": [0.20, 0.75],
            "minimum_development_minus_heldout_gap": 0.05,
            "minimum_prediction_minus_mechanism_gap": 0.15,
            "maximum_false_discovery_rate": 0.0,
            "passed": execution_passed,
        },
        "limitations": [
            "The oracle is a low-dimensional, non-scattering thermal-emission emulator with synthetic noise; it is not line-by-line or satellite validation.",
            "The public parameter family is intentionally small enough for controlled identifiability checks and does not represent the full atmospheric state.",
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
