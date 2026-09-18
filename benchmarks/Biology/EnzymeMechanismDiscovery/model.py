"""Public effective kinetic model; contains no world generation or answers.

Concentrations are mM and time is minutes. Optional terms compose: this is
not a claim that these effective rates identify a unique microscopic scheme.
"""
from __future__ import annotations

import numpy as np
from scipy.integrate import solve_ivp


MODULES = ("product_feedback", "substrate_inhibition", "enzyme_decay")
CHANNELS = ("substrate", "intermediate", "product")
PARAMETERS = ("kcat", "km", "k2", "ki", "ks", "kd")
MODULE_PARAMETER = dict(zip(MODULES, ("ki", "ks", "kd")))


def rate(parameters, substrate, product, enzyme):
    """Substrate disappearance rate, not instantaneous product appearance."""
    denominator = parameters["km"] + substrate
    if parameters["ki"] is not None:
        denominator += parameters["km"] * product / parameters["ki"]
    if parameters["ks"] is not None:
        denominator += substrate * substrate / parameters["ks"]
    return parameters["kcat"] * enzyme * substrate / denominator


def simulate(parameters, design, rtol=2e-7, atol=2e-9):
    """Return all three species at sample times; pulse-time samples are post-pulse.

    Integration is restarted at pulses, so a discontinuity is never hidden
    inside an adaptive ODE step. Enzyme loss is integrated analytically.
    """
    times = np.asarray(design["times"], dtype=float)
    initial = design["initial"]
    pulse = design.get("pulse")
    pulse_time = float(pulse["time"]) if pulse else float("inf")
    kd = float(parameters["kd"] or 0.0)
    y = np.array([initial["substrate"], 0.0, initial["product"]], dtype=float)
    rows = []
    start = 0.0
    applied = False

    def derivative(t, state):
        enzyme = initial["enzyme"] * np.exp(-kd * t)
        if applied and pulse["species"] == "enzyme":
            enzyme += pulse["amount"] * np.exp(-kd * (t - pulse_time))
        # Roundoff may put a depleted substrate microscopically below zero.
        substrate, intermediate, product = np.maximum(state, 0.0)
        v1 = rate(parameters, substrate, product, enzyme)
        v2 = parameters["k2"] * intermediate
        return [-v1, v1 - v2, v2]

    def advance(end, selected):
        nonlocal y, start
        if end > start:
            solved = solve_ivp(derivative, (start, end), y, t_eval=selected,
                               rtol=rtol, atol=atol, dense_output=True)
            if not solved.success:
                raise RuntimeError("kinetic integrator failed")
            if len(selected):
                rows.extend(solved.y.T.tolist())
            y = solved.sol(end)
            start = end
        elif len(selected):
            rows.extend([y.tolist() for _ in selected])

    if pulse_time <= times[-1]:
        advance(pulse_time, times[times < pulse_time])
        if pulse["species"] != "enzyme":
            y[CHANNELS.index(pulse["species"])] += pulse["amount"]
        applied = True
        # solve_ivp accepts its initial time among t_eval values.
        advance(float(times[-1]), times[times >= pulse_time])
    else:
        advance(float(times[-1]), times)
    result = np.asarray(rows, dtype=float)
    if result.shape != (len(times), 3) or not np.all(np.isfinite(result)):
        raise RuntimeError("kinetic integrator returned invalid trajectory")
    return result
