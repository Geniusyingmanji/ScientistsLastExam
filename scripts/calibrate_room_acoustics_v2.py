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
from scipy.optimize import minimize


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Acoustics/RoomImpulseResponse"
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


REFERENCE_MAXIMUM_ITERATIONS = 10
REFERENCE_MAXIMUM_FUNCTION_EVALUATIONS = 800
REFERENCE_X_TOLERANCE = 5.0e-4
REFERENCE_FUNCTION_TOLERANCE = 1.0e-6
REFERENCE_UTILITY_GAP_TOLERANCE = 2.0e-3


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


def _independent_shifted_geometry(problem, design, shift=None):
    nominal_room = np.asarray(problem["room_dimensions_m"], dtype=float)
    scale = (
        np.ones(3, dtype=float)
        if shift is None
        else np.asarray(shift["room_scale"], dtype=float)
    )
    room = nominal_room * scale
    source = np.asarray(design[:3], dtype=float) * scale
    receivers = (
        np.asarray(problem["receiver_positions_m"], dtype=float)
        * scale[None, :]
    )
    sound_speed = float(problem["speed_of_sound_m_s"])
    if shift is not None:
        source += np.asarray(shift["source_offset_m"], dtype=float)
        amplitude = float(shift["receiver_jitter_m"])
        if amplitude:
            index = np.arange(len(receivers), dtype=float)
            receivers[:, 0] += amplitude * np.sin(1.19 * index + 0.31)
            receivers[:, 1] += amplitude * np.cos(0.83 * index + 0.47)
            receivers[:, 2] += (
                0.25 * amplitude * np.sin(1.67 * index + 0.11)
            )
        sound_speed *= float(shift["sound_speed_scale"])
    return room, source, receivers, sound_speed


def _independent_geometry_feasible(oracle, room, source, receivers):
    room = np.asarray(room, dtype=float)
    source = np.asarray(source, dtype=float)
    receivers = np.asarray(receivers, dtype=float)
    return bool(
        np.all(room > 0.0)
        and np.all(source >= oracle.MINIMUM_SOURCE_CLEARANCE_M)
        and np.all(source <= room - oracle.MINIMUM_SOURCE_CLEARANCE_M)
        and np.all(receivers >= 0.10)
        and np.all(receivers <= room[None, :] - 0.10)
        and float(np.min(np.linalg.norm(
            receivers - source[None, :], axis=1
        ))) >= 0.30
    )


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


def _independent_metrics(oracle, problem, design, shift=None,
                         image_order=None):
    room, source, receivers, sound_speed = _independent_shifted_geometry(
        problem, design, shift=shift
    )
    if image_order is None:
        image_order = (
            oracle.NOMINAL_IMAGE_ORDER
            if shift is None else int(shift["image_order"])
        )
    absorption = _independent_absorption(
        problem, design[3:], room, shift=shift
    )
    if not _independent_geometry_feasible(
        oracle, room, source, receivers
    ):
        return {
            "utility": 0.0,
            "geometry_feasible": False,
            "image_order": int(image_order),
        }
    rows = tuple(
        _independent_receiver(
            oracle, room, source, receiver, sound_speed, absorption,
            int(image_order),
        )
        for receiver in receivers
    )
    c50 = np.asarray([row["c50_db"] for row in rows], dtype=float)
    total_energy = np.asarray(
        [row["total_energy"] for row in rows], dtype=float
    )
    level_db = 10.0 * np.log10(np.maximum(total_energy, 1.0e-300))
    spatial_level_std_db = np.std(level_db, axis=0)
    reverberation_time = _independent_rt(oracle, room, absorption)
    target_rt = np.asarray(
        problem["target_reverberation_time_s"], dtype=float
    )
    clarity_value = np.clip((c50 + 5.0) / 13.0, 0.0, 1.0)
    clarity_utility = float(
        0.72 * np.mean(clarity_value)
        + 0.28 * np.quantile(clarity_value, 0.20)
    )
    rt_log_error = np.log(reverberation_time / target_rt)
    reverberation_utility = float(np.mean(
        np.exp(-0.5 * (rt_log_error / 0.30) ** 2)
    ))
    uniformity_utility = float(np.mean(
        np.exp(-0.5 * (spatial_level_std_db / 3.5) ** 2)
    ))
    utility = (
        0.46 * clarity_utility
        + 0.34 * reverberation_utility
        + 0.20 * uniformity_utility
    )
    return {
        "utility": float(utility),
        "geometry_feasible": True,
        "image_order": int(image_order),
        "clarity_utility": clarity_utility,
        "reverberation_utility": reverberation_utility,
        "uniformity_utility": uniformity_utility,
        "mean_c50_db": float(np.mean(c50)),
        "twentieth_percentile_c50_db": float(np.quantile(c50, 0.20)),
        "reverberation_time_s": reverberation_time.tolist(),
        "mean_absolute_log_rt_error": float(np.mean(np.abs(rt_log_error))),
        "mean_spatial_level_std_db": float(np.mean(spatial_level_std_db)),
        "minimum_path_count": min(row["path_count"] for row in rows),
        "maximum_path_count": max(row["path_count"] for row in rows),
    }


def _independent_allocate_area(total_area, weights, maximum_areas):
    total_area = min(float(total_area), float(np.sum(maximum_areas)))
    weights = np.maximum(np.asarray(weights, dtype=float), 0.0)
    maximum_areas = np.asarray(maximum_areas, dtype=float)
    allocation = np.zeros_like(maximum_areas)
    active = maximum_areas > 0.0
    for _ in range(len(allocation) + 1):
        remaining = total_area - float(np.sum(allocation))
        if remaining <= 1.0e-12 or not np.any(active):
            break
        active_weights = weights * active
        if float(np.sum(active_weights)) <= 1.0e-12:
            active_weights = active.astype(float)
        proposal = remaining * active_weights / float(np.sum(active_weights))
        capacity = np.maximum(maximum_areas - allocation, 0.0)
        addition = np.minimum(proposal, capacity)
        allocation += addition
        active = capacity - addition > 1.0e-12
    return allocation


def _independent_family_design(problem, parameters):
    values = np.asarray(parameters, dtype=float)
    bounds = np.asarray(problem["source_position_bounds_m"], dtype=float)
    fractions = np.clip(values[:3], 0.0, 1.0)
    source = bounds[:, 0] + fractions * (bounds[:, 1] - bounds[:, 0])
    maximum_areas = (
        np.asarray(problem["surface_areas_m2"], dtype=float)
        * np.asarray(
            problem["maximum_treatment_fraction_by_surface"], dtype=float
        )
    )
    treatment = _independent_allocate_area(
        float(np.clip(values[3], 0.0, 1.0))
        * float(problem["maximum_treatment_area_m2"]),
        np.maximum(values[4:], 0.0),
        maximum_areas,
    )
    return np.concatenate((source, treatment))


def _recalibrate_family(oracle, instance, robust):
    problem = instance["problem"]
    key = (
        "robust_reference_family" if robust
        else "nominal_reference_family"
    )
    start = np.asarray(instance[key], dtype=float)
    best_parameters = start.copy()
    best_utility = -math.inf
    evaluations = 0

    def utility(parameters):
        design = _independent_family_design(problem, parameters)
        if robust:
            return min(
                _independent_metrics(
                    oracle, problem, design, shift=shift
                )["utility"]
                for shift in oracle.SHIFT_SPECS
            )
        return _independent_metrics(
            oracle, problem, design
        )["utility"]

    def objective(parameters):
        nonlocal best_parameters, best_utility, evaluations
        observed = float(utility(parameters))
        evaluations += 1
        if observed > best_utility:
            best_utility = observed
            best_parameters = np.asarray(parameters, dtype=float).copy()
        return -observed

    start_utility = float(utility(start))
    best_utility = start_utility
    result = minimize(
        objective,
        start,
        method="Powell",
        bounds=((0.0, 1.0),) * 3
        + ((0.45, 1.0),)
        + ((0.0, 1.0),) * 6,
        options={
            "maxiter": REFERENCE_MAXIMUM_ITERATIONS,
            "maxfev": REFERENCE_MAXIMUM_FUNCTION_EVALUATIONS,
            "xtol": REFERENCE_X_TOLERANCE,
            "ftol": REFERENCE_FUNCTION_TOLERANCE,
        },
    )
    terminal_utility = float(-result.fun)
    return {
        "objective": (
            "minimum utility over five sealed shifts"
            if robust else "nominal utility"
        ),
        "deterministic": True,
        "starting_parameters": start.tolist(),
        "starting_utility": start_utility,
        "best_visited_parameters": best_parameters.tolist(),
        "best_visited_utility": float(best_utility),
        "best_visited_minus_declared_utility": float(
            best_utility - start_utility
        ),
        "terminal_parameters": np.asarray(result.x, dtype=float).tolist(),
        "terminal_utility": terminal_utility,
        "terminal_minus_best_visited_utility": float(
            terminal_utility - best_utility
        ),
        "optimizer_success": bool(result.success),
        "optimizer_message": str(result.message),
        "optimizer_iterations": int(result.nit),
        "optimizer_reported_function_evaluations": int(result.nfev),
        "tracked_function_evaluations": int(evaluations),
        "passed": bool(
            best_utility >= start_utility - 1.0e-12
            and best_utility - start_utility
            <= REFERENCE_UTILITY_GAP_TOLERANCE
        ),
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


def calibrate(recalibrate_references=True):
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
    reference_recalibrations = []
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
        shifted_utility_checks = []
        for design_name, design in (
            ("baseline", instance["baseline_design"]),
            ("nominal_reference", instance["nominal_reference_design"]),
            ("robust_reference", instance["robust_reference_design"]),
        ):
            for shift in (None,) + tuple(oracle.SHIFT_SPECS):
                independent_metrics = _independent_metrics(
                    oracle, instance["problem"], design, shift=shift
                )
                evaluator_metrics = oracle._acoustic_metrics(
                    design, instance["problem"], shift=shift
                )
                shifted_utility_checks.append({
                    "design": design_name,
                    "shift": "nominal" if shift is None else shift["name"],
                    "independent_utility": independent_metrics["utility"],
                    "evaluator_utility": evaluator_metrics["utility"],
                    "absolute_utility_error": abs(
                        independent_metrics["utility"]
                        - evaluator_metrics["utility"]
                    ),
                    "geometry_feasibility_exact": (
                        independent_metrics["geometry_feasible"]
                        == evaluator_metrics["geometry_feasible"]
                    ),
                })
        all_equations_pass = all(
            row["maximum_absolute_absorption_error"] <= 1.0e-15
            and row["maximum_absolute_reverberation_time_error_s"] <= 1.0e-13
            and row["maximum_absolute_path_energy_error"] <= 1.0e-15
            and row["maximum_absolute_c50_error_db"] <= 1.0e-12
            and row["maximum_absolute_direct_distance_error_m"] <= 1.0e-13
            and row["path_counts_exact"]
            for row in equation_checks.values()
        ) and all(
            row["absolute_utility_error"] <= 2.0e-12
            and row["geometry_feasibility_exact"]
            for row in shifted_utility_checks
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
            "independent_shifted_utility_checks": shifted_utility_checks,
            "passed": bool(
                nominal_headroom > 1.0e-4
                and robust_headroom > 1.0e-4
                and nominal_horizon["utility"]
                < instance["nominal_reference"]["utility"] - 1.0e-3
                and all_equations_pass
            ),
        })
        if recalibrate_references:
            reference_recalibrations.append({
                "name": instance["name"],
                "split": instance["split"],
                "nominal": _recalibrate_family(
                    oracle, instance, robust=False
                ),
                "robust": _recalibrate_family(
                    oracle, instance, robust=True
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
    preflight_passed = bool(
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
    reference_recalibration_passed = bool(
        recalibrate_references
        and len(reference_recalibrations) == len(oracle.INSTANCES)
        and all(
            row["nominal"]["passed"] and row["robust"]["passed"]
            for row in reference_recalibrations
        )
    )
    execution_passed = bool(
        preflight_passed and reference_recalibration_passed
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
            "optimizer": "SciPy deterministic bounded Powell search with best-visited tracking",
            "maximum_iterations": REFERENCE_MAXIMUM_ITERATIONS,
            "maximum_function_evaluations": REFERENCE_MAXIMUM_FUNCTION_EVALUATIONS,
            "x_tolerance": REFERENCE_X_TOLERANCE,
            "function_tolerance": REFERENCE_FUNCTION_TOLERANCE,
            "maximum_recalibrated_minus_declared_utility": REFERENCE_UTILITY_GAP_TOLERANCE,
            "terminal_point_used_as_reference": False,
            "best_visited_point_retained_when_terminal_point_regresses": True,
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
        "reference_recalibration": {
            "performed": bool(recalibrate_references),
            "records": reference_recalibrations,
            "passed": reference_recalibration_passed,
        },
        "preflight_passed": preflight_passed,
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
    parser.add_argument(
        "--skip-reference-recalibration", action="store_true",
        help="run fast equation preflight only; output cannot be trusted calibration evidence",
    )
    args = parser.parse_args()
    report = calibrate(
        recalibrate_references=not args.skip_reference_recalibration
    )
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
