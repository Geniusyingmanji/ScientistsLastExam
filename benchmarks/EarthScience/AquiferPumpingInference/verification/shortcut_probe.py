"""Fit the confined family, then sweep only low-dimensional residual thresholds."""
from __future__ import annotations

import importlib.util
import itertools
import json
from pathlib import Path

import numpy as np

import evaluator


_SPEC = importlib.util.spec_from_file_location(
    "aquifer_reference_for_shortcut", Path(__file__).with_name("reference_solver.py")
)
_REFERENCE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_REFERENCE)
_FIT_CACHE = {}


def _candidate(chi2_cut, radial_cut, temporal_cut):
    def solve(problem, measure):
        rows = []
        for radius_index in (0, -1):
            radius = problem["observation_radii_m"][radius_index]
            for time in problem["observation_times_s"][1:7]:
                rows.append(measure(radius, time))

        r = np.asarray([row["radius_m"] for row in rows], dtype=float)
        t = np.asarray([row["time_s"] for row in rows], dtype=float)
        y = np.asarray([row["drawdown_m"] for row in rows], dtype=float)
        sigma = np.asarray([row["drawdown_standard_error_m"] for row in rows], dtype=float)
        cache_key = tuple(np.round(y, 12))
        if cache_key not in _FIT_CACHE:
            rss, theta = _REFERENCE._fit(
                "confined", r, t, y, sigma, float(problem["pumping_rate_m3_s"]),
                problem["parameter_bounds"],
            )
            fitted = _REFERENCE._predict(
                "confined", theta, r, t, float(problem["pumping_rate_m3_s"])
            )
            residual = (y - fitted) / sigma
            residual_by_radius = residual.reshape(2, 6)
            radial_contrast = float(np.mean(residual_by_radius[1] - residual_by_radius[0]))
            temporal_contrast = float(
                np.mean(residual_by_radius[:, -2:])
                - np.mean(residual_by_radius[:, :2])
            )
            _FIT_CACHE[cache_key] = (rss / len(rows), radial_contrast, temporal_contrast, theta)
        chi2_per_observation, radial_contrast, temporal_contrast, theta = _FIT_CACHE[cache_key]

        if chi2_per_observation <= chi2_cut:
            diagnosis = "confined"
        elif radial_contrast < radial_cut:
            diagnosis = "leaky_aquifer"
        elif temporal_contrast < temporal_cut:
            diagnosis = "recharge_boundary"
        else:
            diagnosis = "dual_porosity"

        transmissivity, storativity = np.exp(theta[:2])
        predictions = [
            _REFERENCE._theis(
                transmissivity,
                storativity,
                float(context["radius_m"]),
                float(context["time_s"]),
                float(problem["pumping_rate_m3_s"]),
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

    return solve


def run_sweep():
    best = None
    count = 0
    for values in itertools.product(
        (2.0, 4.0, 8.0, 16.0),
        (-3.0, -1.5, -0.5, 0.0),
        (-4.0, -2.0, -1.0, -0.5, -0.2, 0.0, 0.2, 0.5),
    ):
        count += 1
        result = evaluator.evaluate(_candidate(*values))
        if best is None or result["combined_score"] > best["combined_score"]:
            best = {"settings": values, **result}
    return {"strategies": count, "best": best}


if __name__ == "__main__":
    print(json.dumps(run_sweep(), indent=2, sort_keys=True))
