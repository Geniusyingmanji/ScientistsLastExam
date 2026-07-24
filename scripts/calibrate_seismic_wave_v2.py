#!/usr/bin/env python3
"""Calibrate SeismicWaveInversion-v2 with independent physics and truth-blind fitting."""

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
from scipy.optimize import brentq, least_squares
from scipy.signal import find_peaks


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/WavePropagation/SeismicWaveInversion"
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


PUBLIC_TIME_STEP_S = 0.004
PUBLIC_TIME_S = np.arange(0.0, 2.0 + 0.5 * PUBLIC_TIME_STEP_S, PUBLIC_TIME_STEP_S)
PUBLIC_PARAMETER_SCALES = np.asarray((
    180.0, 220.0, 300.0, 70.0, 55.0, 40.0, 110.0, 75.0, 55.0,
))
PUBLIC_REFERENCE_EXPERIMENTS = (
    (
        np.full(8, 5000.0),
        np.linspace(120.0, 3000.0, 8),
        24.0,
    ),
    (
        np.linspace(500.0, 9500.0, 8),
        np.linspace(0.0, 700.0, 8),
        16.0,
    ),
)


def _public_reflection_travel_time(path_velocities, path_thicknesses, offsets_m):
    """Independent implementation of the exact Snell-ray equations in Task.md."""
    velocities = np.asarray(path_velocities, dtype=float).ravel()
    thicknesses = np.asarray(path_thicknesses, dtype=float).ravel()
    offsets = np.asarray(offsets_m, dtype=float).ravel()
    low = np.zeros(len(offsets), dtype=float)
    high = np.full(
        len(offsets), (1.0 - 1.0e-10) / float(np.max(velocities))
    )
    target = 0.5 * offsets
    for _ in range(64):
        ray_parameter = 0.5 * (low + high)
        pv = ray_parameter[:, None] * velocities[None, :]
        cosine = np.sqrt(np.maximum(1.0 - pv * pv, 1.0e-18))
        half_offset = np.sum(
            thicknesses[None, :] * pv / cosine, axis=1
        )
        move_right = half_offset < target
        low = np.where(move_right, ray_parameter, low)
        high = np.where(move_right, high, ray_parameter)
    ray_parameter = 0.5 * (low + high)
    pv = ray_parameter[:, None] * velocities[None, :]
    cosine = np.sqrt(np.maximum(1.0 - pv * pv, 1.0e-18))
    return 2.0 * np.sum(
        thicknesses[None, :] / (velocities[None, :] * cosine), axis=1
    )


def _public_local_thicknesses(parameters, midpoints_m):
    parameters = np.asarray(parameters, dtype=float).ravel()
    coordinate = (np.asarray(midpoints_m, dtype=float).ravel() - 5000.0) / 5000.0
    return np.column_stack((
        parameters[3] + parameters[4] * coordinate + parameters[5] * coordinate**2,
        parameters[6] + parameters[7] * coordinate + parameters[8] * coordinate**2,
    ))


def _public_synthesize(parameters, midpoints_m, offsets_m, peak_frequency_hz):
    """Independent public layered-reflection model; no evaluator import is used."""
    parameters = np.asarray(parameters, dtype=float).ravel()
    midpoints = np.asarray(midpoints_m, dtype=float).ravel()
    offsets = np.asarray(offsets_m, dtype=float).ravel()
    if parameters.shape != (9,) or midpoints.shape != offsets.shape:
        raise ValueError("invalid public layered-model inputs")
    velocities = parameters[:3]
    density = 310.0 * velocities**0.25
    impedance = density * velocities
    reflection = (impedance[1:] - impedance[:-1]) / (
        impedance[1:] + impedance[:-1]
    )
    thicknesses = _public_local_thicknesses(parameters, midpoints)
    traces = np.zeros((len(offsets), len(PUBLIC_TIME_S)))
    for row, (local_h, offset) in enumerate(zip(thicknesses, offsets)):
        transmission = 1.0
        for interface in range(2):
            arrival = _public_reflection_travel_time(
                velocities[:interface + 1], local_h[:interface + 1],
                np.asarray((offset,)),
            )[0]
            phase = np.pi * float(peak_frequency_hz) * (PUBLIC_TIME_S - arrival)
            squared = phase * phase
            traces[row] += (
                transmission * reflection[interface]
                * (1.0 - 2.0 * squared) * np.exp(-squared)
            )
            transmission *= 1.0 - reflection[interface] ** 2
    return traces


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location(
        "seismic_wave_v2_calibration_oracle", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load SeismicWaveInversion-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _always_abstain(
    midpoint_bounds, offset_bounds, frequency_bounds, parameter_names,
    parameter_bounds, acquire, budget_units,
):
    del frequency_bounds, parameter_names, parameter_bounds, budget_units
    midpoint = 0.5 * (midpoint_bounds[0] + midpoint_bounds[1])
    acquire(
        np.full(4, midpoint),
        np.linspace(offset_bounds[0], min(600.0, offset_bounds[1]), 4),
        12.0,
    )
    return {
        "parameters": np.zeros(9), "confidence": 0.0, "abstain": True,
    }


def _nmo_initialization(record):
    traces = np.asarray(record["traces"], dtype=float)
    times = np.asarray(record["time_s"], dtype=float)
    offsets = np.asarray(record["offsets_m"], dtype=float)
    noise = float(record["noise_std"])
    peaks, properties = find_peaks(
        traces[0], height=8.0 * noise, prominence=8.0 * noise, distance=25
    )
    if len(peaks) < 2:
        return None, {"detected_event_count": int(len(peaks))}
    strongest = np.argsort(properties["prominences"])[::-1][:2]
    picks = np.sort(times[peaks[strongest]])
    curves = []
    for pick in picks:
        best = None
        for t0 in np.linspace(max(0.05, pick - 0.07), pick + 0.008, 80):
            for velocity in np.linspace(1400.0, 4800.0, 171):
                predicted_time = np.sqrt(t0 * t0 + (offsets / velocity) ** 2)
                indices = np.clip(
                    np.rint(predicted_time / PUBLIC_TIME_STEP_S).astype(int),
                    0, len(times) - 1,
                )
                amplitudes = np.asarray([
                    np.max(traces[row, max(0, index - 1):min(len(times), index + 2)])
                    for row, index in enumerate(indices)
                ])
                score = float(np.sum(amplitudes))
                if best is None or score > best[0]:
                    best = (score, float(t0), float(velocity))
        curves.append(best)
    curves.sort(key=lambda row: row[1])
    _score_one, t1, v1 = curves[0]
    _score_two, t2, rms_velocity = curves[1]
    denominator = t2 - t1
    interval_two_squared = (
        rms_velocity**2 * t2 - v1**2 * t1
    ) / denominator
    if denominator <= 0.0 or interval_two_squared <= 0.0:
        return None, {
            "detected_event_count": int(len(peaks)),
            "picked_zero_offset_times_s": picks.tolist(),
            "reason": "invalid Dix interval-velocity initialization",
        }
    v2 = math.sqrt(interval_two_squared)
    initial = np.asarray((
        v1, v2, max(v2 + 300.0, 3800.0),
        0.5 * t1 * v1, 0.0, 0.0,
        0.5 * denominator * v2, 0.0, 0.0,
    ))
    return initial, {
        "detected_event_count": int(len(peaks)),
        "picked_zero_offset_times_s": picks.tolist(),
        "nmo_curve_velocities_m_s": [v1, rms_velocity],
        "initial_parameters": initial.tolist(),
    }


def _fit_public_model(records, parameter_bounds):
    initial, diagnostics = _nmo_initialization(records[0])
    if initial is None:
        return None, None, diagnostics
    noise = float(records[-1]["noise_std"])
    core_indices = np.asarray((0, 1, 2, 3, 6))
    lateral_indices = np.asarray((4, 5, 7, 8))
    center = records[0]
    center_observed = np.asarray(center["traces"]).ravel()

    def pack_core(core_parameters):
        parameters = np.zeros(9)
        parameters[core_indices] = core_parameters
        return parameters

    def center_residual(core_parameters):
        predicted = _public_synthesize(
            pack_core(core_parameters), center["midpoints_m"],
            center["offsets_m"], center["peak_frequency_hz"]
        ).ravel()
        return (predicted - center_observed) / noise

    best_core = None
    third_velocity_starts = (
        max(initial[1] + 150.0, 2600.0),
        max(initial[1] + 500.0, 3400.0),
        max(initial[1] + 1000.0, 4400.0),
        4750.0,
    )
    for third_velocity in third_velocity_starts:
        start = initial[core_indices].copy()
        start[2] = min(4790.0, third_velocity)
        fit = least_squares(
            center_residual, start,
            bounds=(
                parameter_bounds[core_indices, 0],
                parameter_bounds[core_indices, 1],
            ),
            max_nfev=100, x_scale=PUBLIC_PARAMETER_SCALES[core_indices],
            ftol=2.0e-7, xtol=2.0e-7, gtol=2.0e-7,
        )
        reduced_chi_squared = float(np.mean(center_residual(fit.x) ** 2))
        if best_core is None or reduced_chi_squared < best_core[0]:
            best_core = (
                reduced_chi_squared, fit.x.copy(), int(fit.nfev)
            )

    base = pack_core(best_core[1])
    if best_core[0] > 4.0:
        diagnostics.update({
            "third_velocity_starts_m_s": list(third_velocity_starts),
            "core_reduced_chi_squared": best_core[0],
            "reduced_chi_squared": best_core[0],
            "fitted_parameters": base.tolist(),
            "core_optimizer_evaluations": best_core[2],
            "model_check_rejected_before_lateral_fit": True,
        })
        return base, best_core[0], diagnostics

    lateral = records[1]
    picked_thicknesses = []
    for midpoint, offset, trace in zip(
        lateral["midpoints_m"], lateral["offsets_m"], lateral["traces"]
    ):
        peaks, properties = find_peaks(
            trace, height=5.0 * noise, prominence=5.0 * noise, distance=20
        )
        if len(peaks) < 2:
            diagnostics.update({
                "core_reduced_chi_squared": best_core[0],
                "reason": "fewer than two lateral reflection events",
            })
            return None, None, diagnostics
        strongest = np.argsort(properties["prominences"])[::-1][:2]
        t1, t2 = np.sort(lateral["time_s"][peaks[strongest]])
        radicand = (base[0] * t1) ** 2 - float(offset) ** 2
        if radicand <= 0.0:
            diagnostics.update({
                "core_reduced_chi_squared": best_core[0],
                "reason": "nonphysical first-reflector event",
            })
            return None, None, diagnostics
        h1 = 0.5 * math.sqrt(radicand)
        try:
            h2 = brentq(
                lambda value: _public_reflection_travel_time(
                    base[:2], np.asarray((h1, value)),
                    np.asarray((float(offset),)),
                )[0] - t2,
                100.0, 1300.0,
            )
        except ValueError:
            diagnostics.update({
                "core_reduced_chi_squared": best_core[0],
                "reason": "nonphysical second-reflector event",
            })
            return None, None, diagnostics
        picked_thicknesses.append((float(midpoint), h1, h2))

    picked = np.asarray(picked_thicknesses)
    normalized_midpoint = (picked[:, 0] - 5000.0) / 5000.0
    design = np.column_stack((
        np.ones(len(picked)), normalized_midpoint, normalized_midpoint**2
    ))
    first_coefficients = np.linalg.lstsq(
        design, picked[:, 1], rcond=None
    )[0]
    second_coefficients = np.linalg.lstsq(
        design, picked[:, 2], rcond=None
    )[0]
    parameters = base.copy()
    parameters[[3, 4, 5]] = first_coefficients
    parameters[[6, 7, 8]] = second_coefficients

    observed = np.concatenate([
        np.asarray(record["traces"]).ravel() for record in records
    ])
    predicted = np.concatenate([
        _public_synthesize(
            parameters, record["midpoints_m"], record["offsets_m"],
            record["peak_frequency_hz"]
        ).ravel()
        for record in records
    ])
    reduced_chi_squared = float(np.mean(((predicted - observed) / noise) ** 2))
    diagnostics.update({
        "third_velocity_starts_m_s": list(third_velocity_starts),
        "core_reduced_chi_squared": best_core[0],
        "reduced_chi_squared": reduced_chi_squared,
        "fitted_parameters": parameters.tolist(),
        "core_optimizer_evaluations": best_core[2],
        "lateral_event_thicknesses": picked.tolist(),
    })
    return parameters, reduced_chi_squared, diagnostics


def truth_blind_discover(
    midpoint_bounds, offset_bounds, frequency_bounds, parameter_names,
    parameter_bounds, acquire, budget_units,
):
    """NMO/Dix initialization plus waveform fit; no hidden seed or label is used."""
    del midpoint_bounds, offset_bounds, frequency_bounds, parameter_names
    del budget_units
    records = [
        acquire(midpoints, offsets, frequency)
        for midpoints, offsets, frequency in PUBLIC_REFERENCE_EXPERIMENTS
    ]
    parameters, reduced_chi_squared, _diagnostics = _fit_public_model(
        records, np.asarray(parameter_bounds, dtype=float)
    )
    abstain = bool(
        parameters is None
        or reduced_chi_squared is None
        or reduced_chi_squared > 4.0
    )
    return {
        "parameters": np.zeros(9) if abstain else parameters,
        "confidence": (
            0.0 if abstain
            else float(np.clip(1.0 - reduced_chi_squared / 4.0, 0.0, 1.0))
        ),
        "abstain": abstain,
    }


class _ReferencePolicy:
    def __init__(self, oracle):
        self.oracle = oracle
        self.index = 0

    def __call__(
        self, midpoint_bounds, offset_bounds, frequency_bounds,
        parameter_names, parameter_bounds, acquire, budget_units,
    ):
        del midpoint_bounds, offset_bounds, frequency_bounds, parameter_names
        del parameter_bounds
        del budget_units
        for midpoints, offsets, frequency in self.oracle.REFERENCE_EXPERIMENTS:
            acquire(midpoints, offsets, frequency)
        specs = list(self.oracle.DEVELOPMENT_SPECS) + list(
            self.oracle.HELDOUT_SPECS
        )
        world = self.oracle._world(specs[self.index])
        self.index += 1
        return self.oracle._reference_submission(world)


def _independent_normal_incidence(parameters, peak_frequency_hz, oracle):
    velocities = np.asarray(parameters[:3], dtype=float)
    thicknesses = np.asarray((parameters[3], parameters[6]), dtype=float)
    density = 310.0 * velocities**0.25
    impedance = density * velocities
    reflection = (impedance[1:] - impedance[:-1]) / (
        impedance[1:] + impedance[:-1]
    )
    arrival = np.asarray((
        2.0 * thicknesses[0] / velocities[0],
        2.0 * (
            thicknesses[0] / velocities[0]
            + thicknesses[1] / velocities[1]
        ),
    ))
    transmission = np.asarray((1.0, 1.0 - reflection[0] ** 2))
    traces = np.zeros((1, len(oracle.TIME_S)))
    for index in range(2):
        phase = np.pi * peak_frequency_hz * (
            oracle.TIME_S - arrival[index]
        )
        squared = phase * phase
        traces[0] += (
            transmission[index] * reflection[index]
            * (1.0 - 2.0 * squared) * np.exp(-squared)
        )
    return traces


def _world_fit_diagnostics(oracle):
    rows = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            laboratory = oracle._SeismicLaboratory(world)
            records = [
                laboratory.acquire(midpoints, offsets, frequency)
                for midpoints, offsets, frequency in oracle.REFERENCE_EXPERIMENTS
            ]
            parameters, reduced_chi_squared, diagnostics = _fit_public_model(
                records, oracle.PARAMETER_BOUNDS
            )
            rows.append({
                "split": split,
                "world_index": index,
                "kind": world["kind"],
                "claim_supported": bool(
                    parameters is not None
                    and reduced_chi_squared is not None
                    and reduced_chi_squared <= 4.0
                ),
                "reduced_chi_squared": reduced_chi_squared,
                "diagnostics": diagnostics,
                "mechanism_quality": (
                    oracle._mechanism_quality(
                        parameters, world["parameters"]
                    )
                    if parameters is not None and world["kind"] == "in_library"
                    else None
                ),
                "prediction_quality": (
                    oracle._prediction_quality(world, parameters, False)[0]
                    if parameters is not None else None
                ),
            })
    return rows


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(_always_abstain)
    reference = oracle.evaluate(_ReferencePolicy(oracle))
    classical = oracle.evaluate(truth_blind_discover)
    fit_diagnostics = _world_fit_diagnostics(oracle)

    independent_equation_checks = []
    identifiability_checks = []
    narrow_information_checks = []
    misspecified_checks = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            if world["kind"] == "in_library":
                check_midpoints = np.asarray((350.0, 3100.0, 6800.0, 9650.0))
                check_offsets = np.asarray((0.0, 430.0, 1370.0, 2860.0))
                production = oracle.synthesize_public(
                    world["parameters"], check_midpoints,
                    check_offsets, 17.0
                )
                independent = _public_synthesize(
                    world["parameters"], check_midpoints,
                    check_offsets, 17.0
                )
                maximum_error = float(np.max(np.abs(
                    production - independent
                )))
                normal_incidence = oracle.synthesize_public(
                    world["parameters"], np.asarray((5000.0,)),
                    np.asarray((0.0,)), 15.0
                )
                analytic_normal_incidence = _independent_normal_incidence(
                    world["parameters"], 15.0, oracle
                )
                normal_incidence_error = float(np.max(np.abs(
                    normal_incidence - analytic_normal_incidence
                )))
                independent_equation_checks.append({
                    "split": split, "world_index": index,
                    "maximum_absolute_error": maximum_error,
                    "normal_incidence_maximum_absolute_error": (
                        normal_incidence_error
                    ),
                    "passed": (
                        maximum_error < 2.0e-12
                        and normal_incidence_error < 2.0e-12
                    ),
                })
                reference_records = [
                    {
                        "midpoints_m": midpoints,
                        "offsets_m": offsets,
                        "peak_frequency_hz": frequency,
                    }
                    for midpoints, offsets, frequency in oracle.REFERENCE_EXPERIMENTS
                ]
                information = oracle._experiment_information(
                    world, reference_records
                )
                identifiability_checks.append({
                    "split": split, "world_index": index, **information,
                    "passed": (
                        information["jacobian_rank"] == 9
                        and information["condition_number"] is not None
                        and information["condition_number"] < 250.0
                        and information["information_score"] > 0.999
                    ),
                })
                narrow_records = [{
                    "midpoints_m": np.full(4, 5000.0),
                    "offsets_m": np.linspace(0.0, 600.0, 4),
                    "peak_frequency_hz": 12.0,
                }]
                narrow = oracle._experiment_information(world, narrow_records)
                narrow_information_checks.append({
                    "split": split, "world_index": index,
                    "reference_information_score": information[
                        "information_score"
                    ],
                    "narrow_information_score": narrow["information_score"],
                    "narrow_rank": narrow["jacobian_rank"],
                    "narrow_condition_number": narrow["condition_number"],
                    "passed": (
                        narrow["jacobian_rank"] < 9
                        and narrow["information_score"] == 0.0
                    ),
                })
            elif world["kind"] == "misspecified":
                matching = next(
                    row for row in fit_diagnostics
                    if row["split"] == split and row["world_index"] == index
                )
                misspecified_checks.append({
                    "split": split, "world_index": index,
                    "best_public_model_reduced_chi_squared": matching[
                        "reduced_chi_squared"
                    ],
                    "passed": matching["reduced_chi_squared"] > 10.0,
                })

    execution_passed = bool(
        oracle.SEISMIC_WAVE_INVERSION_V2
        and baseline["valid"] == 1.0
        and baseline["combined_score"] == 0.0
        and reference["valid"] == 1.0
        and all(abs(reference[key] - 1.0) < 1.0e-12 for key in (
            "combined_score", "mechanism_score", "robustness_score",
            "heldout_policy_score", "heldout_mechanism_score",
            "heldout_robustness_score",
        ))
        and classical["valid"] == 1.0
        and classical["combined_score"] > 0.90
        and classical["heldout_policy_score"] > 0.90
        and classical["development_false_discovery_rate"] == 0.0
        and classical["heldout_false_discovery_rate"] == 0.0
        and all(row["passed"] for row in independent_equation_checks)
        and all(row["passed"] for row in identifiability_checks)
        and all(row["passed"] for row in narrow_information_checks)
        and all(row["passed"] for row in misspecified_checks)
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "SEISMIC_WAVE_V2_SYNTHETIC_LAYERED_ACTIVE_INVERSION_"
            "CALIBRATION_NOT_FIELD_OR_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "task_dimensions": {
            "development_worlds": len(oracle.DEVELOPMENT_SPECS),
            "heldout_worlds": len(oracle.HELDOUT_SPECS),
            "parameters": list(oracle.PARAMETER_NAMES),
            "acquisition_budget_units": oracle.ACQUISITION_BUDGET_UNITS,
            "trace_shape_per_offset": len(oracle.TIME_S),
        },
        "weak_baseline": baseline,
        "reference_policy": reference,
        "truth_blind_nmo_dix_waveform_policy": classical,
        "truth_blind_fit_diagnostics": fit_diagnostics,
        "independent_equation_checks": independent_equation_checks,
        "identifiability_checks": identifiability_checks,
        "narrow_information_checks": narrow_information_checks,
        "misspecified_resolvability_checks": misspecified_checks,
        "limitations": [
            "All worlds are controlled synthetic horizontal acoustic layers with primary reflections only.",
            "The oracle omits elastic conversion, attenuation, anisotropy, multiples, source uncertainty, topography and field noise.",
            "Public deterministic seeds aid reproducibility and require a future server-held procedural split.",
            "The truth-blind policy is a calibration witness, not a global optimum or a model-population result.",
            "No result supports field-geology validation or autonomous scientific discovery.",
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
