#!/usr/bin/env python3
"""Calibrate RoomImpulseResponse-v2 equations, anchors and robustness axes."""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Acoustics/RoomImpulseResponse"
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location(
        "room_acoustics_v2_calibration_oracle", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load RoomImpulseResponse-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _independent_axis_images(source, receiver, length, maximum_order):
    rows = []
    for cell in range(-int(maximum_order), int(maximum_order) + 1):
        for sign in (1.0, -1.0):
            image = 2.0 * cell * float(length) + sign * float(source)
            low = min(float(receiver), image)
            high = max(float(receiver), image)
            crossed = range(
                math.floor(low / float(length)) + 1,
                math.ceil(high / float(length)),
            )
            low_hits = sum(int(index % 2 == 0) for index in crossed)
            high_hits = sum(int(index % 2 != 0) for index in crossed)
            if low_hits + high_hits <= int(maximum_order):
                rows.append((image, low_hits, high_hits))
    return tuple(rows)


def _independent_paths(room, source, receiver, maximum_order):
    axes = tuple(
        _independent_axis_images(
            source[index], receiver[index], room[index], maximum_order
        )
        for index in range(3)
    )
    rows = []
    for xrow, yrow, zrow in itertools.product(*axes):
        counts = np.asarray(
            (xrow[1], xrow[2], yrow[1], yrow[2], zrow[1], zrow[2]),
            dtype=int,
        )
        order = int(np.sum(counts))
        if order > int(maximum_order):
            continue
        image = np.asarray((xrow[0], yrow[0], zrow[0]), dtype=float)
        distance = float(np.linalg.norm(image - np.asarray(receiver, dtype=float)))
        rows.append((distance, counts, order))
    rows.sort(key=lambda row: (row[2], row[0], tuple(row[1])))
    return rows


def _surface_areas(room):
    lx, ly, lz = map(float, room)
    return np.asarray((ly * lz, ly * lz, lx * lz, lx * lz, lx * ly, lx * ly))


def _independent_absorption(problem, treatment_area, room, shift=None):
    base = np.asarray(problem["base_absorption_coefficients"], dtype=float)
    treatment = np.asarray(
        problem["treatment_absorption_coefficients"], dtype=float
    )
    effectiveness = 1.0
    if shift is not None:
        base = np.clip(
            base * float(shift["base_absorption_scale"]), 0.005, 0.97
        )
        effectiveness = float(shift["treatment_effectiveness"])
    realized = base + effectiveness * np.maximum(
        treatment[None, :] - base, 0.0
    )
    coverage = np.asarray(treatment_area, dtype=float) / _surface_areas(room)
    return base + coverage[:, None] * (realized - base)


def _independent_rt(oracle, room, absorption):
    areas = _surface_areas(room)
    volume = float(np.prod(room))
    denominator = np.sum(
        -areas[:, None] * np.log1p(-np.asarray(absorption, dtype=float)),
        axis=0,
    ) + 4.0 * volume * oracle.AIR_ENERGY_ATTENUATION_NP_M
    return 0.161 * volume / denominator


def _independent_receiver(oracle, room, source, receiver, sound_speed,
                          absorption, maximum_order):
    paths = _independent_paths(room, source, receiver, maximum_order)
    distance = np.asarray([row[0] for row in paths], dtype=float)
    counts = np.asarray([row[1] for row in paths], dtype=int)
    orders = np.asarray([row[2] for row in paths], dtype=int)
    log_energy = counts @ np.log1p(-np.asarray(absorption, dtype=float))
    energy = (
        np.exp(log_energy)
        / (4.0 * np.pi * distance[:, None]) ** 2
        * np.exp(
            -2.0 * distance[:, None]
            * oracle.AIR_ENERGY_ATTENUATION_NP_M[None, :]
        )
    )
    direct_distance = float(distance[orders == 0][0])
    early = distance / float(sound_speed) <= (
        direct_distance / float(sound_speed) + oracle.EARLY_WINDOW_S + 1.0e-15
    )
    early_energy = np.sum(energy[early], axis=0)
    late_energy = np.sum(energy[~early], axis=0)
    return {
        "early_energy": early_energy,
        "late_energy": late_energy,
        "total_energy": early_energy + late_energy,
        "c50_db": 10.0 * np.log10(
            np.maximum(early_energy, 1.0e-300)
            / np.maximum(late_energy, 1.0e-300)
        ),
        "path_count": int(len(paths)),
        "direct_distance_m": direct_distance,
    }


def _independent_nominal_check(oracle, instance, design):
    problem = instance["problem"]
    room = np.asarray(problem["room_dimensions_m"], dtype=float)
    source = np.asarray(design[:3], dtype=float)
    receivers = np.asarray(problem["receiver_positions_m"], dtype=float)
    sound_speed = float(problem["speed_of_sound_m_s"])
    absorption = _independent_absorption(problem, design[3:], room)
    rt = _independent_rt(oracle, room, absorption)
    independent_rows = [
        _independent_receiver(
            oracle, room, source, receiver, sound_speed, absorption,
            oracle.NOMINAL_IMAGE_ORDER,
        )
        for receiver in receivers
    ]
    oracle_rows = [
        oracle._receiver_band_energies(
            room, source, receiver, sound_speed, absorption,
            oracle.NOMINAL_IMAGE_ORDER,
        )
        for receiver in receivers
    ]
    maximum_energy_error = max(
        float(np.max(np.abs(left[key] - right[key])))
        for left, right in zip(independent_rows, oracle_rows)
        for key in ("early_energy", "late_energy", "total_energy")
    )
    maximum_c50_error = max(
        float(np.max(np.abs(left["c50_db"] - right["c50_db"])))
        for left, right in zip(independent_rows, oracle_rows)
    )
    path_count_exact = all(
        left["path_count"] == right["path_count"]
        for left, right in zip(independent_rows, oracle_rows)
    )
    direct_distance_error = max(
        abs(left["direct_distance_m"] - right["direct_distance_m"])
        for left, right in zip(independent_rows, oracle_rows)
    )
    oracle_absorption, _ = oracle._effective_absorption(
        problem, design[3:], room
    )
    oracle_rt = oracle._reverberation_time(room, oracle_absorption)
    return {
        "maximum_absolute_absorption_error": float(np.max(np.abs(
            absorption - oracle_absorption
        ))),
        "maximum_absolute_reverberation_time_error_s": float(np.max(np.abs(
            rt - oracle_rt
        ))),
        "maximum_absolute_path_energy_error": maximum_energy_error,
        "maximum_absolute_c50_error_db": maximum_c50_error,
        "maximum_absolute_direct_distance_error_m": direct_distance_error,
        "path_counts_exact": path_count_exact,
        "minimum_path_count": min(row["path_count"] for row in independent_rows),
        "maximum_path_count": max(row["path_count"] for row in independent_rows),
    }


def _compact(metrics):
    keys = (
        "combined_score", "valid", "feasibility_rate", "raw_score",
        "robustness_score", "development_validation_gap",
        "heldout_policy_score", "heldout_robustness_score",
        "heldout_feasibility_rate", "development_nominal_utility",
        "heldout_nominal_utility", "development_robust_utility",
        "heldout_robust_utility", "development_proxy_utility",
        "heldout_proxy_utility", "development_proxy_exact_gap",
        "heldout_proxy_exact_gap", "candidate_instance_call_count",
        "candidate_instance_valid_rate", "error_message",
    )
    return {key: metrics.get(key) for key in keys if key in metrics}


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(
        lambda problem: oracle._weak_baseline_design(problem)
    )
    baseline_replay = oracle.evaluate(
        lambda problem: oracle._weak_baseline_design(problem)
    )
    nominal = oracle.evaluate(
        lambda problem: oracle.reference_policy(problem, robust=False)
    )
    robust = oracle.evaluate(
        lambda problem: oracle.reference_policy(problem, robust=True)
    )
    invalid = {
        "wrong_shape": oracle.evaluate(lambda _problem: np.zeros(8)),
        "nonfinite": oracle.evaluate(lambda _problem: np.full(9, np.nan)),
        "complex": oracle.evaluate(
            lambda _problem: np.zeros(9, dtype=complex) + 1j
        ),
        "negative": oracle.evaluate(lambda _problem: -np.ones(9)),
        "over_budget": oracle.evaluate(
            lambda problem: np.concatenate((
                np.mean(np.asarray(problem["source_position_bounds_m"]), axis=1),
                np.full(6, float(problem["maximum_treatment_area_m2"])),
            ))
        ),
    }
    deterministic = bool(
        json.dumps(baseline, sort_keys=True, allow_nan=False)
        == json.dumps(baseline_replay, sort_keys=True, allow_nan=False)
    )

    instance_checks = []
    for instance in oracle.INSTANCES:
        equation_checks = {
            name: _independent_nominal_check(oracle, instance, design)
            for name, design in (
                ("baseline", instance["baseline_design"]),
                ("nominal_reference", instance["nominal_reference_design"]),
                ("robust_reference", instance["robust_reference_design"]),
            )
        }
        nominal_proxy = oracle._acoustic_metrics(
            instance["nominal_reference_design"], instance["problem"],
            image_order=oracle.PROXY_IMAGE_ORDER,
        )
        nominal_horizon = oracle._acoustic_metrics(
            instance["nominal_reference_design"], instance["problem"],
            image_order=14,
        )
        all_equations_pass = all(
            row["maximum_absolute_absorption_error"] <= 1.0e-15
            and row["maximum_absolute_reverberation_time_error_s"] <= 1.0e-13
            and row["maximum_absolute_path_energy_error"] <= 1.0e-15
            and row["maximum_absolute_c50_error_db"] <= 1.0e-12
            and row["maximum_absolute_direct_distance_error_m"] <= 1.0e-13
            and row["path_counts_exact"]
            for row in equation_checks.values()
        )
        nominal_headroom = (
            instance["nominal_reference"]["utility"]
            - instance["baseline_nominal"]["utility"]
        )
        robust_headroom = (
            instance["robust_reference_utility"]
            - instance["baseline_robust_utility"]
        )
        instance_checks.append({
            "name": instance["name"],
            "split": instance["split"],
            "receiver_count": len(instance["problem"]["receiver_positions_m"]),
            "room_dimensions_m": list(instance["problem"]["room_dimensions_m"]),
            "maximum_treatment_area_m2": instance["problem"]["maximum_treatment_area_m2"],
            "baseline_nominal_utility": instance["baseline_nominal"]["utility"],
            "nominal_reference_utility": instance["nominal_reference"]["utility"],
            "nominal_reference_headroom": nominal_headroom,
            "baseline_robust_utility": instance["baseline_robust_utility"],
            "robust_reference_utility": instance["robust_reference_utility"],
            "robust_reference_headroom": robust_headroom,
            "nominal_reference_design": instance["nominal_reference_design"].tolist(),
            "robust_reference_design": instance["robust_reference_design"].tolist(),
            "nominal_reference_family": list(instance["nominal_reference_family"]),
            "robust_reference_family": list(instance["robust_reference_family"]),
            "nominal_reference_axes": {
                key: instance["nominal_reference"][key]
                for key in (
                    "clarity_utility", "reverberation_utility",
                    "uniformity_utility", "mean_c50_db",
                    "twentieth_percentile_c50_db",
                    "mean_absolute_log_rt_error",
                    "mean_spatial_level_std_db",
                )
            },
            "first_order_proxy_utility": nominal_proxy["utility"],
            "proxy_minus_nominal_utility": (
                nominal_proxy["utility"]
                - instance["nominal_reference"]["utility"]
            ),
            "order14_utility": nominal_horizon["utility"],
            "order14_minus_order10_utility": (
                nominal_horizon["utility"]
                - instance["nominal_reference"]["utility"]
            ),
            "independent_equation_checks": equation_checks,
            "passed": bool(
                nominal_headroom > 1.0e-4
                and robust_headroom > 1.0e-4
                and nominal_horizon["utility"]
                < instance["nominal_reference"]["utility"] - 1.0e-3
                and all_equations_pass
            ),
        })

    invalid_passed = all(
        row["valid"] == 0.0
        and row["combined_score"] == 0.0
        and row["raw_score"] == 0.0
        for row in invalid.values()
    )
    difficulty_passed = bool(
        nominal["combined_score"] > 0.999999
        and nominal["heldout_policy_score"] > 0.999999
        and nominal["robustness_score"] > 0.90
        and nominal["heldout_robustness_score"] > 0.50
        and robust["robustness_score"] > 0.999999
        and robust["heldout_robustness_score"] > 0.999999
        and robust["combined_score"] > 0.90
        and robust["heldout_policy_score"] > 0.50
        and baseline["development_proxy_exact_gap"] > 0.05
    )
    execution_passed = bool(
        oracle.ROOM_ACOUSTICS_V2
        and len(oracle.DEVELOPMENT_INSTANCES) == 4
        and len(oracle.HELDOUT_INSTANCES) == 2
        and len(oracle.SHIFT_SPECS) == 5
        and baseline["valid"] == 1.0
        and baseline["combined_score"] == 0.0
        and baseline["robustness_score"] == 0.0
        and nominal["valid"] == 1.0
        and robust["valid"] == 1.0
        and deterministic
        and invalid_passed
        and all(row["passed"] for row in instance_checks)
        and difficulty_passed
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "REDUCED_ORDER_ROOM_ACOUSTICS_OPTIMIZATION_TASK_CALIBRATION_NOT_"
            "WAVE_SOLVER_MEASUREMENT_BUILDING_DESIGN_OR_DISCOVERY_VALIDATION"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "task_dimensions": {
            "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
            "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
            "shift_count": len(oracle.SHIFT_SPECS),
            "octave_band_count": len(oracle.BAND_CENTERS_HZ),
            "nominal_image_order": oracle.NOMINAL_IMAGE_ORDER,
            "proxy_image_order": oracle.PROXY_IMAGE_ORDER,
            "higher_order_shift": 14,
            "receiver_count_range": [
                min(len(row["problem"]["receiver_positions_m"]) for row in oracle.INSTANCES),
                max(len(row["problem"]["receiver_positions_m"]) for row in oracle.INSTANCES),
            ],
            "room_volume_range_m3": [
                min(float(np.prod(row["problem"]["room_dimensions_m"])) for row in oracle.INSTANCES),
                max(float(np.prod(row["problem"]["room_dimensions_m"])) for row in oracle.INSTANCES),
            ],
        },
        "reference_method": {
            "family": (
                "three normalized source coordinates, treatment-budget utilization, "
                "and six capped nonnegative surface-allocation weights"
            ),
            "optimizer": "deterministic bounded Powell search used during v2 construction",
            "global_optimality_claimed": False,
            "normalization_clips_better_feasible_candidates": True,
        },
        "weak_baseline": _compact(baseline),
        "nominal_reference_policy": _compact(nominal),
        "robust_reference_policy": _compact(robust),
        "invalid_artifact_checks": {
            key: _compact(value) for key, value in invalid.items()
        },
        "independent_equation_and_reference_checks": instance_checks,
        "determinism_check": {
            "exact_json_replay": deterministic,
            "passed": deterministic,
        },
        "difficulty_gate": {
            "nominal_reference_score": nominal["combined_score"],
            "nominal_reference_cross_robustness": nominal["robustness_score"],
            "nominal_reference_heldout_robustness": nominal["heldout_robustness_score"],
            "robust_reference_score": robust["combined_score"],
            "robust_reference_heldout_nominal_score": robust["heldout_policy_score"],
            "baseline_development_proxy_exact_gap": baseline["development_proxy_exact_gap"],
            "passed": difficulty_passed,
        },
        "limitations": [
            "The oracle assumes rectangular rooms, frequency-banded energy image sources and locally mixed absorption; it omits phase interference, diffraction, diffuse scattering and structural coupling.",
            "The first-order proxy and order-10/order-14 models are computational models, not experimental truth.",
            "The deterministic repository-visible rooms require server-held procedural rooms before population or leakage-resistant generalization claims.",
            "The frozen nominal and robust witnesses are reproducible members of a ten-parameter family, not certificates of global optimality.",
            "Architectural or product claims require hybrid wave/ray simulation and measured room impulse responses under an applicable measurement protocol.",
            "Task calibration does not measure GPT-5.5, feedback causality, model-population performance or autonomous scientific discovery.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main() -> int:
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
