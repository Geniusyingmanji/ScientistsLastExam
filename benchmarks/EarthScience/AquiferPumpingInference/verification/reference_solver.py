"""Truth-blind multi-model pumping-test reference."""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import least_squares
from scipy.special import exp1


def _theis(T, S, r, t, q):
    u = r * r * S / (4.0 * T * t)
    return q * exp1(u) / (4.0 * math.pi * T)


def _predict(kind, theta, r, t, q):
    T, S = np.exp(theta[:2])
    base = _theis(T, S, r, t, q)
    if kind == "confined":
        return base
    if kind == "leaky_aquifer":
        return base * np.exp(-r / np.exp(theta[2]))
    if kind == "recharge_boundary":
        image = np.sqrt(r * r + (2.0 * np.exp(theta[2])) ** 2)
        return np.maximum(0.0, base - _theis(T, S, image, t, q))
    ratio, delay = np.exp(theta[2:4])
    weight = 1.0 / (1.0 + np.exp(-theta[4]))
    slow = _theis(T, S * ratio, r, t / delay, q)
    return weight * base + (1.0 - weight) * slow


def _fit(kind, r, t, y, sigma, q, bounds):
    lower = [math.log(bounds["transmissivity_m2_s"][0]), math.log(bounds["storativity"][0])]
    upper = [math.log(bounds["transmissivity_m2_s"][1]), math.log(bounds["storativity"][1])]
    starts = [
        [math.log(0.0005), math.log(0.00008)],
        [math.log(0.0008), math.log(0.0015)],
        [math.log(0.0020), math.log(0.0003)],
        [math.log(0.0040), math.log(0.0040)],
        [math.log(0.0080), math.log(0.0010)],
    ]
    if kind in ("leaky_aquifer", "recharge_boundary"):
        lower += [math.log(35.0)]
        upper += [math.log(500.0)]
        starts = [s + [math.log(v)] for s, v in zip(
            starts, (70.0, 140.0, 230.0, 350.0, 470.0)
        )]
    elif kind == "dual_porosity":
        lower += [math.log(3.0), math.log(2.0), -2.0]
        upper += [math.log(40.0), math.log(12.0), 2.0]
        starts = [s + [math.log(ra), math.log(de), w] for s, ra, de, w in zip(
            starts, (3.5, 5.0, 7.0, 10.0, 20.0),
            (2.2, 3.0, 4.0, 5.5, 8.0), (-1.0, -0.4, 0.2, 0.8, 1.4))]
    best = None
    for start in starts:
        fit = least_squares(lambda p: (_predict(kind, p, r, t, q) - y) / sigma,
                            start, bounds=(lower, upper), max_nfev=900)
        rss = float(np.sum(fit.fun * fit.fun))
        if best is None or rss < best[0]:
            best = (rss, fit.x)
    return best


def _infer(problem, measure, radius_indices=(1, 3), time_indices=None, repeats=1,
           allow_refusal=True, fixed_storage=None):
    rows = []
    # Two radius setups and twelve measurements consume all 24 priced units.
    if time_indices is None:
        time_indices = range(1, 7)
    for radius_index in radius_indices:
        radius = problem["observation_radii_m"][radius_index]
        for time_index in time_indices:
            time = problem["observation_times_s"][time_index]
            for _ in range(repeats):
                rows.append(measure(radius, time))
    r = np.asarray([row["radius_m"] for row in rows], dtype=float)
    t = np.asarray([row["time_s"] for row in rows], dtype=float)
    y = np.asarray([row["drawdown_m"] for row in rows], dtype=float)
    sigma = np.asarray([row["drawdown_standard_error_m"] for row in rows], dtype=float)
    q = float(problem["pumping_rate_m3_s"])
    bounds = problem["parameter_bounds"]
    fits = {kind: _fit(kind, r, t, y, sigma, q, bounds)
            for kind in ("confined", "leaky_aquifer", "recharge_boundary", "dual_porosity")}
    parameter_counts = {"confined": 2, "leaky_aquifer": 3, "recharge_boundary": 3, "dual_porosity": 5}
    bic = {kind: value[0] + parameter_counts[kind] * math.log(len(rows)) for kind, value in fits.items()}
    best = min(bic, key=bic.get)
    confined_theta = fits["confined"][1]
    T, S = np.exp(confined_theta[:2])
    if fixed_storage is not None:
        S = float(fixed_storage)
    margin = (sorted(bic.values())[1] - sorted(bic.values())[0]) / 20.0
    if not allow_refusal:
        best = "confined"
    prediction_theta = fits[best][1].copy()
    if fixed_storage is not None:
        prediction_theta[1] = math.log(S)
    predictions = [
        _predict(
            best,
            prediction_theta,
            float(ctx["radius_m"]),
            float(ctx["time_s"]),
            q,
        )
        for ctx in problem["prediction_contexts"]
    ]
    return {
        "diagnosis": best,
        "transmissivity_m2_s": float(T),
        "storativity": float(S),
        "predicted_drawdown_m": [float(v) for v in predictions],
        "confidence": float(np.clip(0.55 + margin, 0.0, 0.95)),
        "abstain": best != "confined",
        "evidence_measurement_ids": [row["measurement_id"] for row in rows],
    }


def infer_aquifer(problem, measure):
    return _infer(problem, measure)
