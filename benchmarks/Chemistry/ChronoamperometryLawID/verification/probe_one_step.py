"""Low-dimensional shortcut probe: fit every public law to one potential step."""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import least_squares

STEP = 0.15
CHI_SQUARE_PER_DOF_GATE = 3.5
FAMILY_PARAMETER_COUNT = {"cottrell": 1, "bounded": 2, "catalytic": 2,
                          "kinetic": 2, "adsorption": 2, "surface": 3}


def _current_law(family, parameters, potential, time):
    a = parameters[0]
    b = parameters[1] if len(parameters) > 1 else 0.0
    c = parameters[2] if len(parameters) > 2 else 0.0
    phi = 1.0 - math.exp(-3.0 * potential)
    time = np.asarray(time, dtype=float)
    if family == "cottrell":
        return a * phi * time ** -0.5
    if family == "bounded":
        return a * phi * time ** -0.5 * np.tanh(b * time ** -0.5)
    if family == "catalytic":
        from scipy.special import erfc
        return a * phi * time ** -0.5 * np.exp(b * b * time) * erfc(b * np.sqrt(time))
    if family == "kinetic":
        return a * phi * (1.0 - np.exp(-b * math.exp(1.5 * potential) * time))
    if family == "adsorption":
        return a * phi * b * np.exp(-b * time)
    if family == "surface":
        return a * phi * np.exp(-b * time) + c * phi * time ** -0.5
    raise ValueError("unknown family")


def identify_current_law(problem, step, budget_units):
    del budget_units
    bounds = np.asarray(problem["parameter_bounds"], dtype=float)
    time = np.asarray(problem["time_grid_s"], dtype=float)
    measurement = step(STEP)

    def residual(family, parameters):
        predicted = _current_law(family, parameters, measurement["potential"], time)
        return (np.asarray(measurement["current"]) - predicted) / measurement["noise_std"]

    fits = {}
    for family in problem["families"]:
        count = FAMILY_PARAMETER_COUNT[family]
        active = bounds[:count]

        def objective(unit, family=family):
            parameters = active[:, 0] + unit * (active[:, 1] - active[:, 0])
            return residual(family, parameters)

        best = None
        for seed in (0.35, 0.7):
            result = least_squares(objective, np.full(count, seed), bounds=(0.0, 1.0),
                                   max_nfev=300, ftol=1e-10, xtol=1e-10)
            value = float(np.sum(result.fun ** 2))
            if best is None or value < best[0]:
                best = (value, active[:, 0] + result.x * (active[:, 1] - active[:, 0]))
        fits[family] = (best[0] + 2.0 * count, best[0], best[1])

    best_family = min(fits, key=lambda name: fits[name][0])
    chi_square, parameters = fits[best_family][1:]
    dof = max(len(time) - FAMILY_PARAMETER_COUNT[best_family], 1)
    if chi_square / dof > CHI_SQUARE_PER_DOF_GATE:
        return {"family_probabilities": {name: 1.0 / len(problem["families"])
                                         for name in problem["families"]},
                "parameters": None, "abstain": True, "confidence": 0.8}
    scores = {name: -4.0 * fits[name][0] for name in problem["families"]}
    weights = {name: math.exp(score - max(scores.values()))
               for name, score in scores.items()}
    total = sum(weights.values())
    return {"family_probabilities": {name: weight / total
                                      for name, weight in weights.items()},
            "parameters": list(parameters) + [0.0] * (3 - len(parameters)),
            "abstain": False, "confidence": 0.75}
