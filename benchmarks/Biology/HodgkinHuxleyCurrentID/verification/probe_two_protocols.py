"""Low-budget shortcut probe: the public reference fit with only two clamps."""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import least_squares

PROTOCOLS = ((-40.0, 20.0), (-20.0, 20.0))
MISFIT_GATE = 6.0
HOLDING = -80.0
SAMPLE_DT = 0.25


def _x_over_expm1(x):
    if abs(x) < 1e-7:
        return 1.0 - 0.5 * x
    return x / math.expm1(x)


def _rates(v):
    return (
        _x_over_expm1((25.0 - v) / 10.0), 4.0 * math.exp(-v / 18.0),
        0.07 * math.exp(-v / 20.0), 1.0 / (math.exp((30.0 - v) / 10.0) + 1.0),
        0.1 * _x_over_expm1((10.0 - v) / 10.0), 0.125 * math.exp(-v / 80.0),
    )


def _relax(step_rates, hold_rates, time):
    a_step, b_step = step_rates
    a_hold, b_hold = hold_rates
    steady = a_step / (a_step + b_step)
    start = a_hold / (a_hold + b_hold)
    return steady + (start - steady) * np.exp(-(a_step + b_step) * time)


def _current(parameters, voltage, duration):
    s_na, s_k = parameters[6], parameters[7]
    time = np.arange(1, int(round(duration / SAMPLE_DT)) + 1) * SAMPLE_DT
    rates_na = _rates(voltage + 65.0 - s_na)
    hold_na = _rates(HOLDING + 65.0 - s_na)
    rates_k = _rates(voltage + 65.0 - s_k)
    hold_k = _rates(HOLDING + 65.0 - s_k)
    m = _relax(rates_na[0:2], hold_na[0:2], time)
    h = _relax(rates_na[2:4], hold_na[2:4], time)
    n = _relax(rates_k[4:6], hold_k[4:6], time)
    g_na, g_k, g_l, e_na, e_k, e_l = parameters[:6]
    return (g_na * m ** 3 * h * (voltage - e_na)
            + g_k * n ** 4 * (voltage - e_k)
            + g_l * (voltage - e_l))


def recover_channel_parameters(problem, voltage_step, budget_units):
    del budget_units
    traces = [voltage_step(voltage, duration) for voltage, duration in PROTOCOLS]
    bounds = np.asarray(problem["parameter_bounds"], dtype=float)
    low, high = bounds[:, 0], bounds[:, 1]

    def residual(unit):
        parameters = low + unit * (high - low)
        return np.concatenate([
            (np.asarray(row["current"]) - _current(parameters, voltage, duration))
            / row["noise_std"]
            for row, (voltage, duration) in zip(traces, PROTOCOLS)
        ])

    classic = np.asarray([120.0, 36.0, 0.3, 50.0, -77.0, -54.4, 0.0, 0.0])
    starts = [np.full(8, level) for level in (0.2, 0.35, 0.5, 0.65)]
    starts.append(np.clip((classic - low) / (high - low), 0.0, 1.0))
    best = None
    for start in starts:
        result = least_squares(residual, start, bounds=(0.0, 1.0),
                               max_nfev=260, ftol=1e-11, xtol=1e-11)
        value = float(np.sum(result.fun ** 2))
        if best is None or value < best[0]:
            best = (value, low + result.x * (high - low))
    dof = max(sum(len(np.asarray(row["current"])) for row in traces) - 8, 1)
    if best[0] / dof > MISFIT_GATE:
        return {"parameters": None, "abstain": True, "confidence": 0.8}
    return {"parameters": [float(value) for value in best[1]],
            "abstain": False, "confidence": 0.75}
