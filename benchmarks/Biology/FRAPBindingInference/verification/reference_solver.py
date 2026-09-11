"""Truth-blind multi-family fit for FRAPBindingInference."""
from __future__ import annotations

import math

import numpy as np


MEASURE_TIME_INDICES = (1, 2, 3, 4, 5, 6, 7, 9)


def _supported(parameters, radius, time):
    d = float(parameters[0])
    mobile = float(parameters[1])
    kon = float(parameters[2])
    koff = np.asarray(parameters[3], dtype=float)
    radius = np.asarray(radius, dtype=float)
    time = np.asarray(time, dtype=float)
    lam = 4.0 * d / np.square(radius)
    free_fraction = koff / (kon + koff)
    trace = lam + kon + koff
    discriminant = np.sqrt(np.maximum(trace * trace - 4.0 * lam * koff, 1e-14))
    fast = 0.5 * (trace + discriminant)
    slow = 0.5 * (trace - discriminant)
    weight = (lam * free_fraction - slow) / discriminant
    deficit = weight * np.exp(-fast * time) + (1.0 - weight) * np.exp(-slow * time)
    return np.clip(mobile * (1.0 - deficit), 0.0, 1.0)


def _anomalous(parameters, radius, time):
    d, mobile, alpha = [float(value) for value in parameters]
    scaled = np.power(np.maximum(4.0 * d * np.asarray(time) / np.square(radius), 0.0), alpha)
    return np.clip(mobile * (1.0 - np.exp(-scaled)), 0.0, 1.0)


def _two_pools(parameters, radius, time):
    mobile, d1, d2, weight = [float(value) for value in parameters]
    radius = np.asarray(radius, dtype=float)
    time = np.asarray(time, dtype=float)
    first = np.exp(-4.0 * d1 * time / np.square(radius))
    second = np.exp(-4.0 * d2 * time / np.square(radius))
    return np.clip(mobile * (1.0 - weight * first - (1.0 - weight) * second), 0.0, 1.0)


def _spatial(parameters, radius, time):
    d, mobile, kon, koff, slope = [float(value) for value in parameters]
    varying_koff = koff * np.power(np.asarray(radius, dtype=float) / 1.5, slope)
    return _supported((d, mobile, kon, varying_koff), radius, time)


def _collect(problem, measure, radii=None, time_indices=MEASURE_TIME_INDICES):
    rows = []
    selected_radii = list(problem["bleach_radii_um"] if radii is None else radii)
    times = problem["sample_times_s"]
    for radius in selected_radii:
        for index in time_indices:
            rows.append(measure(radius, times[index]))
    return rows


def _fit(model, bounds, starts, radius, time, recovery, sigma):
    lower = np.asarray(bounds[0], dtype=float)
    upper = np.asarray(bounds[1], dtype=float)
    width = upper - lower

    def objective(values):
        residual = (model(values, radius, time) - recovery) / sigma
        return float(np.sum(np.square(residual)))

    best = None
    for start in starts:
        values = np.clip(np.asarray(start, dtype=float), lower, upper)
        score = objective(values)
        step = 0.22
        for _ in range(80):
            improved = False
            for index in range(len(values)):
                for direction in (-1.0, 1.0):
                    trial = values.copy()
                    trial[index] = np.clip(
                        trial[index] + direction * step * width[index],
                        lower[index], upper[index],
                    )
                    trial_score = objective(trial)
                    if trial_score + 1e-12 < score:
                        values, score = trial, trial_score
                        improved = True
            if not improved:
                step *= 0.62
                if step < 2e-5:
                    break
        if best is None or score < best[0]:
            best = (score, values)
    return best


def _fits(problem, rows, fixed_rates=None):
    radius = np.asarray([row["radius_um"] for row in rows], dtype=float)
    time = np.asarray([row["time_s"] for row in rows], dtype=float)
    recovery = np.asarray([row["recovery_fraction"] for row in rows], dtype=float)
    sigma = np.asarray([row["recovery_standard_error"] for row in rows], dtype=float)
    bounds = problem["parameter_bounds"]
    d_bounds = bounds["diffusion_coefficient_um2_s"]
    m_bounds = bounds["mobile_fraction"]
    on_bounds = bounds["binding_on_rate_s"]
    off_bounds = bounds["binding_off_rate_s"]
    supported_starts = (
        (0.16, 0.70, 0.08, 0.03),
        (0.35, 0.82, 0.25, 0.08),
        (0.75, 0.88, 0.65, 0.18),
        (1.45, 0.78, 1.20, 0.06),
        (2.10, 0.94, 0.15, 0.55),
    )
    if fixed_rates is None:
        supported_fit = _fit(
            _supported,
            ([d_bounds[0], m_bounds[0], on_bounds[0], off_bounds[0]],
             [d_bounds[1], m_bounds[1], on_bounds[1], off_bounds[1]]),
            supported_starts, radius, time, recovery, sigma,
        )
    else:
        kon, koff = fixed_rates
        model = lambda values, r, t: _supported((values[0], values[1], kon, koff), r, t)
        reduced = _fit(
            model,
            ([d_bounds[0], m_bounds[0]], [d_bounds[1], m_bounds[1]]),
            ((0.2, 0.72), (0.7, 0.85), (1.8, 0.92)), radius, time, recovery, sigma,
        )
        supported_fit = (reduced[0], np.array([reduced[1][0], reduced[1][1], kon, koff]))
    anomalous_fit = _fit(
        _anomalous,
        ([d_bounds[0], m_bounds[0], 0.42], [d_bounds[1], m_bounds[1], 0.88]),
        ((0.2, 0.72, 0.55), (0.65, 0.85, 0.68), (1.7, 0.92, 0.78)),
        radius, time, recovery, sigma,
    )
    two_pool_fit = _fit(
        _two_pools,
        ([m_bounds[0], d_bounds[0], d_bounds[0], 0.12],
         [m_bounds[1], d_bounds[1], d_bounds[1], 0.88]),
        ((0.75, 0.10, 1.0, 0.5), (0.86, 0.18, 1.8, 0.6),
         (0.92, 0.5, 2.3, 0.35), (0.78, 1.4, 0.12, 0.45)),
        radius, time, recovery, sigma,
    )
    spatial_fit = _fit(
        _spatial,
        ([d_bounds[0], m_bounds[0], on_bounds[0], off_bounds[0], -1.6],
         [d_bounds[1], m_bounds[1], on_bounds[1], off_bounds[1], 1.6]),
        tuple(list(start) + [slope] for start, slope in zip(supported_starts, (-1.2, -0.5, 0.0, 0.6, 1.2))),
        radius, time, recovery, sigma,
    )
    count = len(rows)
    candidates = {
        "supported": (supported_fit, 4),
        "anomalous_transport": (anomalous_fit, 3),
        "two_mobile_pools": (two_pool_fit, 4),
        "spatially_varying_binding": (spatial_fit, 5),
    }
    scored = {}
    for name, ((rss, parameters), parameter_count) in candidates.items():
        bic = count * math.log(max(rss / count, 1e-12)) + parameter_count * math.log(count)
        scored[name] = {"rss": rss, "bic": bic, "parameters": parameters}
    return scored


def solve(problem, measure, *, radii=None, time_indices=MEASURE_TIME_INDICES,
          fixed_rates=None, force_supported=False):
    rows = _collect(problem, measure, radii=radii, time_indices=time_indices)
    fitted = _fits(problem, rows, fixed_rates=fixed_rates)
    supported_bic = fitted["supported"]["bic"]
    alternatives = {key: value for key, value in fitted.items() if key != "supported"}
    best_alternative = min(alternatives, key=lambda key: alternatives[key]["bic"])
    improvement = supported_bic - alternatives[best_alternative]["bic"]
    diagnosis = "supported" if force_supported or improvement < 12.0 else best_alternative
    parameters = fitted["supported"]["parameters"]
    predictions = _supported(
        parameters,
        np.asarray([item["radius_um"] for item in problem["prediction_contexts"]]),
        np.asarray([item["time_s"] for item in problem["prediction_contexts"]]),
    )
    confidence = float(np.clip(0.72 + min(abs(improvement), 24.0) / 120.0, 0.72, 0.92))
    return {
        "diagnosis": diagnosis,
        "diffusion_coefficient_um2_s": float(parameters[0]),
        "mobile_fraction": float(parameters[1]),
        "binding_on_rate_s": float(parameters[2]),
        "binding_off_rate_s": float(parameters[3]),
        "predicted_recovery": [float(value) for value in predictions],
        "confidence": confidence,
        "abstain": diagnosis != "supported",
        "evidence_measurement_ids": [row["measurement_id"] for row in rows],
    }


def infer_frap_binding(problem, measure):
    return solve(problem, measure)
