"""Low-dimensional no-fit shortcut probe used by the contribution gate."""
from __future__ import annotations

import numpy as np


def policy(mean_cutoff=1.015, low_fraction_cutoff=0.12, roughness_cutoff=0.46,
           lens_duration=8.0, variable_period=15.0):
    def infer_microlensing(problem, observe):
        rows = [observe(float(time), "r") for time in problem["candidate_times"][:-1]]
        flux = np.asarray([row["flux"] for row in rows])
        times = np.asarray([row["time"] for row in rows])
        mean = float(np.mean(flux))
        low_fraction = float(np.mean(flux < 0.95))
        roughness = float(np.max(np.abs(np.diff(flux, n=2))))
        feature_time = float(times[int(np.argmax(flux))])
        if low_fraction > low_fraction_cutoff and mean > mean_cutoff:
            return {"abstain": True, "confidence": 0.70,
                    "evidence_query_ids": [row["query_id"] for row in rows]}
        if low_fraction > low_fraction_cutoff:
            model, timescale, amplitude = "variable_source", variable_period, 0.45
        elif roughness > roughness_cutoff:
            model, timescale, amplitude = "binary_lens", lens_duration, 0.22
        else:
            model, timescale, amplitude = "point_lens", lens_duration, 0.0
        return {
            "abstain": False, "model": model, "timescale_days": timescale,
            "amplitude": amplitude, "feature_time_days": feature_time,
            "confidence": 0.75, "evidence_query_ids": [row["query_id"] for row in rows],
        }
    return infer_microlensing


def infer_microlensing(problem, observe):
    return policy()(problem, observe)
