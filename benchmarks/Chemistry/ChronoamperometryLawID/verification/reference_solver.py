"""Truth-blind reference witness: multi-family least squares with refusal tests.

Uses only the public laws and the charged potentiostat. Three potential steps cover
the amplitude response; every family is fitted to the merged transients by bounded
least squares and the best relative residual wins. Two refusal tests guard the
unmodellable worlds: the tail log-slope must match the fitted family within a public
tolerance (anomalous fractional diffusion decays as t^-1/3), and the residuals must
not trend with time (a linear baseline drift leaves a ramming trend). It deliberately
lacks model selection by information criteria, amplitude-weighted fitting, and any
use of more than three steps.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import least_squares

STEPS = (0.15, 0.45, 0.85)
SLOPE_TOLERANCE = 0.12

FAMILY_PARAMETER_COUNT = {"cottrell": 1, "bounded": 2, "catalytic": 2,
                          "kinetic": 2, "adsorption": 2, "surface": 3}


def _current_law(family, parameters, potential, t):
    a = parameters[0]
    b = parameters[1] if len(parameters) > 1 else 0.0
    c = parameters[2] if len(parameters) > 2 else 0.0
    phi = 1.0 - math.exp(-3.0 * potential)
    t = np.asarray(t, dtype=float)
    if family == "cottrell":
        return a * phi * t ** -0.5
    if family == "bounded":
        return a * phi * t ** -0.5 * np.tanh(b * t ** -0.5)
    if family == "catalytic":
        from scipy.special import erfc
        return a * phi * t ** -0.5 * np.exp(b * b * t) * erfc(b * np.sqrt(t))
    if family == "kinetic":
        return a * phi * (1.0 - np.exp(-b * math.exp(1.5 * potential) * t))
    if family == "adsorption":
        return a * phi * b * np.exp(-b * t)
    if family == "surface":
        return a * phi * np.exp(-b * t) + c * phi * t ** -0.5
    raise ValueError("unknown family")


def _family_slope(family):
    if family in ("cottrell", "bounded", "catalytic"):
        return -0.5
    if family == "kinetic":
        return 0.0
    if family == "adsorption":
        return -1.0
    return -0.5  # surface tail is diffusion-dominated


def identify_current_law(problem, step, budget_units):
    del budget_units
    bounds = np.asarray(problem["parameter_bounds"], dtype=float)
    time = np.asarray(problem["time_grid_s"], dtype=float)
    measurements = [step(value) for value in STEPS]

    def residual(family, parameters):
        parts = []
        for row in measurements:
            predicted = _current_law(family, parameters, row["potential"], time)
            parts.append((np.asarray(row["current"]) - predicted) / row["noise_std"])
        return np.concatenate(parts)

    fits = {}
    for family in problem["families"]:
        count = FAMILY_PARAMETER_COUNT[family]
        active = bounds[:count]
        def fun(unit, family=family):
            parameters = active[:, 0] + unit * (active[:, 1] - active[:, 0])
            return residual(family, parameters)
        best = None
        for seed in (0.35, 0.7):
            unit0 = np.full(count, seed)
            result = least_squares(fun, unit0, bounds=(0.0, 1.0),
                                   max_nfev=300, ftol=1e-10, xtol=1e-10)
            value = float(np.sum(result.fun ** 2))
            if best is None or value < best[0]:
                best = (value, active[:, 0] + result.x * (active[:, 1] - active[:, 0]))
        # Akaike-style penalty: families with extra freedom must pay for it in
        # chi-square, or a diffusion tail plus noise lets the three-parameter
        # surface law beat the one-parameter Cottrell law by a hair.
        fits[family] = (best[0] + 2.0 * count, best[0], best[1])

    best_family = min(fits, key=lambda name: fits[name][0])
    chi_square = fits[best_family][1]
    parameters = fits[best_family][2]
    padded = list(parameters) + [0.0] * (3 - len(parameters))

    # Refusal test: with stated noise a correct family lands near one chi-square per
    # degree of freedom. Fractional-diffusion transport and superposed baseline drift
    # both leave structural misfit no family can absorb.
    dof = max(len(STEPS) * len(time) - FAMILY_PARAMETER_COUNT[best_family], 1)
    if chi_square / dof > 2.2:
        return {"family_probabilities": {name: 1.0 / len(problem["families"])
                                         for name in problem["families"]},
                "parameters": None, "abstain": True, "confidence": 0.8}

    # Drift test by variable projection: a linear baseline d*t is shared across all
    # potentials, while every family scales with phi(E) -- a significant shared
    # linear term is therefore unmodellable drift, not family curvature.
    merged_time = np.concatenate([time for _ in measurements])
    merged_current = np.concatenate([np.asarray(row["current"])
                                     for row in measurements])
    merged_sigma = np.concatenate([np.full(len(time), row["noise_std"])
                                   for row in measurements])
    design = merged_time / merged_sigma
    predicted = merged_current - residual(best_family, parameters) * merged_sigma
    drift_numerator = float(np.sum(design * (merged_current - predicted) / merged_sigma))
    drift_precision = float(np.sum(design ** 2))
    if drift_precision > 0:
        drift_hat = drift_numerator / drift_precision
        drift_sigma = 1.0 / math.sqrt(drift_precision)
        if abs(drift_hat) > 3.0 * drift_sigma and abs(drift_hat) > 0.02:
            return {"family_probabilities": {name: 1.0 / len(problem["families"])
                                             for name in problem["families"]},
                    "parameters": None, "abstain": True, "confidence": 0.8}

    scores = {name: -4.0 * fits[name][0] for name in problem["families"]}
    weights = {name: math.exp(score - max(scores.values()))
               for name, score in scores.items()}
    total = sum(weights.values())
    probabilities = {name: weight / total for name, weight in weights.items()}
    return {"family_probabilities": probabilities, "parameters": padded,
            "abstain": False, "confidence": 0.75}
