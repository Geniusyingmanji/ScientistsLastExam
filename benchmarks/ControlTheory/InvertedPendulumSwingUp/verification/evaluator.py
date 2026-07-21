"""Trusted evaluator for nonlinear cart-pole swing-up and robust stabilization.

The public convention is theta=0 hanging down and theta=pi upright. Development scenarios vary
initial conditions on the disclosed nominal plant. Evaluator-only validation scenarios change
plant parameters and add bounded force disturbances. Optimization and robustness are reported
separately; only development utility defines ``combined_score``.
"""

from __future__ import annotations

import math

import numpy as np


G = 9.81
F_MAX = 10.0
DT = 0.02
T_TOTAL = 20.0
N_STEPS = int(round(T_TOTAL / DT))
CART_LIMIT = 5.0
NOMINAL_PLANT = {
    "cart_mass": 1.0,
    "pendulum_mass": 0.1,
    "length": 1.0,
    "cart_friction": 0.05,
    "joint_friction": 0.005,
}

DEVELOPMENT_SCENARIOS = (
    {"initial": (0.0, 0.0, -0.08, 0.0)},
    {"initial": (0.2, 0.0, 0.12, 0.05)},
    {"initial": (-0.2, 0.1, -0.18, -0.05)},
    {"initial": (0.3, -0.1, 0.20, 0.0)},
    {"initial": (0.0, 0.0, 0.0, 0.25)},
)

VALIDATION_SCENARIOS = (
    {
        "initial": (-0.35, 0.15, -0.25, 0.1),
        "plant": (1.10, 0.13, 0.85, 0.04, 0.007),
        "disturbances": ((8.0, 8.2, 3.0),),
    },
    {
        "initial": (0.25, -0.1, 0.28, -0.1),
        "plant": (0.75, 0.07, 1.15, 0.09, 0.003),
        "disturbances": ((12.0, 12.25, -3.0),),
    },
    {
        "initial": (0.0, 0.0, -0.15, 0.2),
        "plant": (1.25, 0.14, 0.75, 0.02, 0.009),
        "disturbances": ((9.0, 9.15, 2.5), (15.0, 15.15, -2.0)),
    },
    {
        "initial": (0.4, 0.0, 0.1, -0.2),
        "plant": (0.85, 0.09, 1.05, 0.07, 0.006),
        "disturbances": ((10.0, 10.2, -2.5),),
    },
)


def _plant_tuple(mapping=NOMINAL_PLANT):
    return (
        float(mapping["cart_mass"]),
        float(mapping["pendulum_mass"]),
        float(mapping["length"]),
        float(mapping["cart_friction"]),
        float(mapping["joint_friction"]),
    )


def wrap_upright_error(theta):
    """Return theta-pi wrapped to [-pi, pi)."""
    return float((float(theta) - math.pi + math.pi) % (2 * math.pi) - math.pi)


def cart_pole_derivative(state, force, plant):
    """Continuous dynamics with theta=0 down and theta=pi upright.

    ``plant`` is ``(cart_mass, pendulum_mass, length, cart_friction, joint_friction)``.
    The equations are the standard cart-pole equations transformed from the common
    upright-zero coordinate into the public down-zero coordinate.
    """
    x, x_dot, theta, theta_dot = np.asarray(state, dtype=float)
    cart_mass, pendulum_mass, length, cart_friction, joint_friction = plant
    sine, cosine = math.sin(theta), math.cos(theta)
    total_mass = cart_mass + pendulum_mass
    intermediate = (
        float(force) - cart_friction * x_dot
        - pendulum_mass * length * theta_dot**2 * sine
    ) / total_mass
    denominator = length * (
        4.0 / 3.0 - pendulum_mass * cosine**2 / total_mass
    )
    theta_acceleration = (
        -G * sine + cosine * intermediate
        - joint_friction * theta_dot / (pendulum_mass * length)
    ) / denominator
    x_acceleration = (
        intermediate
        + pendulum_mass * length * theta_acceleration * cosine / total_mass
    )
    return np.array([x_dot, x_acceleration, theta_dot, theta_acceleration])


def _rk4_step(state, force, plant):
    """Two RK4 substeps per controller interval."""
    step = DT / 2.0
    state = np.asarray(state, dtype=float)
    for _ in range(2):
        k1 = cart_pole_derivative(state, force, plant)
        k2 = cart_pole_derivative(state + 0.5 * step * k1, force, plant)
        k3 = cart_pole_derivative(state + 0.5 * step * k2, force, plant)
        k4 = cart_pole_derivative(state + step * k3, force, plant)
        state = state + step * (k1 + 2 * k2 + 2 * k3 + k4) / 6.0
    return state


def _disturbance_force(scenario, time):
    return float(sum(
        force for start, end, force in scenario.get("disturbances", ())
        if start <= time < end
    ))


def _scenario_utility(controller, scenario, validation=False):
    plant = tuple(scenario.get("plant", _plant_tuple()))
    state = np.asarray(scenario["initial"], dtype=float)
    balanced = 0
    commanded_force_squared = []
    cart_position_squared = []
    terminal_states = []
    first_balance_time = None
    runaway = False

    for index in range(N_STEPS):
        time = index * DT
        command = float(controller(state.copy(), time, DT))
        if not math.isfinite(command):
            raise ValueError("controller returned a non-finite force")
        command = float(np.clip(command, -F_MAX, F_MAX))
        plant_force = command + _disturbance_force(scenario, time)
        state = _rk4_step(state, plant_force, plant)
        commanded_force_squared.append(command**2)
        cart_position_squared.append(float(state[0] ** 2))
        if not np.all(np.isfinite(state)):
            raise ValueError("cart-pole trajectory became non-finite")
        if abs(state[0]) > CART_LIMIT:
            runaway = True
            break

        upright_error = abs(wrap_upright_error(state[2]))
        is_balanced = bool(
            upright_error < 0.20
            and abs(state[3]) < 1.0
            and abs(state[0]) < 2.4
            and abs(state[1]) < 2.0
        )
        if is_balanced and first_balance_time is None:
            first_balance_time = time
        if time >= 5.0 and is_balanced:
            balanced += 1
        if time >= T_TOTAL - 3.0:
            terminal_states.append(state.copy())

    balanced_fraction = balanced / max(1, int(round((T_TOTAL - 5.0) / DT)))
    rms_force = math.sqrt(float(np.mean(commanded_force_squared))) if commanded_force_squared else F_MAX
    rms_cart_position = math.sqrt(float(np.mean(cart_position_squared))) if cart_position_squared else CART_LIMIT
    if terminal_states:
        terminal_loss = float(np.mean([
            wrap_upright_error(row[2]) ** 2
            + 0.10 * row[3] ** 2
            + 0.05 * row[0] ** 2
            + 0.02 * row[1] ** 2
            for row in terminal_states
        ]))
        terminal_score = math.exp(-terminal_loss)
    else:
        terminal_score = 0.0
    effort_factor = math.exp(-0.025 * rms_force**2)
    cart_factor = math.exp(-0.05 * rms_cart_position**2)
    utility = (
        (0.70 * balanced_fraction + 0.30 * terminal_score)
        * effort_factor * cart_factor
    ) if not runaway else 0.0
    return {
        "group": "validation" if validation else "development",
        "utility": float(np.clip(utility, 0.0, 1.0)),
        "balanced_fraction": float(balanced_fraction),
        "terminal_score": float(terminal_score),
        "rms_force": float(rms_force),
        "rms_cart_position": float(rms_cart_position),
        "first_balance_time": (
            None if first_balance_time is None else float(first_balance_time)
        ),
        "runaway": bool(runaway),
    }


def evaluate(swing_up_controller):
    development = [
        _scenario_utility(swing_up_controller, scenario, validation=False)
        for scenario in DEVELOPMENT_SCENARIOS
    ]
    validation = [
        _scenario_utility(swing_up_controller, scenario, validation=True)
        for scenario in VALIDATION_SCENARIOS
    ]
    development_score = float(np.mean([row["utility"] for row in development]))
    robustness_score = float(np.mean([row["utility"] for row in validation]))
    return {
        "combined_score": development_score,
        "valid": 1.0,
        "feasibility_rate": 1.0,
        "raw_score": development_score,
        "development_score": development_score,
        # Evaluator-only shifted scenarios. This remains a diagnostic rather than a strictly
        # sealed metric until every search adapter redacts non-selection metrics.
        "robustness_score": robustness_score,
        "development_robustness_gap": development_score - robustness_score,
        "mean_balanced_fraction": float(np.mean([
            row["balanced_fraction"] for row in development
        ])),
        "mean_rms_force": float(np.mean([row["rms_force"] for row in development])),
        "mean_rms_cart_position": float(np.mean([
            row["rms_cart_position"] for row in development
        ])),
        "per_scenario": development + validation,
    }
