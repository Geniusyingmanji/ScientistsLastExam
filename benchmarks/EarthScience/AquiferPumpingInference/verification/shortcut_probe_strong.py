"""Strong low-dimensional residual probe without alternative-model fitting."""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import least_squares
from scipy.special import exp1


def _theis(transmissivity, storativity, radius, time, pumping_rate):
    u = radius * radius * storativity / (4.0 * transmissivity * time)
    return pumping_rate * exp1(u) / (4.0 * math.pi * transmissivity)


def _fit_confined(radius, time, drawdown, sigma, pumping_rate, bounds):
    lower = np.log([
        bounds["transmissivity_m2_s"][0],
        bounds["storativity"][0],
    ])
    upper = np.log([
        bounds["transmissivity_m2_s"][1],
        bounds["storativity"][1],
    ])
    starts = (
        np.log([0.0007, 0.00015]),
        np.log([0.0020, 0.0010]),
        np.log([0.0060, 0.0060]),
    )
    best = None
    for start in starts:
        fit = least_squares(
            lambda theta: (
                _theis(
                    math.exp(theta[0]),
                    math.exp(theta[1]),
                    radius,
                    time,
                    pumping_rate,
                )
                - drawdown
            )
            / sigma,
            start,
            bounds=(lower, upper),
            max_nfev=900,
        )
        rss = float(np.sum(fit.fun * fit.fun))
        if best is None or rss < best[0]:
            best = (rss, fit.x)
    return best


def _infer(problem, measure, radius_indices=(1, 4)):
    rows = []
    for radius_index in radius_indices:
        radius = problem["observation_radii_m"][radius_index]
        for time in problem["observation_times_s"][1:7]:
            rows.append(measure(radius, time))

    radius = np.asarray([row["radius_m"] for row in rows], dtype=float)
    time = np.asarray([row["time_s"] for row in rows], dtype=float)
    drawdown = np.asarray([row["drawdown_m"] for row in rows], dtype=float)
    sigma = np.asarray([row["drawdown_standard_error_m"] for row in rows], dtype=float)
    pumping_rate = float(problem["pumping_rate_m3_s"])
    rss, theta = _fit_confined(
        radius, time, drawdown, sigma, pumping_rate, problem["parameter_bounds"]
    )
    fitted = _theis(
        np.exp(theta[0]), np.exp(theta[1]), radius, time, pumping_rate
    )
    residual = ((drawdown - fitted) / sigma).reshape(2, 6)
    radial = float(np.mean(residual[1] - residual[0]))
    curvature = float(
        np.mean(residual[:, 2:4])
        - 0.5 * np.mean(residual[:, :2])
        - 0.5 * np.mean(residual[:, -2:])
    )

    if rss / len(rows) <= 2.0 and radial <= 0.8 and curvature <= 1.0:
        diagnosis = "confined"
    elif radial > 0.8 or (curvature > 1.0 and radial > 0.0):
        diagnosis = "dual_porosity"
    elif curvature > 0.60 * abs(radial):
        diagnosis = "recharge_boundary"
    else:
        diagnosis = "leaky_aquifer"

    transmissivity, storativity = np.exp(theta)
    predictions = [
        _theis(
            transmissivity,
            storativity,
            float(context["radius_m"]),
            float(context["time_s"]),
            pumping_rate,
        )
        for context in problem["prediction_contexts"]
    ]
    return {
        "diagnosis": diagnosis,
        "transmissivity_m2_s": float(transmissivity),
        "storativity": float(storativity),
        "predicted_drawdown_m": [float(value) for value in predictions],
        "confidence": 0.75,
        "abstain": diagnosis != "confined",
        "evidence_measurement_ids": [row["measurement_id"] for row in rows],
    }


def infer_aquifer(problem, measure):
    return _infer(problem, measure)
