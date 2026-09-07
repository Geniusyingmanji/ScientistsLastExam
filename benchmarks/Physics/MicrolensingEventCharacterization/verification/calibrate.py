"""Reproduce microlensing reference metrics and a low-dimensional shortcut sweep."""
from __future__ import annotations

import importlib.util
import itertools
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load("microlensing_calibration_evaluator", HERE / "evaluator.py")
REFERENCE = _load("microlensing_calibration_reference", HERE / "reference_solver.py")


def reference_policy(fit_cutoff, point_signal_cutoff, sine_signal_cutoff,
                     anomaly_cutoff):
    def infer(problem, observe):
        times = np.asarray(problem["candidate_times"], dtype=float)
        chosen = list(times[::2])
        chosen += [float(value) for value in (-6.0, -2.0, 2.0, 6.0, 10.0, 14.0)]
        chosen = list(dict.fromkeys(round(value, 3) for value in chosen))[:18]
        rows = [observe(float(time), "r") for time in chosen]
        rows.extend(observe(float(time), "g")
                    for time in (-18.0, -10.0, 0.0, 4.0, 8.0, 16.0))
        t = np.asarray([row["time"] for row in rows if row["band"] == "r"], dtype=float)
        y = np.asarray([row["flux"] for row in rows if row["band"] == "r"], dtype=float)
        point = REFERENCE._fit_point(t, y)
        sine_error, period, sine_amplitude = REFERENCE._sinusoid(t, y)
        residual = y - (point[3][0] + point[3][1] * point[2])
        anomaly = float(np.max(residual))
        point_excess = float(np.max(y) - np.median(y[np.abs(t) > 16.0]))
        evidence = [row["query_id"] for row in rows]
        if (min(point[0], sine_error) > fit_cutoff
                or (point_excess < point_signal_cutoff
                    and sine_amplitude < sine_signal_cutoff)):
            return {"abstain": True, "confidence": 0.72,
                    "evidence_query_ids": evidence}
        if anomaly > anomaly_cutoff and point_excess > 0.20:
            model, amplitude, confidence, scale = (
                "binary_lens", float(np.clip(anomaly, 0, 1)), 0.78, point[1]
            )
        elif point_excess > 0.20 and point[0] <= sine_error * 1.15:
            model, amplitude, confidence, scale = "point_lens", 0.0, 0.80, point[1]
        else:
            model, amplitude, confidence, scale = (
                "variable_source", float(np.clip(sine_amplitude, 0, 1)), 0.74, period
            )
        return {
            "abstain": False,
            "model": model,
            "timescale_days": float(np.clip(scale, 2, 20)),
            "amplitude": amplitude,
            "confidence": confidence,
            "evidence_query_ids": evidence,
        }
    return infer


def threshold_policy(sample_count, refusal_range, roughness_cutoff, peak_shape_cutoff,
                     fixed_timescale):
    def infer(problem, observe):
        allowed = list(problem["candidate_times"])
        indices = np.linspace(0, len(allowed) - 1, sample_count, dtype=int)
        times = [float(allowed[index]) for index in indices]
        rows = [observe(time, "r") for time in times]
        values = np.asarray([row["flux"] for row in rows], dtype=float)
        evidence = [row["query_id"] for row in rows]
        flux_range = float(np.ptp(values))
        if flux_range < refusal_range:
            return {"abstain": True, "confidence": 0.60,
                    "evidence_query_ids": evidence}
        roughness = float(np.max(np.abs(np.diff(values, n=2)))) if len(values) > 2 else 0.0
        edge = 0.5 * (values[0] + values[-1])
        peak_shape = float(np.max(values) - edge)
        if roughness > roughness_cutoff:
            model = "binary_lens"
        elif peak_shape > peak_shape_cutoff:
            model = "point_lens"
        else:
            model = "variable_source"
        return {
            "abstain": False,
            "model": model,
            "timescale_days": float(fixed_timescale),
            "amplitude": float(np.clip(0.35 * flux_range if model != "point_lens" else 0.0,
                                       0.0, 1.0)),
            "confidence": 0.65,
            "evidence_query_ids": evidence,
        }
    return infer


def _summary(metrics):
    keys = (
        "combined_score", "development_mechanism_score", "heldout_mechanism_score",
        "development_model_accuracy", "heldout_model_accuracy",
        "development_false_discovery_rate", "heldout_false_discovery_rate",
        "development_correct_refusal_rate", "heldout_correct_refusal_rate",
    )
    return {key: metrics[key] for key in keys}


def main():
    reference_first = EVALUATOR.evaluate(REFERENCE.infer_microlensing)
    reference_second = EVALUATOR.evaluate(REFERENCE.infer_microlensing)
    if reference_first != reference_second:
        raise RuntimeError("reference replay is not deterministic")
    tuned = None
    tuning_count = 0
    for parameters in itertools.product(
        (0.0025, 0.005, 0.01),
        (0.16, 0.25, 0.34),
        (0.09, 0.15, 0.21),
        (0.06, 0.09, 0.12),
    ):
        metrics = EVALUATOR.evaluate(reference_policy(*parameters))
        tuning_count += 1
        if tuned is None or metrics["combined_score"] > tuned[0]:
            tuned = (metrics["combined_score"], parameters, metrics)
    best = None
    count = 0
    grid = itertools.product(
        (6, 9, 12, 18),
        np.linspace(0.08, 0.32, 7),
        np.linspace(0.04, 0.28, 7),
        np.linspace(0.08, 0.56, 7),
        (6.0, 10.0, 14.0),
    )
    for parameters in grid:
        metrics = EVALUATOR.evaluate(threshold_policy(*parameters))
        count += 1
        if best is None or metrics["combined_score"] > best[0]:
            best = (metrics["combined_score"], parameters, metrics)
    print(json.dumps({
        "reference": _summary(reference_first),
        "reference_parameter_probe": {
            "strategy_count": tuning_count,
            "best_parameters": list(tuned[1]),
            **_summary(tuned[2]),
        },
        "shortcut_probe": {
            "strategy_count": count,
            "best_parameters": list(best[1]),
            **_summary(best[2]),
        },
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
