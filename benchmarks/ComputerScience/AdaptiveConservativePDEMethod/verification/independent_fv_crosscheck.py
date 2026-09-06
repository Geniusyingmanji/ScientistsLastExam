"""Independent finite-volume replay used only to cross-check the primary oracle.

This module deliberately owns a second copy of the seven scientific worlds and numerical
semantics.  It does not read task artifacts at runtime.  Face reconstruction is written as an
explicit interface loop so agreement is not obtained by sharing the primary implementation.
"""
from __future__ import annotations

import math

import numpy as np

WORLDS = (
    {
        "id": "dev-advection-sine",
        "split": "development",
        "equation": "advection",
        "boundary": "periodic",
        "speed": 1.0,
        "initial": {
            "kind": "sine",
            "offset": 0.15,
            "amplitude": 0.75,
            "frequency": 1,
            "phase": 0.08,
        },
        "final_time": 0.37,
        "accuracy_scale": 0.035,
        "max_work_units": 120000,
    },
    {
        "id": "dev-advection-multisine",
        "split": "development",
        "equation": "advection",
        "boundary": "periodic",
        "speed": -0.7,
        "initial": {
            "kind": "multisine",
            "offset": -0.1,
            "amplitude": 0.65,
            "phase": 0.21,
        },
        "final_time": 0.43,
        "accuracy_scale": 0.045,
        "max_work_units": 120000,
    },
    {
        "id": "dev-advection-top-hat",
        "split": "development",
        "equation": "advection",
        "boundary": "periodic",
        "speed": 0.85,
        "initial": {
            "kind": "top_hat",
            "left": 0.19,
            "right": 0.58,
            "low": -0.15,
            "high": 0.9,
        },
        "final_time": 0.31,
        "accuracy_scale": 0.075,
        "max_work_units": 120000,
    },
    {
        "id": "dev-burgers-shock",
        "split": "development",
        "equation": "burgers",
        "boundary": "fixed",
        "initial": {
            "kind": "riemann",
            "location": 0.32,
            "left": 1.0,
            "right": 0.0,
        },
        "final_time": 0.24,
        "accuracy_scale": 0.07,
        "max_work_units": 120000,
    },
    {
        "id": "heldout-advection-gaussian",
        "split": "heldout",
        "equation": "advection",
        "boundary": "periodic",
        "speed": 1.3,
        "initial": {
            "kind": "gaussian",
            "center": 0.72,
            "width": 0.085,
            "low": -0.2,
            "high": 0.8,
        },
        "final_time": 0.29,
        "accuracy_scale": 0.045,
        "max_work_units": 120000,
    },
    {
        "id": "heldout-advection-narrow-pulse",
        "split": "heldout",
        "equation": "advection",
        "boundary": "periodic",
        "speed": -1.1,
        "initial": {
            "kind": "top_hat",
            "left": 0.41,
            "right": 0.59,
            "low": 0.05,
            "high": 1.0,
        },
        "final_time": 0.27,
        "accuracy_scale": 0.075,
        "max_work_units": 120000,
    },
    {
        "id": "heldout-burgers-rarefaction",
        "split": "heldout",
        "equation": "burgers",
        "boundary": "fixed",
        "initial": {
            "kind": "riemann",
            "location": 0.44,
            "left": -0.35,
            "right": 0.85,
        },
        "final_time": 0.21,
        "accuracy_scale": 0.075,
        "max_work_units": 120000,
    },
)

WENO_EPSILON = 0.01
SENSOR_EPSILON = 1.0e-14
DIVISION_EPSILON = 1.0e-15
TIME_TOLERANCE = 1.0e-15
SPEED_FLOOR = 1.0e-12
WORK_PADDING_STEPS = 2
UTILITY_WEIGHTS = (0.72, 0.14, 0.10, 0.04)
REGIME_WEIGHTS = {"smooth": 0.8, "shock": 0.2}


def _cell_targets(world, cells, time):
    dx = 1.0 / cells
    edges = np.linspace(0.0, 1.0, cells + 1)
    result = np.empty(cells, dtype=float)
    initial = world["initial"]

    if world["equation"] == "advection":
        shift = float(world["speed"]) * time
        phase = float(initial.get("phase", 0.0)) + shift
        for cell in range(cells):
            lower = edges[cell]
            upper = edges[cell + 1]
            kind = initial["kind"]
            if kind == "sine":
                omega = 2.0 * math.pi * float(initial["frequency"])
                mean = (
                    math.cos(omega * (lower - phase))
                    - math.cos(omega * (upper - phase))
                ) / (omega * dx)
                result[cell] = float(initial["offset"]) + float(initial["amplitude"]) * mean
                continue
            if kind == "multisine":
                def sine_mean(harmonic, lower=lower, upper=upper):
                    omega = 2.0 * math.pi * harmonic
                    return (
                        math.cos(omega * (lower - phase))
                        - math.cos(omega * (upper - phase))
                    ) / (omega * dx)

                omega = 10.0 * math.pi
                cosine_mean = (
                    math.sin(omega * (upper - phase))
                    - math.sin(omega * (lower - phase))
                ) / (omega * dx)
                shape = 0.65 * sine_mean(1) + 0.25 * sine_mean(3) + 0.10 * cosine_mean
                result[cell] = float(initial["offset"]) + float(initial["amplitude"]) * shape
                continue
            if kind == "top_hat":
                start = (float(initial["left"]) + shift) % 1.0
                width = float(initial["right"] - initial["left"])
                overlap = 0.0
                for image in (-1.0, 0.0, 1.0):
                    image_left = start + image
                    image_right = image_left + width
                    overlap += max(min(upper, image_right) - max(lower, image_left), 0.0)
                low = float(initial["low"])
                result[cell] = low + (float(initial["high"]) - low) * overlap / dx
                continue
            if kind == "gaussian":
                center = (float(initial["center"]) + shift) % 1.0
                width = float(initial["width"])
                factor = width * math.sqrt(math.pi / 2.0)
                denominator = math.sqrt(2.0) * width
                integral = 0.0
                for image in (-1.0, 0.0, 1.0):
                    image_center = center + image
                    segment_left = max(lower, image_center - 0.5)
                    segment_right = min(upper, image_center + 0.5)
                    if segment_right > segment_left:
                        integral += factor * (
                            math.erf((segment_right - image_center) / denominator)
                            - math.erf((segment_left - image_center) / denominator)
                        )
                low = float(initial["low"])
                result[cell] = low + (float(initial["high"]) - low) * integral / dx
                continue
            raise RuntimeError("unknown periodic profile")
        return result

    left_state = float(initial["left"])
    right_state = float(initial["right"])
    location = float(initial["location"])
    if time == 0.0 or left_state > right_state:
        front = location
        if time:
            front += 0.5 * (left_state + right_state) * time
        for cell in range(cells):
            lower = edges[cell]
            upper = edges[cell + 1]
            left_length = min(max(front - lower, 0.0), dx)
            result[cell] = (
                left_state * left_length + right_state * (dx - left_length)
            ) / dx
        return result

    fan_left = location + left_state * time
    fan_right = location + right_state * time
    for cell in range(cells):
        lower = edges[cell]
        upper = edges[cell + 1]
        left_length = min(max(fan_left - lower, 0.0), dx)
        right_length = min(max(upper - fan_right, 0.0), dx)
        middle_left = max(lower, fan_left)
        middle_right = min(upper, fan_right)
        fan_integral = 0.0
        if middle_right > middle_left:
            fan_integral = (
                0.5 * (middle_right**2 - middle_left**2)
                - location * (middle_right - middle_left)
            ) / time
        result[cell] = (
            left_state * left_length + fan_integral + right_state * right_length
        ) / dx
    return result


def _minmod(*values):
    if all(value > 0.0 for value in values):
        return min(values)
    if all(value < 0.0 for value in values):
        return max(values)
    return 0.0


def _base_slope(backward, forward, limiter):
    if limiter == "minmod":
        return _minmod(backward, forward)
    if limiter == "mc":
        return _minmod(0.5 * (backward + forward), 2.0 * backward, 2.0 * forward)
    if limiter == "van_leer":
        denominator = backward + forward
        if backward * forward <= 0.0 or abs(denominator) <= DIVISION_EPSILON:
            return 0.0
        return 2.0 * backward * forward / denominator
    if limiter == "superbee":
        first = _minmod(2.0 * backward, forward)
        second = _minmod(backward, 2.0 * forward)
        return first if abs(first) >= abs(second) else second
    if limiter == "central":
        return 0.5 * (backward + forward)
    raise RuntimeError("unknown limiter")


def _differences(state, world):
    cells = len(state)
    backward = np.empty(cells, dtype=float)
    forward = np.empty(cells, dtype=float)
    boundary_left = float(world["initial"].get("left", 0.0))
    boundary_right = float(world["initial"].get("right", 0.0))
    for cell in range(cells):
        previous = state[cell - 1] if cell else (
            state[-1] if world["boundary"] == "periodic" else boundary_left
        )
        following = state[cell + 1] if cell + 1 < cells else (
            state[0] if world["boundary"] == "periodic" else boundary_right
        )
        backward[cell] = state[cell] - previous
        forward[cell] = following - state[cell]
    return backward, forward


def _slopes_and_sensor(state, method, world):
    backward, forward = _differences(state, world)
    slopes = np.array(
        [
            _base_slope(backward[index], forward[index], method["limiter"])
            for index in range(len(state))
        ],
        dtype=float,
    )
    sensor = np.abs(forward - backward) / (
        np.abs(forward) + np.abs(backward) + SENSOR_EPSILON
    )
    activation = np.clip(
        (sensor - float(method["sensor_threshold"]))
        / (1.0 - float(method["sensor_threshold"])),
        0.0,
        1.0,
    )
    return slopes, activation, backward, forward


def _weno_pair(u_minus, u_left, u_right, u_plus):
    candidate_left_zero = 0.5 * (-u_minus + 3.0 * u_left)
    candidate_left_one = 0.5 * (u_left + u_right)
    weight_left_zero = (1.0 / 3.0) / (WENO_EPSILON + (u_left - u_minus) ** 2) ** 2
    weight_left_one = (2.0 / 3.0) / (WENO_EPSILON + (u_right - u_left) ** 2) ** 2
    left = (
        weight_left_zero * candidate_left_zero + weight_left_one * candidate_left_one
    ) / (weight_left_zero + weight_left_one)

    candidate_right_zero = 0.5 * (-u_plus + 3.0 * u_right)
    candidate_right_one = 0.5 * (u_right + u_left)
    weight_right_zero = (1.0 / 3.0) / (WENO_EPSILON + (u_right - u_plus) ** 2) ** 2
    weight_right_one = (2.0 / 3.0) / (WENO_EPSILON + (u_left - u_right) ** 2) ** 2
    right = (
        weight_right_zero * candidate_right_zero
        + weight_right_one * candidate_right_one
    ) / (weight_right_zero + weight_right_one)
    return left, right


def _face_states(state, method, world):
    cells = len(state)
    if method["reconstruction"] == "constant":
        slopes = np.zeros(cells, dtype=float)
        activation = np.zeros(cells, dtype=float)
    else:
        slopes, activation, backward, forward = _slopes_and_sensor(state, method, world)
        if method["reconstruction"] == "muscl":
            for cell in range(cells):
                safe = _minmod(backward[cell], forward[cell])
                blend = float(method["shock_blend"]) * activation[cell]
                slopes[cell] = (1.0 - blend) * slopes[cell] + blend * safe

    periodic = world["boundary"] == "periodic"
    face_count = cells if periodic else cells + 1
    left_states = np.empty(face_count, dtype=float)
    right_states = np.empty(face_count, dtype=float)
    if not periodic:
        left_states[0] = float(world["initial"]["left"])
        right_states[0] = state[0] - 0.5 * slopes[0]
        left_states[-1] = state[-1] + 0.5 * slopes[-1]
        right_states[-1] = float(world["initial"]["right"])

    first_face = 0 if periodic else 1
    for face in range(first_face, cells):
        left_cell = face if periodic else face - 1
        right_cell = (left_cell + 1) % cells
        if method["reconstruction"] != "weno3":
            left_states[face] = state[left_cell] + 0.5 * slopes[left_cell]
            right_states[face] = state[right_cell] - 0.5 * slopes[right_cell]
            continue
        previous = state[left_cell - 1] if left_cell else (
            state[-1] if periodic else float(world["initial"]["left"])
        )
        next_after_right = state[(right_cell + 1) % cells] if (
            periodic or right_cell + 1 < cells
        ) else float(world["initial"]["right"])
        high_left, high_right = _weno_pair(
            previous, state[left_cell], state[right_cell], next_after_right
        )
        safe_left = state[left_cell] + 0.5 * slopes[left_cell]
        safe_right = state[right_cell] - 0.5 * slopes[right_cell]
        blend = float(method["shock_blend"]) * max(
            activation[left_cell], activation[right_cell]
        )
        left_states[face] = (1.0 - blend) * high_left + blend * safe_left
        right_states[face] = (1.0 - blend) * high_right + blend * safe_right
    return left_states, right_states


def _flux(left, right, method, world):
    if world["equation"] == "advection":
        speed = float(world["speed"])
        physical_left = speed * left
        physical_right = speed * right
        wave_speed = abs(speed)
    else:
        physical_left = 0.5 * left * left
        physical_right = 0.5 * right * right
        wave_speed = np.maximum(np.abs(left), np.abs(right))
    if method["riemann_solver"] == "rusanov":
        return 0.5 * (physical_left + physical_right) - 0.5 * (
            float(method["flux_dissipation"]) * wave_speed
        ) * (right - left)
    if world["equation"] == "advection":
        return physical_left if float(world["speed"]) >= 0.0 else physical_right
    result = np.empty_like(left)
    for face, (left_value, right_value) in enumerate(zip(left, right)):
        if left_value <= right_value:
            if left_value >= 0.0:
                result[face] = 0.5 * left_value * left_value
            elif right_value <= 0.0:
                result[face] = 0.5 * right_value * right_value
            else:
                result[face] = 0.0
        elif 0.5 * (left_value + right_value) >= 0.0:
            result[face] = 0.5 * left_value * left_value
        else:
            result[face] = 0.5 * right_value * right_value
    return result


def _rhs(state, method, world):
    face_left, face_right = _face_states(state, method, world)
    face_flux = _flux(face_left, face_right, method, world)
    if world["boundary"] == "periodic":
        divergence = face_flux - np.roll(face_flux, 1)
        boundary_difference = 0.0
    else:
        divergence = face_flux[1:] - face_flux[:-1]
        boundary_difference = float(face_flux[-1] - face_flux[0])
    return -len(state) * divergence, boundary_difference


def _step(state, dt, method, world):
    rhs_zero, flux_zero = _rhs(state, method, world)
    if method["time_integrator"] == "euler":
        return state + dt * rhs_zero, dt * flux_zero, 1
    state_one = state + dt * rhs_zero
    rhs_one, flux_one = _rhs(state_one, method, world)
    if method["time_integrator"] == "ssprk2":
        return (
            0.5 * state + 0.5 * (state_one + dt * rhs_one),
            0.5 * dt * (flux_zero + flux_one),
            2,
        )
    state_two = 0.75 * state + 0.25 * (state_one + dt * rhs_one)
    rhs_two, flux_two = _rhs(state_two, method, world)
    return (
        state / 3.0 + (2.0 / 3.0) * (state_two + dt * rhs_two),
        dt * (flux_zero / 6.0 + flux_one / 6.0 + 2.0 * flux_two / 3.0),
        3,
    )


def _speed_bound(world, state=None):
    if world["equation"] == "advection":
        return abs(float(world["speed"]))
    initial = world["initial"]
    bound = max(abs(float(initial["left"])), abs(float(initial["right"])), SPEED_FLOOR)
    if state is not None:
        bound = max(bound, float(np.max(np.abs(state))))
    return bound


def _total_variation(state, world):
    if world["boundary"] == "periodic":
        return float(np.sum(np.abs(state - np.roll(state, 1))))
    extended = np.concatenate(
        ([float(world["initial"]["left"])], state, [float(world["initial"]["right"])])
    )
    return float(np.sum(np.abs(np.diff(extended))))


def _profile_bounds(world):
    initial = world["initial"]
    kind = initial["kind"]
    if kind == "sine":
        return (
            float(initial["offset"] - initial["amplitude"]),
            float(initial["offset"] + initial["amplitude"]),
        )
    if kind in {"gaussian", "top_hat"}:
        return float(initial["low"]), float(initial["high"])
    if kind == "riemann":
        return min(initial["left"], initial["right"]), max(
            initial["left"], initial["right"]
        )
    points = np.arange(16384, dtype=float) / 16384.0
    angle = 2.0 * math.pi * (points - float(initial["phase"]))
    shape = 0.65 * np.sin(angle) + 0.25 * np.sin(3.0 * angle)
    shape += 0.10 * np.cos(5.0 * angle)
    values = float(initial["offset"]) + float(initial["amplitude"]) * shape
    return float(np.min(values)), float(np.max(values))


def _run(method, world):
    cells = int(method["cells"])
    predicted_steps = math.ceil(
        world["final_time"] * _speed_bound(world) * cells / float(method["cfl"])
    ) + WORK_PADDING_STEPS
    stages = {"euler": 1, "ssprk2": 2, "ssprk3": 3}[method["time_integrator"]]
    if predicted_steps * cells * stages > int(world["max_work_units"]):
        raise ValueError("work budget exceeded")
    state = _cell_targets(world, cells, 0.0)
    initial_mass = float(np.mean(state))
    initial_tv = _total_variation(state, world)
    elapsed = 0.0
    boundary_integral = 0.0
    work = 0
    while elapsed < float(world["final_time"]) - TIME_TOLERANCE:
        dt = float(method["cfl"]) / (cells * max(_speed_bound(world, state), SPEED_FLOOR))
        dt = min(dt, float(world["final_time"]) - elapsed)
        state, flux_increment, stage_count = _step(state, dt, method, world)
        elapsed += dt
        boundary_integral += flux_increment
        work += cells * stage_count
        if work > int(world["max_work_units"]):
            raise ValueError("realized work budget exceeded")

    target = _cell_targets(world, cells, float(world["final_time"]))
    l1_error = float(np.mean(np.abs(state - target)))
    lower, upper = _profile_bounds(world)
    scale = max(upper - lower, SPEED_FLOOR)
    overshoot = max(float(np.max(state)) - upper, lower - float(np.min(state)), 0.0)
    tv_growth = max(_total_variation(state, world) - initial_tv, 0.0) / max(
        initial_tv, SPEED_FLOOR
    )
    if world["boundary"] == "periodic":
        balance = abs(float(np.mean(state)) - initial_mass)
    else:
        balance = abs(float(np.mean(state)) - initial_mass + boundary_integral)
    accuracy = math.exp(-l1_error / float(world["accuracy_scale"]))
    stability = math.exp(-18.0 * overshoot / scale - 4.0 * tv_growth)
    conservation = math.exp(-balance / 1.0e-11)
    cost = 1.0 / (1.0 + work / float(world["max_work_units"]))
    raw = sum(
        weight * value
        for weight, value in zip(
            UTILITY_WEIGHTS, (accuracy, stability, conservation, cost)
        )
    )
    return {
        "id": world["id"],
        "split": world["split"],
        "regime": "smooth"
        if world["initial"]["kind"] in {"sine", "multisine", "gaussian"}
        else "shock",
        "l1_error": l1_error,
        "conservation_error": balance,
        "work_units": work,
        "raw_utility": raw,
    }


def _aggregate(rows):
    means = {}
    for regime in ("smooth", "shock"):
        selected = [row["raw_utility"] for row in rows if row["regime"] == regime]
        means[regime] = sum(selected) / len(selected)
    return sum(REGIME_WEIGHTS[regime] * means[regime] for regime in means)


def evaluate_method(method):
    rows = [_run(method, world) for world in WORLDS]
    development = [row for row in rows if row["split"] == "development"]
    heldout = [row for row in rows if row["split"] == "heldout"]
    return {
        "per_world": rows,
        "development_raw_utility": _aggregate(development),
        "heldout_raw_utility": _aggregate(heldout),
    }
