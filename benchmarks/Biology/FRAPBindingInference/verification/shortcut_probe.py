"""Low-dimensional summary-statistic shortcut sweep."""
from __future__ import annotations

import itertools
import math

import numpy as np


TIME_INDICES = (1, 2, 3, 4, 5, 6, 7, 9)


def _supported(parameters, radius, time):
    d, mobile, kon, koff = parameters
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


def _policy(shape_threshold, plateau_threshold, tail_threshold, ordering):
    def candidate(problem, measure):
        radii = np.asarray(problem["bleach_radii_um"], dtype=float)
        times = np.asarray([problem["sample_times_s"][index] for index in TIME_INDICES], dtype=float)
        observations = []
        curves = []
        for radius in radii:
            rows = [measure(float(radius), float(time)) for time in times]
            observations.extend(rows)
            curves.append([row["recovery_fraction"] for row in rows])
        curves = np.asarray(curves, dtype=float)
        plateaus = np.maximum(curves[:, -1], 0.05)
        mobile = float(np.clip(np.median(plateaus), 0.55, 0.99))
        half_times = []
        exponents = []
        for curve, plateau in zip(curves, plateaus):
            target = 0.5 * plateau
            half_times.append(float(times[int(np.argmin(np.abs(curve - target)))]))
            mask = (curve > 0.08 * plateau) & (curve < 0.85 * plateau)
            if np.count_nonzero(mask) >= 2:
                transformed = np.log(np.maximum(-np.log(np.clip(1.0 - curve[mask] / plateau, 1e-6, 0.999999)), 1e-8))
                exponents.append(float(np.polyfit(np.log(times[mask]), transformed, 1)[0]))
        half_times = np.asarray(half_times)
        d_values = np.square(radii) * math.log(2.0) / np.maximum(4.0 * half_times, 1e-8)
        d = float(np.clip(np.median(d_values), 0.08, 2.5))
        shape = float(np.median(exponents)) if exponents else 1.0
        plateau_spread = float(np.ptp(plateaus) / max(np.mean(plateaus), 0.05))
        tail = float(np.mean((plateaus - curves[:, -2]) / plateaus))
        triggered = {
            "anomalous_transport": shape < shape_threshold,
            "spatially_varying_binding": plateau_spread > plateau_threshold,
            "two_mobile_pools": tail > tail_threshold,
        }
        diagnosis = "supported"
        for name in ordering:
            if triggered[name]:
                diagnosis = name
                break
        parameters = (d, mobile, 0.30, 0.12)
        contexts = problem["prediction_contexts"]
        predictions = _supported(
            parameters,
            np.asarray([item["radius_um"] for item in contexts]),
            np.asarray([item["time_s"] for item in contexts]),
        )
        return {
            "diagnosis": diagnosis,
            "diffusion_coefficient_um2_s": d,
            "mobile_fraction": mobile,
            "binding_on_rate_s": 0.30,
            "binding_off_rate_s": 0.12,
            "predicted_recovery": [float(value) for value in predictions],
            "confidence": 0.65,
            "abstain": diagnosis != "supported",
            "evidence_measurement_ids": [row["measurement_id"] for row in observations],
        }
    return candidate


def run(evaluator):
    orders = (
        ("anomalous_transport", "spatially_varying_binding", "two_mobile_pools"),
        ("two_mobile_pools", "anomalous_transport", "spatially_varying_binding"),
        ("spatially_varying_binding", "two_mobile_pools", "anomalous_transport"),
    )
    records = []
    for shape, plateau, tail, ordering in itertools.product(
            (0.55, 0.68, 0.81, 0.94),
            (0.015, 0.035, 0.060, 0.100),
            (0.015, 0.035, 0.070, 0.120),
            orders):
        result = evaluator.evaluate(_policy(shape, plateau, tail, ordering))
        records.append({
            "shape_threshold": shape,
            "plateau_threshold": plateau,
            "tail_threshold": tail,
            "ordering": ordering,
            "development": result["development_combined_score"],
            "heldout": result["heldout_combined_score"],
            "development_false_discovery_rate": result["development_false_discovery_rate"],
            "heldout_false_discovery_rate": result["heldout_false_discovery_rate"],
            "development_correct_refusal_rate": result["development_correct_refusal_rate"],
            "heldout_correct_refusal_rate": result["heldout_correct_refusal_rate"],
        })
    return max(records, key=lambda row: (row["development"], row["heldout"]))


if __name__ == "__main__":
    import evaluator
    print(run(evaluator))
