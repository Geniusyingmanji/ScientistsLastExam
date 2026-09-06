"""Deterministic finite-volume oracle for frozen scalar conservation-law panels."""
from __future__ import annotations

import importlib.util
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

TASK_DIR = Path(__file__).resolve().parent.parent
CONTRACT_DIR = TASK_DIR / "frontier_eval" / "contracts"


def _load_contract(name, filename):
    spec = importlib.util.spec_from_file_location(name, CONTRACT_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load frozen semantic contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CANONICALIZER = _load_contract(
    "adaptive_conservative_pde_method_canonicalizer",
    "method_canonicalizer_v1.py",
)
_EVIDENCE = _load_contract(
    "adaptive_conservative_pde_evidence_predicate",
    "evidence_predicate_v1.py",
)


class WorkBudgetExceeded(ValueError):
    pass


@lru_cache(maxsize=1)
def _load_panel():
    path = CONTRACT_DIR / "evaluation_panel_v1.json"
    panel = json.loads(path.read_text(encoding="utf-8"))
    if (
        panel.get("schema_version") != 2
        or not isinstance(panel.get("worlds"), list)
        or not isinstance(panel.get("oracle"), dict)
        or not isinstance(panel.get("baseline_method"), dict)
        or not isinstance(panel.get("reference_method"), dict)
    ):
        raise RuntimeError("invalid frozen evaluation panel")
    return panel


def _public_problem():
    return {
        "method_fields": list(_CANONICALIZER.METHOD_FIELDS),
        "discrete_choices": {
            "reconstruction": list(_CANONICALIZER.RECONSTRUCTIONS),
            "limiter": list(_CANONICALIZER.LIMITERS),
            "riemann_solver": list(_CANONICALIZER.RIEMANN_SOLVERS),
            "time_integrator": list(_CANONICALIZER.TIME_INTEGRATORS),
            "cells": list(_CANONICALIZER.CELL_COUNTS),
        },
        "continuous_bounds": {
            key: list(value) for key, value in _CANONICALIZER.BOUNDS.items()
        },
        "equations": ["constant-coefficient advection", "inviscid Burgers"],
        "boundary_conditions": ["periodic", "fixed far-field states"],
        "adaptivity": (
            "face states are locally blended toward the selected MUSCL fallback when a "
            "normalized curvature sensor exceeds sensor_threshold; shock_blend controls "
            "the fallback strength"
        ),
        "objectives": [
            "cell-average L1 accuracy",
            "discrete flux-balance conservation",
            "maximum-principle and total-variation stability",
            "cell-stage work",
        ],
        "work_unit_definition": "one finite-volume cell update in one Runge--Kutta stage",
        "max_work_units_per_case": max(
            int(world["max_work_units"]) for world in _load_panel()["worlds"]
        ),
        "scope_warning": (
            "repository-visible frozen scalar-law benchmark; not evidence that a method "
            "generalizes to multidimensional or real application PDEs"
        ),
    }


def _normalize_method(value, _problem=None):
    return _CANONICALIZER.normalize_method(value)


def _canonical_method_id(method):
    return _CANONICALIZER.canonical_method_id(method)


def _canonical_payload(method):
    return _CANONICALIZER.canonical_payload(method)


def _weak_method():
    return dict(_load_panel()["baseline_method"])


def _reference_method():
    return dict(_load_panel()["reference_method"])


def _initial_value(x, initial):
    kind = initial["kind"]
    if kind == "sine":
        angle = 2.0 * np.pi * initial["frequency"] * (x - initial["phase"])
        return initial["offset"] + initial["amplitude"] * np.sin(angle)
    if kind == "multisine":
        angle = 2.0 * np.pi * (x - initial["phase"])
        shape = 0.65 * np.sin(angle) + 0.25 * np.sin(3.0 * angle)
        shape += 0.10 * np.cos(5.0 * angle)
        return initial["offset"] + initial["amplitude"] * shape
    if kind == "gaussian":
        distance = np.minimum(
            np.abs(x - initial["center"]), 1.0 - np.abs(x - initial["center"])
        )
        pulse = np.exp(-0.5 * (distance / initial["width"]) ** 2)
        return initial["low"] + (initial["high"] - initial["low"]) * pulse
    if kind == "top_hat":
        inside = (x >= initial["left"]) & (x < initial["right"])
        return np.where(inside, initial["high"], initial["low"])
    if kind == "riemann":
        return np.where(x < initial["location"], initial["left"], initial["right"])
    raise RuntimeError("unknown frozen initial condition")


def _exact_value(x, world, time):
    initial = world["initial"]
    if world["equation"] == "advection":
        foot = np.mod(x - world["speed"] * time, 1.0)
        return _initial_value(foot, initial)
    left = float(initial["left"])
    right = float(initial["right"])
    location = float(initial["location"])
    if time == 0.0:
        return _initial_value(x, initial)
    if left > right:
        shock = location + 0.5 * (left + right) * time
        return np.where(x < shock, left, right)
    similarity = (x - location) / time
    return np.where(similarity <= left, left, np.where(similarity >= right, right, similarity))


def _cell_averages(world, cells, time):
    edges = np.arange(cells + 1, dtype=float) / cells
    lower_edges = edges[:-1]
    upper_edges = edges[1:]
    dx = 1.0 / cells
    initial = world["initial"]
    kind = initial["kind"]

    if world["equation"] == "advection":
        shift = float(world["speed"]) * time
        if kind in {"sine", "multisine"}:
            phase = float(initial["phase"]) + shift

            def mean_sine(harmonic):
                frequency = float(harmonic)
                omega = 2.0 * math.pi * frequency
                return (
                    np.cos(omega * (lower_edges - phase))
                    - np.cos(omega * (upper_edges - phase))
                ) / (omega * dx)

            if kind == "sine":
                return float(initial["offset"]) + float(initial["amplitude"]) * mean_sine(
                    int(initial["frequency"])
                )
            omega = 10.0 * math.pi
            mean_cosine_five = (
                np.sin(omega * (upper_edges - phase))
                - np.sin(omega * (lower_edges - phase))
            ) / (omega * dx)
            shape = 0.65 * mean_sine(1) + 0.25 * mean_sine(3)
            shape += 0.10 * mean_cosine_five
            return float(initial["offset"]) + float(initial["amplitude"]) * shape

        if kind == "top_hat":
            start = (float(initial["left"]) + shift) % 1.0
            width = float(initial["right"] - initial["left"])
            covered = np.zeros(cells, dtype=float)
            for image in (-1.0, 0.0, 1.0):
                image_left = start + image
                image_right = image_left + width
                covered += np.maximum(
                    np.minimum(upper_edges, image_right)
                    - np.maximum(lower_edges, image_left),
                    0.0,
                )
            low = float(initial["low"])
            return low + (float(initial["high"]) - low) * covered / dx

        if kind == "gaussian":
            center = (float(initial["center"]) + shift) % 1.0
            width = float(initial["width"])
            factor = width * math.sqrt(math.pi / 2.0)
            denominator = math.sqrt(2.0) * width
            pulse_integral = np.zeros(cells, dtype=float)
            for image in (-1.0, 0.0, 1.0):
                image_center = center + image
                segment_left = np.maximum(lower_edges, image_center - 0.5)
                segment_right = np.minimum(upper_edges, image_center + 0.5)
                active = segment_right > segment_left
                if not np.any(active):
                    continue
                left_values = segment_left[active]
                right_values = segment_right[active]
                primitives = np.fromiter(
                    (
                        factor
                        * (
                            math.erf((right - image_center) / denominator)
                            - math.erf((left - image_center) / denominator)
                        )
                        for left, right in zip(left_values, right_values)
                    ),
                    dtype=float,
                    count=int(np.count_nonzero(active)),
                )
                pulse_integral[active] += primitives
            low = float(initial["low"])
            return low + (float(initial["high"]) - low) * pulse_integral / dx

        raise RuntimeError("unknown frozen periodic initial condition")

    left_state = float(initial["left"])
    right_state = float(initial["right"])
    location = float(initial["location"])
    if time == 0.0 or left_state > right_state:
        front = location
        if time != 0.0:
            front += 0.5 * (left_state + right_state) * time
        left_length = np.clip(front - lower_edges, 0.0, dx)
        return (left_state * left_length + right_state * (dx - left_length)) / dx

    fan_left = location + left_state * time
    fan_right = location + right_state * time
    left_length = np.clip(fan_left - lower_edges, 0.0, dx)
    right_length = np.clip(upper_edges - fan_right, 0.0, dx)
    middle_left = np.maximum(lower_edges, fan_left)
    middle_right = np.minimum(upper_edges, fan_right)
    active = middle_right > middle_left
    fan_integral = np.zeros(cells, dtype=float)
    fan_integral[active] = (
        0.5 * (middle_right[active] ** 2 - middle_left[active] ** 2)
        - location * (middle_right[active] - middle_left[active])
    ) / time
    return (
        left_state * left_length + fan_integral + right_state * right_length
    ) / dx


def _boundary_values(world):
    initial = world["initial"]
    return float(initial["left"]), float(initial["right"])


def _minmod(*values):
    arrays = [np.asarray(value, dtype=float) for value in values]
    positive = np.logical_and.reduce([value > 0.0 for value in arrays])
    negative = np.logical_and.reduce([value < 0.0 for value in arrays])
    magnitude = np.minimum.reduce([np.abs(value) for value in arrays])
    return np.where(positive, magnitude, np.where(negative, -magnitude, 0.0))


def _limited_slope(state, method, world):
    if method["reconstruction"] == "constant":
        return np.zeros_like(state)
    if world["boundary"] == "periodic":
        backward = state - np.roll(state, 1)
        forward = np.roll(state, -1) - state
    else:
        left, right = _boundary_values(world)
        extended = np.concatenate(([left], state, [right]))
        backward = state - extended[:-2]
        forward = extended[2:] - state

    limiter = method["limiter"]
    if limiter == "minmod":
        slope = _minmod(backward, forward)
    elif limiter == "mc":
        slope = _minmod(0.5 * (backward + forward), 2.0 * backward, 2.0 * forward)
    elif limiter == "van_leer":
        denominator = backward + forward
        same_sign = backward * forward > 0.0
        epsilon = float(_load_panel()["oracle"]["division_epsilon"])
        slope = np.where(
            same_sign,
            2.0 * backward * forward / np.where(np.abs(denominator) > epsilon, denominator, 1.0),
            0.0,
        )
    elif limiter == "superbee":
        first = _minmod(2.0 * backward, forward)
        second = _minmod(backward, 2.0 * forward)
        slope = np.where(np.abs(first) >= np.abs(second), first, second)
    elif limiter == "central":
        slope = 0.5 * (backward + forward)
    else:  # pragma: no cover - canonicalization rejects unknown limiters
        raise RuntimeError("unknown limiter")

    sensor_epsilon = float(_load_panel()["oracle"]["sensor_epsilon"])
    sensor = np.abs(forward - backward) / (
        np.abs(forward) + np.abs(backward) + sensor_epsilon
    )
    threshold = method["sensor_threshold"]
    activation = np.maximum(sensor - threshold, 0.0) / (1.0 - threshold)
    activation = np.minimum(activation, 1.0)
    safe_slope = _minmod(backward, forward)
    blend = method["shock_blend"] * activation
    return (1.0 - blend) * slope + blend * safe_slope


def _weno3_pair(u_minus, u_left, u_right, u_plus):
    epsilon = float(_load_panel()["oracle"]["weno_epsilon"])
    left_zero = 0.5 * (-u_minus + 3.0 * u_left)
    left_one = 0.5 * (u_left + u_right)
    alpha_zero = (1.0 / 3.0) / (epsilon + (u_left - u_minus) ** 2) ** 2
    alpha_one = (2.0 / 3.0) / (epsilon + (u_right - u_left) ** 2) ** 2
    left = (alpha_zero * left_zero + alpha_one * left_one) / (
        alpha_zero + alpha_one
    )

    right_zero = 0.5 * (-u_plus + 3.0 * u_right)
    right_one = 0.5 * (u_right + u_left)
    alpha_zero = (1.0 / 3.0) / (epsilon + (u_right - u_plus) ** 2) ** 2
    alpha_one = (2.0 / 3.0) / (epsilon + (u_left - u_right) ** 2) ** 2
    right = (alpha_zero * right_zero + alpha_one * right_one) / (
        alpha_zero + alpha_one
    )
    return left, right


def _sensor_activation(state, method, world):
    if world["boundary"] == "periodic":
        backward = state - np.roll(state, 1)
        forward = np.roll(state, -1) - state
    else:
        left, right = _boundary_values(world)
        extended = np.concatenate(([left], state, [right]))
        backward = state - extended[:-2]
        forward = extended[2:] - state
    epsilon = float(_load_panel()["oracle"]["sensor_epsilon"])
    sensor = np.abs(forward - backward) / (
        np.abs(forward) + np.abs(backward) + epsilon
    )
    threshold = method["sensor_threshold"]
    return np.minimum(
        np.maximum(sensor - threshold, 0.0) / (1.0 - threshold),
        1.0,
    )


def _weno3_faces(state, method, world):
    fallback_method = {**method, "reconstruction": "muscl", "shock_blend": 0.0}
    fallback_slope = _limited_slope(state, fallback_method, world)
    activation = _sensor_activation(state, method, world)
    if world["boundary"] == "periodic":
        left, right = _weno3_pair(
            np.roll(state, 1), state, np.roll(state, -1), np.roll(state, -2)
        )
        safe_left = state + 0.5 * fallback_slope
        safe_right = np.roll(state, -1) - 0.5 * np.roll(fallback_slope, -1)
        blend = method["shock_blend"] * np.maximum(
            activation, np.roll(activation, -1)
        )
        return (
            (1.0 - blend) * left + blend * safe_left,
            (1.0 - blend) * right + blend * safe_right,
        )

    boundary_left, boundary_right = _boundary_values(world)
    left = np.empty(len(state) + 1, dtype=float)
    right = np.empty(len(state) + 1, dtype=float)
    left[0] = boundary_left
    right[0] = state[0] - 0.5 * fallback_slope[0]
    left[-1] = state[-1] + 0.5 * fallback_slope[-1]
    right[-1] = boundary_right
    high_left, high_right = _weno3_pair(
        np.concatenate(([boundary_left], state[:-2])),
        state[:-1],
        state[1:],
        np.concatenate((state[2:], [boundary_right])),
    )
    safe_left = state[:-1] + 0.5 * fallback_slope[:-1]
    safe_right = state[1:] - 0.5 * fallback_slope[1:]
    blend = method["shock_blend"] * np.maximum(activation[:-1], activation[1:])
    left[1:-1] = (1.0 - blend) * high_left + blend * safe_left
    right[1:-1] = (1.0 - blend) * high_right + blend * safe_right
    return left, right


def _physical_flux(value, world):
    if world["equation"] == "advection":
        return world["speed"] * value
    return 0.5 * value * value


def _numerical_flux(left, right, method, world):
    if method["riemann_solver"] == "rusanov":
        if world["equation"] == "advection":
            speed = abs(float(world["speed"]))
        else:
            speed = np.maximum(np.abs(left), np.abs(right))
        speed = method["flux_dissipation"] * speed
        return 0.5 * (_physical_flux(left, world) + _physical_flux(right, world)) - (
            0.5 * speed * (right - left)
        )
    if world["equation"] == "advection":
        return world["speed"] * (left if world["speed"] >= 0.0 else right)

    rarefaction = left <= right
    rare_flux = np.where(
        left >= 0.0,
        0.5 * left * left,
        np.where(right <= 0.0, 0.5 * right * right, 0.0),
    )
    shock_speed = 0.5 * (left + right)
    shock_flux = np.where(shock_speed >= 0.0, 0.5 * left * left, 0.5 * right * right)
    return np.where(rarefaction, rare_flux, shock_flux)


def _residual(state, method, world):
    cells = len(state)
    dx = 1.0 / cells
    if method["reconstruction"] == "weno3":
        left, right = _weno3_faces(state, method, world)
        face_flux = _numerical_flux(left, right, method, world)
        if world["boundary"] == "periodic":
            return -(face_flux - np.roll(face_flux, 1)) / dx, 0.0
        return -(face_flux[1:] - face_flux[:-1]) / dx, float(
            face_flux[-1] - face_flux[0]
        )

    slope = _limited_slope(state, method, world)
    if world["boundary"] == "periodic":
        left = state + 0.5 * slope
        right = np.roll(state, -1) - 0.5 * np.roll(slope, -1)
        face_flux = _numerical_flux(left, right, method, world)
        residual = -(face_flux - np.roll(face_flux, 1)) / dx
        return residual, 0.0

    boundary_left, boundary_right = _boundary_values(world)
    face_left = np.empty(cells + 1, dtype=float)
    face_right = np.empty(cells + 1, dtype=float)
    face_left[0] = boundary_left
    face_right[0] = state[0] - 0.5 * slope[0]
    face_left[1:cells] = state[:-1] + 0.5 * slope[:-1]
    face_right[1:cells] = state[1:] - 0.5 * slope[1:]
    face_left[cells] = state[-1] + 0.5 * slope[-1]
    face_right[cells] = boundary_right
    face_flux = _numerical_flux(face_left, face_right, method, world)
    residual = -(face_flux[1:] - face_flux[:-1]) / dx
    return residual, float(face_flux[-1] - face_flux[0])


def _stage_count(method):
    return {"euler": 1, "ssprk2": 2, "ssprk3": 3}[method["time_integrator"]]


def _speed_bound(world):
    if world["equation"] == "advection":
        return abs(float(world["speed"]))
    initial = world["initial"]
    speed_floor = float(_load_panel()["oracle"]["speed_floor"])
    return max(abs(float(initial["left"])), abs(float(initial["right"])), speed_floor)


def _estimated_work(method, world):
    padding = int(_load_panel()["oracle"]["work_padding_steps"])
    steps = math.ceil(
        world["final_time"] * _speed_bound(world) * method["cells"] / method["cfl"]
    ) + padding
    return steps * method["cells"] * _stage_count(method)


def _advance(state, dt, method, world):
    integrator = method["time_integrator"]
    first, flux_first = _residual(state, method, world)
    if integrator == "euler":
        return state + dt * first, dt * flux_first, 1
    stage_one = state + dt * first
    second, flux_second = _residual(stage_one, method, world)
    if integrator == "ssprk2":
        updated = 0.5 * state + 0.5 * (stage_one + dt * second)
        return updated, 0.5 * dt * (flux_first + flux_second), 2
    stage_two = 0.75 * state + 0.25 * (stage_one + dt * second)
    third, flux_third = _residual(stage_two, method, world)
    updated = (state / 3.0) + (2.0 / 3.0) * (stage_two + dt * third)
    flux_integral = dt * (flux_first / 6.0 + flux_second / 6.0 + 2.0 * flux_third / 3.0)
    return updated, flux_integral, 3


def _total_variation(state, world):
    if world["boundary"] == "periodic":
        return float(np.sum(np.abs(np.roll(state, -1) - state)))
    left, right = _boundary_values(world)
    return float(np.sum(np.abs(np.diff(np.concatenate(([left], state, [right]))))))


def _physical_bounds(world):
    initial = world["initial"]
    if initial["kind"] == "sine":
        return initial["offset"] - initial["amplitude"], initial["offset"] + initial["amplitude"]
    if initial["kind"] in {"gaussian", "top_hat"}:
        return float(initial["low"]), float(initial["high"])
    if initial["kind"] == "riemann":
        return min(initial["left"], initial["right"]), max(initial["left"], initial["right"])
    points = int(_load_panel()["oracle"]["physical_bound_points"])
    dense = np.arange(points, dtype=float) / points
    values = _initial_value(dense, initial)
    return float(np.min(values)), float(np.max(values))


def _run_world(method, world):
    predicted_work = _estimated_work(method, world)
    if predicted_work > int(world["max_work_units"]):
        raise WorkBudgetExceeded("declared method exceeds the frozen per-case work budget")
    cells = method["cells"]
    state = _cell_averages(world, cells, 0.0)
    mass_initial = float(np.mean(state))
    initial_tv = _total_variation(state, world)
    elapsed = 0.0
    boundary_flux_integral = 0.0
    work_units = 0
    oracle = _load_panel()["oracle"]
    time_tolerance = float(oracle["time_tolerance"])
    speed_floor = float(oracle["speed_floor"])
    while elapsed < world["final_time"] - time_tolerance:
        max_speed = _speed_bound(world)
        if world["equation"] == "burgers":
            max_speed = max(max_speed, float(np.max(np.abs(state))))
        dt = method["cfl"] / (cells * max(max_speed, speed_floor))
        dt = min(dt, world["final_time"] - elapsed)
        state, flux_integral, stages = _advance(state, dt, method, world)
        if not np.all(np.isfinite(state)):
            raise ValueError("nonfinite finite-volume state")
        elapsed += dt
        boundary_flux_integral += flux_integral
        work_units += stages * cells
        if work_units > int(world["max_work_units"]):
            raise WorkBudgetExceeded("realized method work exceeds the frozen per-case budget")

    exact = _cell_averages(world, cells, world["final_time"])
    l1_error = float(np.mean(np.abs(state - exact)))
    lower, upper = _physical_bounds(world)
    scale = max(upper - lower, speed_floor)
    overshoot = max(float(np.max(state)) - upper, lower - float(np.min(state)), 0.0)
    final_tv = _total_variation(state, world)
    tv_growth = max(final_tv - initial_tv, 0.0) / max(initial_tv, speed_floor)
    if world["boundary"] == "periodic":
        conservation_error = abs(float(np.mean(state)) - mass_initial)
    else:
        conservation_error = abs(
            float(np.mean(state)) - mass_initial + boundary_flux_integral
        )
    accuracy = math.exp(-l1_error / float(world["accuracy_scale"]))
    stability = math.exp(
        -float(oracle["stability_overshoot_scale"]) * overshoot / scale
        - float(oracle["stability_tv_scale"]) * tv_growth
    )
    conservation = math.exp(-conservation_error / float(oracle["conservation_scale"]))
    cost = 1.0 / (1.0 + work_units / float(world["max_work_units"]))
    weights = oracle["utility_weights"]
    utility = (
        float(weights["accuracy"]) * accuracy
        + float(weights["stability"]) * stability
        + float(weights["conservation"]) * conservation
        + float(weights["cost"]) * cost
    )
    initial_kind = world["initial"]["kind"]
    regime = "smooth" if initial_kind in {"sine", "multisine", "gaussian"} else "shock"
    return {
        "id": world["id"],
        "split": world["split"],
        "regime": regime,
        "l1_error": l1_error,
        "accuracy_score": accuracy,
        "stability_score": stability,
        "conservation_score": conservation,
        "conservation_error": conservation_error,
        "overshoot": overshoot,
        "tv_growth": tv_growth,
        "work_units": work_units,
        "cost_score": cost,
        "raw_utility": utility,
    }


def _mean(rows, key):
    if not rows:
        return 0.0
    return float(sum(float(row[key]) for row in rows) / len(rows))


def _aggregate(rows):
    smooth = [row for row in rows if row["regime"] == "smooth"]
    shock = [row for row in rows if row["regime"] == "shock"]
    regime_weights = _load_panel()["oracle"]["development_regime_weights"]
    raw_utility = (
        float(regime_weights["smooth"]) * _mean(smooth, "raw_utility")
        + float(regime_weights["shock"]) * _mean(shock, "raw_utility")
    )
    return {
        "raw_utility": raw_utility,
        "accuracy_score": _mean(rows, "accuracy_score"),
        "smooth_accuracy_score": _mean(smooth, "accuracy_score"),
        "shock_accuracy_score": _mean(shock, "accuracy_score"),
        "stability_score": _mean(rows, "stability_score"),
        "conservation_score": _mean(rows, "conservation_score"),
        "max_conservation_error": max(
            (float(row["conservation_error"]) for row in rows), default=math.inf
        ),
        "mean_work_units": _mean(rows, "work_units"),
        "cost_score": _mean(rows, "cost_score"),
    }


def _evaluate_fixed(method):
    normalized = _normalize_method(method)
    rows = [_run_world(normalized, world) for world in _load_panel()["worlds"]]
    development = [row for row in rows if row["split"] == "development"]
    heldout = [row for row in rows if row["split"] == "heldout"]
    return _aggregate(development), _aggregate(heldout)


@lru_cache(maxsize=1)
def _anchors():
    weak, _ = _evaluate_fixed(_weak_method())
    reference, _ = _evaluate_fixed(_reference_method())
    if reference["raw_utility"] <= weak["raw_utility"]:
        raise RuntimeError("invalid task anchors: reference must improve the weak method")
    return weak["raw_utility"], reference["raw_utility"]


def _normalized(value, weak, reference):
    if reference <= weak:
        raise ValueError("reference anchor must exceed weak anchor")
    return max((float(value) - float(weak)) / (float(reference) - float(weak)), 0.0)


def _quantize_report(metrics):
    """Round reported scores to 6 decimals so SIMD pairwise sums do not drift CI pins."""
    skip = {"per_world", "frontier_records", "evaluation_errors", "method_canonical_id"}
    quantized = dict(metrics)
    for key, value in metrics.items():
        if key in skip:
            continue
        if isinstance(value, float):
            quantized[key] = round(value, 6)
    return quantized


def _invalid_metrics(errors, call_count):
    weak, reference = _anchors()
    return _quantize_report({
        "combined_score": 0.0,
        "valid": 0.0,
        "development_raw_utility": 0.0,
        "heldout_raw_utility": 0.0,
        "baseline_utility": weak,
        "reference_utility": reference,
        "candidate_world_call_count": call_count,
        "evaluation_error_count": len(errors),
        "evaluation_errors": errors,
        "frontier_records": [],
    })


def evaluate(candidate):
    panel = _load_panel()
    expected_payload = None
    method = None
    rows = []
    errors = []
    call_count = 0
    for index, world in enumerate(panel["worlds"]):
        try:
            if index and hasattr(candidate, "reset_session"):
                candidate.reset_session()
            call_count += 1
            proposal = candidate(_public_problem())
            normalized = _normalize_method(proposal)
            payload = _canonical_payload(normalized)
            if expected_payload is None:
                expected_payload = payload
                method = normalized
            elif payload != expected_payload:
                raise ValueError("candidate must return one deterministic method for every world")
            rows.append(_run_world(normalized, world))
        except Exception as exc:  # noqa: BLE001 - candidate and method failures fail closed
            errors.append({"world_id": world["id"], "error": type(exc).__name__})

    if errors or method is None or len(rows) != len(panel["worlds"]):
        return _invalid_metrics(errors, call_count)

    development_rows = [row for row in rows if row["split"] == "development"]
    heldout_rows = [row for row in rows if row["split"] == "heldout"]
    development = _aggregate(development_rows)
    heldout = _aggregate(heldout_rows)
    development_raw = round(float(development["raw_utility"]), 6)
    heldout_raw = round(float(heldout["raw_utility"]), 6)
    weak, reference = _anchors()
    score = _normalized(development["raw_utility"], weak, reference)
    canonical_id = _canonical_method_id(method)
    record = _EVIDENCE.make_frontier_record(
        canonical_id,
        development_raw,
        development["max_conservation_error"],
        True,
    )
    frontier_records = [] if record is None else [record]
    valid = 1.0 if record is not None else 0.0
    return _quantize_report({
        "combined_score": score if valid else 0.0,
        "valid": valid,
        "development_raw_utility": development_raw,
        "development_accuracy_score": development["accuracy_score"],
        "development_smooth_accuracy_score": development["smooth_accuracy_score"],
        "development_shock_accuracy_score": development["shock_accuracy_score"],
        "development_stability_score": development["stability_score"],
        "development_conservation_score": development["conservation_score"],
        "development_max_conservation_error": development["max_conservation_error"],
        "development_mean_work_units": development["mean_work_units"],
        "development_cost_score": development["cost_score"],
        "heldout_raw_utility": heldout_raw,
        "heldout_accuracy_score": heldout["accuracy_score"],
        "heldout_smooth_accuracy_score": heldout["smooth_accuracy_score"],
        "heldout_shock_accuracy_score": heldout["shock_accuracy_score"],
        "heldout_stability_score": heldout["stability_score"],
        "heldout_conservation_score": heldout["conservation_score"],
        "heldout_max_conservation_error": heldout["max_conservation_error"],
        "heldout_mean_work_units": heldout["mean_work_units"],
        "heldout_cost_score": heldout["cost_score"],
        "baseline_utility": weak,
        "reference_utility": reference,
        "candidate_world_call_count": call_count,
        "evaluation_error_count": 0,
        "method_canonical_id": canonical_id,
        "per_world": rows,
        "frontier_records": frontier_records,
    })
