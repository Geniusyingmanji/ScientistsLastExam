#!/usr/bin/env python3
"""Calibrate Antenna-v2 with an independently enumerated domain-policy grid."""

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
TASK = ROOT / "benchmarks/Physics/AntennaArraySynthesis"
sys.path.insert(0, str(ROOT))

from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402


BETA_GRID = np.linspace(0.0, 6.0, 25)
ALPHA_GRID = np.concatenate((np.asarray((0.0,)), np.logspace(-3.0, 4.0, 29)))


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("antenna_v2_calibration_oracle", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load Antenna-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _steering(positions, angles, frequency_scale=1.0, gains=None):
    positions = np.asarray(positions, dtype=float)
    angles = np.asarray(angles, dtype=float)
    matrix = np.exp(
        1j * 2.0 * math.pi * np.outer(
            np.sin(np.deg2rad(angles)), positions * float(frequency_scale)
        )
    )
    if gains is not None:
        matrix = matrix * np.asarray(gains, dtype=complex)[None, :]
    return matrix


def _independent_scenarios(instance):
    positions = np.asarray(instance["positions_lambda"], dtype=float)
    count = len(positions)
    indices = np.arange(count, dtype=float)
    seed = float(instance["seed"])
    rows = [
        ("frequency_low", 0.96, positions, np.ones(count, dtype=complex)),
        ("frequency_high", 1.04, positions, np.ones(count, dtype=complex)),
    ]
    position_error = 0.008 * np.sin((indices + 1.0) * (0.13 * seed + 0.70))
    rows.append((
        "position_error", 1.0, positions + position_error,
        np.ones(count, dtype=complex),
    ))
    amplitude = 1.0 + 0.025 * np.cos((indices + 1.0) * (0.17 * seed + 0.50))
    phase = np.deg2rad(2.0) * np.sin((indices + 1.0) * (0.11 * seed + 0.90))
    rows.append(("gain_phase_error", 1.0, positions, amplitude * np.exp(1j * phase)))
    for failed in range(count):
        gains = np.ones(count, dtype=complex)
        gains[failed] = 0.0
        rows.append(("element_failure_%d" % failed, 1.0, positions, gains))
    return tuple(rows)


def _independent_weights(instance, beta, alpha):
    positions = instance["positions_lambda"]
    target = _steering(positions, [instance["steering_angle_deg"]])[0]
    initial = np.kaiser(len(positions), float(beta)) * np.conj(target)
    initial = initial / (target @ initial)
    null_matrix = _steering(positions, instance["null_grid_deg"])
    normal = (
        np.eye(len(positions), dtype=complex)
        + float(alpha) * (null_matrix.conj().T @ null_matrix) / len(null_matrix)
    )
    inverse = np.linalg.inv(normal)
    base = inverse @ initial
    direction = inverse @ np.conj(target)
    multiplier = (1.0 - target @ base) / (target @ direction)
    weights = base + multiplier * direction
    return np.asarray(weights / (target @ weights), dtype=complex)


def _quality(instance, weights, scenario=None):
    if scenario is None:
        name = "nominal"
        scale = 1.0
        positions = instance["positions_lambda"]
        gains = np.ones(len(positions), dtype=complex)
    else:
        name, scale, positions, gains = scenario
    target = _steering(
        positions, [instance["steering_angle_deg"]], scale, gains
    )[0]
    target_gain = float(abs(target @ weights))
    denominator = max(target_gain, 1.0e-15)
    sidelobes = abs(_steering(
        positions, instance["sidelobe_angles_deg"], scale, gains
    ) @ weights) / denominator
    nulls = abs(_steering(
        positions, instance["null_grid_deg"], scale, gains
    ) @ weights) / denominator
    composite = max(
        float(np.max(sidelobes)),
        float(instance["null_weight"]) * float(np.max(nulls)),
    )
    suppression = -20.0 * math.log10(max(composite, 1.0e-15))
    gain_penalty = min(
        0.0, 20.0 * math.log10(max(target_gain, 1.0e-15) / 0.80)
    )
    return {
        "name": name,
        "quality_db": float(suppression + gain_penalty),
        "suppression_db": float(suppression),
        "target_gain": target_gain,
    }


def _enumerate_grid(instance):
    records = []
    scenarios = _independent_scenarios(instance)
    for beta in BETA_GRID:
        for alpha in ALPHA_GRID:
            weights = _independent_weights(instance, beta, alpha)
            l2_norm = float(np.linalg.norm(weights))
            max_amplitude = float(np.max(abs(weights)))
            feasible = bool(
                l2_norm <= float(instance["l2_norm_limit"]) + 1.0e-10
                and max_amplitude <= float(instance["element_amplitude_limit"]) + 1.0e-10
            )
            nominal = _quality(instance, weights)
            shifted = [_quality(instance, weights, row) for row in scenarios]
            records.append({
                "beta": float(beta),
                "alpha": float(alpha),
                "feasible": feasible,
                "nominal_quality_db": nominal["quality_db"],
                "worst_shifted_quality_db": min(
                    row["quality_db"] for row in shifted
                ),
                "minimum_shifted_target_gain": min(
                    row["target_gain"] for row in shifted
                ),
                "l2_norm": l2_norm,
                "max_element_amplitude": max_amplitude,
                "weights": weights,
            })
    feasible = [row for row in records if row["feasible"]]
    return (
        max(feasible, key=lambda row: row["nominal_quality_db"]),
        max(feasible, key=lambda row: row["worst_shifted_quality_db"]),
        len(records),
        len(feasible),
    )


def _policy_for(oracle, key):
    def design_array(positions, steering, *_args):
        for instance in oracle.INSTANCES:
            if (
                np.array_equal(instance["positions_lambda"], positions)
                and float(instance["steering_angle_deg"]) == float(steering)
            ):
                return instance[key].copy()
        raise ValueError("unknown public array instance")
    return design_array


def _reference_checks(oracle):
    checks = []
    for instance in oracle.INSTANCES:
        nominal_grid, robust_grid, grid_count, feasible_count = _enumerate_grid(instance)
        declared_nominal = instance["nominal_reference_weights"]
        declared_robust = instance["robust_reference_weights"]
        nominal_independent = _quality(instance, declared_nominal)
        robust_independent = [
            _quality(instance, declared_robust, scenario)
            for scenario in _independent_scenarios(instance)
        ]
        nominal_oracle = oracle._pattern_metrics(instance, declared_nominal)
        robust_oracle = [
            oracle._pattern_metrics(instance, declared_robust, scenario)
            for scenario in instance["shift_scenarios"]
        ]

        translated = dict(instance)
        translated["positions_lambda"] = instance["positions_lambda"] + 2.731
        original_pattern = abs(oracle._steering_matrix(
            instance["positions_lambda"], instance["sidelobe_angles_deg"]
        ) @ declared_nominal)
        translated_pattern = abs(oracle._steering_matrix(
            translated["positions_lambda"], instance["sidelobe_angles_deg"]
        ) @ declared_nominal)
        translation_error = float(np.max(abs(original_pattern - translated_pattern)))
        scaled = oracle._score_instance(
            lambda *_args, w=declared_nominal: (2.4 - 1.7j) * w,
            instance,
        )
        base = oracle._score_instance(
            lambda *_args, w=declared_nominal: w,
            instance,
        )
        scale_invariance_error = max(
            abs(float(base[key]) - float(scaled[key]))
            for key in ("score", "robustness_score", "nominal_quality_db")
        )
        nominal_parameter_match = bool(
            float(instance["nominal_beta"]) == nominal_grid["beta"]
            and float(instance["nominal_alpha"]) == nominal_grid["alpha"]
        )
        robust_parameter_match = bool(
            float(instance["robust_beta"]) == robust_grid["beta"]
            and float(instance["robust_alpha"]) == robust_grid["alpha"]
        )
        nominal_quality_error = abs(
            nominal_independent["quality_db"] - nominal_oracle["quality_db"]
        )
        robust_quality_error = abs(
            min(row["quality_db"] for row in robust_independent)
            - min(row["quality_db"] for row in robust_oracle)
        )
        checks.append({
            "name": instance["name"],
            "grid_candidate_count": grid_count,
            "feasible_grid_candidate_count": feasible_count,
            "declared_nominal_beta": instance["nominal_beta"],
            "declared_nominal_alpha": instance["nominal_alpha"],
            "grid_best_nominal_beta": nominal_grid["beta"],
            "grid_best_nominal_alpha": nominal_grid["alpha"],
            "declared_nominal_quality_db": nominal_independent["quality_db"],
            "grid_best_nominal_quality_db": nominal_grid["nominal_quality_db"],
            "declared_robust_beta": instance["robust_beta"],
            "declared_robust_alpha": instance["robust_alpha"],
            "grid_best_robust_beta": robust_grid["beta"],
            "grid_best_robust_alpha": robust_grid["alpha"],
            "declared_worst_shifted_quality_db": min(
                row["quality_db"] for row in robust_independent
            ),
            "grid_best_worst_shifted_quality_db": robust_grid[
                "worst_shifted_quality_db"
            ],
            "minimum_robust_reference_target_gain": min(
                row["target_gain"] for row in robust_independent
            ),
            "independent_nominal_quality_error_db": nominal_quality_error,
            "independent_robust_quality_error_db": robust_quality_error,
            "position_translation_magnitude_error": translation_error,
            "complex_scale_invariance_error": scale_invariance_error,
            "passed": bool(
                nominal_parameter_match and robust_parameter_match
                and nominal_quality_error <= 1.0e-10
                and robust_quality_error <= 1.0e-10
                and translation_error <= 1.0e-12
                and scale_invariance_error <= 1.0e-12
                and nominal_grid["nominal_quality_db"]
                > instance["baseline_nominal_metrics"]["quality_db"] + 1.0
                and robust_grid["worst_shifted_quality_db"]
                > instance["baseline_robust_quality_db"] + 1.0
                and robust_grid["minimum_shifted_target_gain"] >= 0.80
            ),
        })
    return checks


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(_policy_for(oracle, "baseline_weights"))
    nominal = oracle.evaluate(_policy_for(oracle, "nominal_reference_weights"))
    robust = oracle.evaluate(_policy_for(oracle, "robust_reference_weights"))
    nonfinite = oracle.evaluate(
        lambda positions, *_args: np.full(len(positions), np.nan + 0j)
    )
    zero = oracle.evaluate(
        lambda positions, *_args: np.zeros(len(positions), dtype=complex)
    )
    wrong_length = oracle.evaluate(lambda *_args: np.ones(1, dtype=complex))
    excessive = oracle.evaluate(
        lambda positions, *_args: np.eye(1, len(positions), dtype=complex)[0]
    )
    checks = _reference_checks(oracle)
    for invalid in (nonfinite, zero, wrong_length, excessive):
        json.dumps(invalid, allow_nan=False)
    execution_passed = bool(
        baseline["valid"] == 1.0 and baseline["combined_score"] == 0.0
        and baseline["robustness_score"] == 0.0
        and nominal["valid"] == 1.0 and nominal["combined_score"] > 0.999999
        and nominal["heldout_policy_score"] > 0.999999
        and 0.05 < nominal["robustness_score"] < 0.95
        and robust["valid"] == 1.0 and robust["robustness_score"] > 0.999999
        and robust["heldout_robustness_score"] > 0.999999
        and 0.05 < robust["combined_score"] < 0.95
        and all(row["valid"] == 0.0 and row["combined_score"] == 0.0
                for row in (nonfinite, zero, wrong_length, excessive))
        and all(row["passed"] for row in checks)
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
                "Independent exhaustive 25-by-30 beta/alpha enumeration of a "
                "Kaiser-taper plus regularized-null-projection domain family."
            ),
            "beta_grid": [float(value) for value in BETA_GRID],
            "alpha_grid": [float(value) for value in ALPHA_GRID],
            "global_optimality_claimed": False,
            "normalization_clips_better_feasible_candidates": True,
        },
        "baseline": baseline,
        "nominal_reference_policy": nominal,
        "robust_reference_policy": robust,
        "nonfinite_rejection": nonfinite,
        "zero_response_rejection": zero,
        "wrong_length_rejection": wrong_length,
        "excessive_excitation_rejection": excessive,
        "independent_reference_checks": checks,
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
