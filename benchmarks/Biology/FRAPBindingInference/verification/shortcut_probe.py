"""Coarse, optimizer-free model-grid shortcut for FRAPBindingInference."""
from __future__ import annotations

import math

import numpy as np


TIME_INDICES = (1, 2, 3, 4, 5, 6, 7, 9)


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


def _profile_mobile(base, recovery, sigma, bounds):
    mobile = float(np.clip(np.dot(base, recovery) / max(np.dot(base, base), 1e-12), *bounds))
    rss = float(np.sum(np.square((mobile * base - recovery) / sigma)))
    return rss, mobile


def _best_supported(radius, time, recovery, sigma, bounds):
    best = None
    for d in np.geomspace(*bounds["diffusion_coefficient_um2_s"], 12):
        for kon in np.geomspace(*bounds["binding_on_rate_s"], 10):
            for koff in np.geomspace(*bounds["binding_off_rate_s"], 10):
                base = _supported(d, kon, koff, radius, time)
                rss, mobile = _profile_mobile(base, recovery, sigma, bounds["mobile_fraction"])
                if best is None or rss < best[0]:
                    best = (rss, (float(d), mobile, float(kon), float(koff)))
    return best


def _best_anomalous(radius, time, recovery, sigma, bounds):
    best = None
    for d in np.geomspace(*bounds["diffusion_coefficient_um2_s"], 12):
        for alpha in np.linspace(0.42, 0.88, 10):
            scaled = np.power(np.maximum(4.0 * d * time / np.square(radius), 0.0), alpha)
            base = 1.0 - np.exp(-scaled)
            rss, mobile = _profile_mobile(base, recovery, sigma, bounds["mobile_fraction"])
            if best is None or rss < best[0]:
                best = (rss, (float(d), mobile, float(alpha)))
    return best


def _best_two_pools(radius, time, recovery, sigma, bounds):
    best = None
    d_grid = np.geomspace(*bounds["diffusion_coefficient_um2_s"], 12)
    for d1 in d_grid:
        for d2 in d_grid:
            if d2 <= d1:
                continue
            first = np.exp(-4.0 * d1 * time / np.square(radius))
            second = np.exp(-4.0 * d2 * time / np.square(radius))
            for weight in np.linspace(0.15, 0.85, 7):
                base = 1.0 - weight * first - (1.0 - weight) * second
                rss, mobile = _profile_mobile(base, recovery, sigma, bounds["mobile_fraction"])
                if best is None or rss < best[0]:
                    best = (rss, (mobile, float(d1), float(d2), float(weight)))
    return best


def _best_spatial(radius, time, recovery, sigma, bounds):
    best = None
    for d in np.geomspace(*bounds["diffusion_coefficient_um2_s"], 8):
        for kon in np.geomspace(*bounds["binding_on_rate_s"], 6):
            for koff in np.geomspace(*bounds["binding_off_rate_s"], 6):
                for slope in np.linspace(-1.5, 1.5, 7):
                    varying_koff = koff * np.power(radius / 1.5, slope)
                    base = _supported(d, kon, varying_koff, radius, time)
                    rss, mobile = _profile_mobile(base, recovery, sigma, bounds["mobile_fraction"])
                    if best is None or rss < best[0]:
                        best = (rss, (float(d), mobile, float(kon), float(koff), float(slope)))
    return best


def infer_frap_binding(problem, measure):
    radii = (problem["bleach_radii_um"][0], problem["bleach_radii_um"][-1])
    times = [problem["sample_times_s"][index] for index in TIME_INDICES]
    rows = [measure(radius, time) for radius in radii for time in times]
    radius = np.asarray([row["radius_um"] for row in rows], dtype=float)
    time = np.asarray([row["time_s"] for row in rows], dtype=float)
    recovery = np.asarray([row["recovery_fraction"] for row in rows], dtype=float)
    sigma = np.asarray([row["recovery_standard_error"] for row in rows], dtype=float)
    bounds = problem["parameter_bounds"]

    fits = {
        "supported": (_best_supported(radius, time, recovery, sigma, bounds), 4),
        "anomalous_transport": (_best_anomalous(radius, time, recovery, sigma, bounds), 3),
        "two_mobile_pools": (_best_two_pools(radius, time, recovery, sigma, bounds), 4),
        "spatially_varying_binding": (_best_spatial(radius, time, recovery, sigma, bounds), 5),
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
    predicted = mobile * _supported(
        d,
        kon,
        koff,
        np.asarray([context["radius_um"] for context in contexts]),
        np.asarray([context["time_s"] for context in contexts]),
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
