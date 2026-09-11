"""Coarse, optimizer-free model-grid shortcut for FRAPBindingInference."""
from __future__ import annotations

import math

import numpy as np


TIME_INDICES = (3, 6, 7, 9)
GRID_LADDER = {
    # Number of candidate points is the sum of the four family grids.
    "coarse": {"d": 12, "on": 10, "off": 10, "alpha": 10, "weight": 7, "slope": 7},  # 3,798
    "medium": {"d": 16, "on": 14, "off": 14, "alpha": 14, "weight": 9, "slope": 9},  # 15,240
    "fine": {"d": 18, "on": 16, "off": 16, "alpha": 16, "weight": 10, "slope": 10},  # 26,586
}


def _supported(d, kon, koff, radius, time):
    lam = 4.0 * d / np.square(radius)
    free_fraction = koff / (kon + koff)
    trace = lam + kon + koff
    discriminant = np.sqrt(np.maximum(trace * trace - 4.0 * lam * koff, 1e-14))
    fast = 0.5 * (trace + discriminant)
    slow = 0.5 * (trace - discriminant)
    weight = (lam * free_fraction - slow) / discriminant
    deficit = weight * np.exp(-fast * time) + (1.0 - weight) * np.exp(-slow * time)
    return np.clip(1.0 - deficit, 0.0, 1.0)


def _anomalous(d, alpha, radius, time):
    scaled = np.power(np.maximum(4.0 * d * time / np.square(radius), 0.0), alpha)
    return np.clip(1.0 - np.exp(-scaled), 0.0, 1.0)


def _two_pools(d1, d2, weight, radius, time):
    first = np.exp(-4.0 * d1 * time / np.square(radius))
    second = np.exp(-4.0 * d2 * time / np.square(radius))
    return np.clip(1.0 - weight * first - (1.0 - weight) * second, 0.0, 1.0)


def _profile_mobile(base, recovery, sigma, bounds):
    mobile = float(np.clip(np.dot(base, recovery) / max(np.dot(base, base), 1e-12), *bounds))
    rss = float(np.sum(np.square((mobile * base - recovery) / sigma)))
    return rss, mobile


def _best_supported(radius, time, recovery, sigma, bounds, grid):
    best = None
    for d in np.geomspace(*bounds["diffusion_coefficient_um2_s"], grid["d"]):
        for kon in np.geomspace(*bounds["binding_on_rate_s"], grid["on"]):
            for koff in np.geomspace(*bounds["binding_off_rate_s"], grid["off"]):
                base = _supported(d, kon, koff, radius, time)
                rss, mobile = _profile_mobile(base, recovery, sigma, bounds["mobile_fraction"])
                if best is None or rss < best[0]:
                    best = (rss, (float(d), mobile, float(kon), float(koff)))
    return best


def _best_anomalous(radius, time, recovery, sigma, bounds, grid):
    best = None
    for d in np.geomspace(*bounds["diffusion_coefficient_um2_s"], grid["d"]):
        for alpha in np.linspace(0.42, 0.88, grid["alpha"]):
            scaled = np.power(np.maximum(4.0 * d * time / np.square(radius), 0.0), alpha)
            base = 1.0 - np.exp(-scaled)
            rss, mobile = _profile_mobile(base, recovery, sigma, bounds["mobile_fraction"])
            if best is None or rss < best[0]:
                best = (rss, (float(d), mobile, float(alpha)))
    return best


def _best_two_pools(radius, time, recovery, sigma, bounds, grid):
    best = None
    d_grid = np.geomspace(*bounds["diffusion_coefficient_um2_s"], grid["d"])
    for d1 in d_grid:
        for d2 in d_grid:
            if d2 <= d1:
                continue
            first = np.exp(-4.0 * d1 * time / np.square(radius))
            second = np.exp(-4.0 * d2 * time / np.square(radius))
            for weight in np.linspace(0.15, 0.85, grid["weight"]):
                base = 1.0 - weight * first - (1.0 - weight) * second
                rss, mobile = _profile_mobile(base, recovery, sigma, bounds["mobile_fraction"])
                if best is None or rss < best[0]:
                    best = (rss, (mobile, float(d1), float(d2), float(weight)))
    return best


def _best_spatial(radius, time, recovery, sigma, bounds, grid):
    best = None
    for d in np.geomspace(*bounds["diffusion_coefficient_um2_s"], grid["d"] - 4):
        for kon in np.geomspace(*bounds["binding_on_rate_s"], grid["on"] - 4):
            for koff in np.geomspace(*bounds["binding_off_rate_s"], grid["off"] - 4):
                for slope in np.linspace(-1.5, 1.5, grid["slope"]):
                    varying_koff = koff * np.power(radius / 1.5, slope)
                    base = _supported(d, kon, varying_koff, radius, time)
                    rss, mobile = _profile_mobile(base, recovery, sigma, bounds["mobile_fraction"])
                    if best is None or rss < best[0]:
                        best = (rss, (float(d), mobile, float(kon), float(koff), float(slope)))
    return best


def infer_frap_binding_at_resolution(problem, measure, resolution):
    grid = GRID_LADDER[resolution]
    radii = (problem["bleach_radii_um"][0], problem["bleach_radii_um"][-1])
    times = [problem["sample_times_s"][index] for index in TIME_INDICES]
    rows = [measure(radius, time) for radius in radii for time in times]
    radius = np.asarray([row["radius_um"] for row in rows], dtype=float)
    time = np.asarray([row["time_s"] for row in rows], dtype=float)
    recovery = np.asarray([row["recovery_fraction"] for row in rows], dtype=float)
    sigma = np.asarray([row["recovery_standard_error"] for row in rows], dtype=float)
    bounds = problem["parameter_bounds"]

    fits = {
        "supported": (_best_supported(radius, time, recovery, sigma, bounds, grid), 4),
        "anomalous_transport": (_best_anomalous(radius, time, recovery, sigma, bounds, grid), 3),
        "two_mobile_pools": (_best_two_pools(radius, time, recovery, sigma, bounds, grid), 4),
        "spatially_varying_binding": (_best_spatial(radius, time, recovery, sigma, bounds, grid), 5),
    }
    count = len(rows)
    bic = {
        name: count * math.log(max(fit[0] / count, 1e-12)) + parameters * math.log(count)
        for name, (fit, parameters) in fits.items()
    }
    best_alternative = min((name for name in fits if name != "supported"), key=bic.get)
    diagnosis = best_alternative if bic["supported"] - bic[best_alternative] >= 12.0 else "supported"
    d, mobile, kon, koff = fits["supported"][0][1]
    contexts = problem["prediction_contexts"]
    context_radius = np.asarray([context["radius_um"] for context in contexts])
    context_time = np.asarray([context["time_s"] for context in contexts])
    if diagnosis == "supported":
        predicted = mobile * _supported(d, kon, koff, context_radius, context_time)
    elif diagnosis == "anomalous_transport":
        alt_d, alt_mobile, alpha = fits[diagnosis][0][1]
        predicted = alt_mobile * _anomalous(alt_d, alpha, context_radius, context_time)
    elif diagnosis == "two_mobile_pools":
        alt_mobile, d1, d2, weight = fits[diagnosis][0][1]
        predicted = alt_mobile * _two_pools(d1, d2, weight, context_radius, context_time)
    else:
        alt_d, alt_mobile, alt_kon, alt_koff, slope = fits[diagnosis][0][1]
        predicted = alt_mobile * _supported(
            alt_d, alt_kon, alt_koff * np.power(context_radius / 1.5, slope),
            context_radius, context_time,
        )
    return {
        "diagnosis": diagnosis,
        "diffusion_coefficient_um2_s": d,
        "mobile_fraction": mobile,
        "binding_on_rate_s": kon,
        "binding_off_rate_s": koff,
        "predicted_recovery": [float(value) for value in predicted],
        "confidence": 0.70,
        "abstain": diagnosis != "supported",
        "evidence_measurement_ids": [row["measurement_id"] for row in rows],
    }


def infer_frap_binding(problem, measure):
    return infer_frap_binding_at_resolution(problem, measure, "coarse")


def resolution_candidate(resolution):
    def candidate(problem, measure):
        return infer_frap_binding_at_resolution(problem, measure, resolution)
    return candidate


def run(evaluator):
    return evaluator.evaluate(infer_frap_binding)


if __name__ == "__main__":
    import evaluator

    result = run(evaluator)
    print({
        "development": result["development_combined_score"],
        "heldout": result["heldout_combined_score"],
        "development_correct_refusal_rate": result["development_correct_refusal_rate"],
        "heldout_correct_refusal_rate": result["heldout_correct_refusal_rate"],
    })
