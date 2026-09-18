"""Truth-blind confined fit with fixed residual-threshold attribution."""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import least_squares
from scipy.special import exp1


CHI2_CUT = 2.0
RADIAL_CUT = -3.0
TEMPORAL_CUT = -4.0


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


def infer_aquifer(problem, measure):
    rows = []
    for radius_index in (0, 3):
        radius = problem["observation_radii_m"][radius_index]
        for time in problem["observation_times_s"][1:7]:
            rows.append(measure(radius, time))

    radius = np.asarray([row["radius_m"] for row in rows], dtype=float)
    time = np.asarray([row["time_s"] for row in rows], dtype=float)
    drawdown = np.asarray([row["drawdown_m"] for row in rows], dtype=float)
    sigma = np.asarray(
        [row["drawdown_standard_error_m"] for row in rows], dtype=float
    )
    pumping_rate = float(problem["pumping_rate_m3_s"])
    rss, theta = _fit_confined(
        radius,
        time,
        drawdown,
        sigma,
        pumping_rate,
        problem["parameter_bounds"],
    )
    fitted = _theis(
        math.exp(theta[0]),
        math.exp(theta[1]),
        radius,
        time,
        pumping_rate,
    )
    residual = ((drawdown - fitted) / sigma).reshape(2, 6)
    radial_contrast = float(np.mean(residual[1] - residual[0]))
    temporal_contrast = float(
        np.mean(residual[:, -2:]) - np.mean(residual[:, :2])
    )

    if rss / len(rows) <= CHI2_CUT:
        diagnosis = "confined"
    elif radial_contrast < RADIAL_CUT:
        diagnosis = "leaky_aquifer"
    elif temporal_contrast < TEMPORAL_CUT:
        diagnosis = "recharge_boundary"
    else:
        diagnosis = "dual_porosity"

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
        "confidence": 0.65,
        "abstain": diagnosis != "confined",
        "evidence_measurement_ids": [row["measurement_id"] for row in rows],
    }
