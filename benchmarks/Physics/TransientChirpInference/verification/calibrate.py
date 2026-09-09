"""Reproduce the reference ablations and low-dimensional shortcut probe."""
from __future__ import annotations

import importlib.util
import argparse
import itertools
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load(ROOT / "verification" / "evaluator.py", "chirp_calibration_evaluator")
REFERENCE = _load(ROOT / "verification" / "reference_solver.py", "chirp_calibration_reference")


def _line_fit(times, values):
    t = np.asarray(times, dtype=float)
    y = np.asarray(values, dtype=float)
    best = (float("inf"), 0.0)
    for frequency in np.linspace(0.04, 0.18, 29):
        phase = 2 * math.pi * frequency * t
        design = np.column_stack([np.ones(len(t)), np.sin(phase), np.cos(phase)])
        coefficients, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
        error = float(np.mean((y - design @ coefficients) ** 2))
        amplitude = float(np.hypot(coefficients[1], coefficients[2]))
        if error < best[0]:
            best = (error, amplitude)
    return best


def no_chirp_grid(problem, observe):
    times = [float(value) for value in problem["candidate_times"][:12]]
    rows = [observe(time, detector) for detector in ("H1", "L1") for time in times]
    h1 = np.asarray([row["strain"] for row in rows[:12]], dtype=float)
    l1 = np.asarray([row["strain"] for row in rows[12:]], dtype=float)
    difference = np.abs(h1 - l1)
    peak = int(np.argmax(difference))
    if float(difference[peak]) > 0.38 and float(np.median(np.abs(l1))) < 0.18:
        model, event_time, amplitude, abstain = (
            "glitch", times[peak], float(np.clip(np.max(np.abs(h1)), 0, 1)), False
        )
    else:
        error, amplitude = _line_fit(times, h1)
        model, event_time, abstain = "line", 9.0, error > 0.006 or amplitude < 0.20
    answer = {
        "abstain": abstain,
        "confidence": 0.70,
        "evidence_query_ids": [row["query_id"] for row in rows],
    }
    if not abstain:
        answer.update(model=model, frequency_slope=0.0, event_time=event_time,
                      amplitude=float(np.clip(amplitude, 0, 1)))
    return answer


def h1_only(problem, observe):
    times = [float(value) for value in problem["candidate_times"][:12]]
    rows = [observe(time, "H1") for time in times]
    values = np.asarray([row["strain"] for row in rows], dtype=float)
    fit = REFERENCE._fit_grid(np.asarray(times), values)
    line_error, _ = _line_fit(times, values)
    if fit[0] > 0.006 or fit[3] < 0.20:
        return {"abstain": True, "confidence": 0.70,
                "evidence_query_ids": [row["query_id"] for row in rows]}
    model = "chirp" if fit[0] < line_error * 0.72 else "line"
    return {
        "abstain": False,
        "model": model,
        "frequency_slope": float(np.clip(fit[2] if model == "chirp" else 0.0, 0, 0.05)),
        "event_time": 9.0,
        "amplitude": float(np.clip(fit[3], 0, 1)),
        "confidence": 0.76,
        "evidence_query_ids": [row["query_id"] for row in rows],
    }


def never_refuse(problem, observe):
    answer = REFERENCE.infer_transient(problem, observe)
    if answer["abstain"]:
        return {
            "abstain": False,
            "model": "line",
            "frequency_slope": 0.0,
            "event_time": 9.0,
            "amplitude": 0.15,
            "confidence": 0.55,
            "evidence_query_ids": answer["evidence_query_ids"],
        }
    return answer


def threshold_policy(sample_count, glitch_threshold, refusal_threshold, chirp_threshold):
    def infer(problem, observe):
        times = [float(value) for value in problem["candidate_times"][:sample_count]]
        rows = [observe(time, detector) for detector in ("H1", "L1") for time in times]
        h1 = np.asarray([row["strain"] for row in rows[:sample_count]], dtype=float)
        l1 = np.asarray([row["strain"] for row in rows[sample_count:]], dtype=float)
        difference = np.abs(h1 - l1)
        peak = int(np.argmax(difference))
        scale = float(np.sqrt(np.mean((0.5 * (h1 + l1)) ** 2)))
        evidence = [row["query_id"] for row in rows]
        if scale < refusal_threshold:
            return {"abstain": True, "confidence": 0.6, "evidence_query_ids": evidence}
        if float(difference[peak]) > glitch_threshold:
            model, slope, event_time = "glitch", 0.0, times[peak]
        else:
            rough_change = float(abs(np.mean(np.diff(h1[: sample_count // 2]))
                                     - np.mean(np.diff(h1[sample_count // 2 :]))))
            model = "chirp" if rough_change > chirp_threshold else "line"
            slope, event_time = (0.02 if model == "chirp" else 0.0), 9.0
        return {
            "abstain": False,
            "model": model,
            "frequency_slope": slope,
            "event_time": event_time,
            "amplitude": float(np.clip(np.sqrt(2) * scale, 0, 1)),
            "confidence": 0.65,
            "evidence_query_ids": evidence,
        }
    return infer


def _summary(metrics):
    keys = (
        "combined_score", "robustness_score", "development_science_score", "heldout_science_score",
        "development_mechanism_score", "heldout_mechanism_score",
        "development_model_accuracy", "heldout_model_accuracy",
        "development_false_discovery_rate", "heldout_false_discovery_rate",
        "development_correct_refusal_rate", "heldout_correct_refusal_rate",
    )
    return {key: metrics[key] for key in keys}


def sign_count_policy(sample_count=12, glitch_threshold=0.38, refusal_rms=0.0,
                      uncertainty_threshold=0.08, count_delta=0, chirp_slope=0.02):
    def infer(problem, observe):
        times = [float(value) for value in problem["candidate_times"][:sample_count]]
        rows = [observe(time, detector) for detector in ("H1", "L1") for time in times]
        h = np.array([r["strain"] for r in rows[:sample_count]])
        l = np.array([r["strain"] for r in rows[sample_count:]])
        evidence = [r["query_id"] for r in rows]
        if rows[0]["uncertainty"] > uncertainty_threshold or float(np.std(h)) < refusal_rms:
            return {"abstain": True, "confidence": 0.8, "evidence_query_ids": evidence}
        diff = np.abs(h - l)
        if float(np.max(diff)) > glitch_threshold:
            model, slope, event_time = "glitch", 0.0, times[int(np.argmax(diff))]
            amplitude = float(np.max(np.abs(h)))
        else:
            early = int(np.sum(np.diff(np.signbit(h[:sample_count // 2]))))
            late = int(np.sum(np.diff(np.signbit(h[sample_count // 2:]))))
            model = "chirp" if late - early > count_delta else "line"
            slope, event_time = (chirp_slope if model == "chirp" else 0.0), 9.0
            amplitude = float(np.sqrt(2) * np.std(h))
        return {"abstain": False, "model": model, "frequency_slope": slope,
                "event_time": event_time, "amplitude": float(np.clip(amplitude, 0, 1)),
                "confidence": 0.8, "evidence_query_ids": evidence}
    return infer


def morphology_policy(sample_count=15, refusal_rms=0.15, glitch_median=0.15,
                      count_delta=1, chirp_slope=0.006):
    """No-fit morphology probe supplied during PR48 review."""
    def infer(problem, observe):
        times = [float(value) for value in problem["candidate_times"][:sample_count]]
        rows = [observe(time, "H1") for time in times]
        h = np.asarray([row["strain"] for row in rows], dtype=float)
        evidence = [row["query_id"] for row in rows]
        if float(np.std(h)) < refusal_rms:
            return {"abstain": True, "confidence": 1.0, "evidence_query_ids": evidence}
        if float(np.median(np.abs(h))) < glitch_median:
            model, slope = "glitch", 0.0
            event_time = times[int(np.argmax(h))]
            amplitude = float(np.max(np.abs(h)))
        else:
            early = int(np.sum(np.diff(np.signbit(h[:6]))))
            late = int(np.sum(np.diff(np.signbit(h[6:]))))
            model = "chirp" if late - early >= count_delta else "line"
            slope, event_time = (chirp_slope if model == "chirp" else 0.0), 9.0
            amplitude = float(np.sqrt(2) * np.std(h))
        return {"abstain": False, "model": model, "frequency_slope": slope,
                "event_time": event_time, "amplitude": float(np.clip(amplitude, 0, 1)),
                "confidence": 1.0, "evidence_query_ids": evidence}
    return infer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    strategies = {
        "reference": REFERENCE.infer_transient,
        "h1_only": h1_only,
        "no_chirp_grid": no_chirp_grid,
        "never_refuse": never_refuse,
        "maintainer_sign_count": sign_count_policy(),
    }
    results = {name: _summary(EVALUATOR.evaluate(strategy))
               for name, strategy in strategies.items()}
    best = None
    count = 0
    grid = itertools.product(
        (6, 8, 10, 12),
        np.linspace(0.15, 0.55, 9),
        np.linspace(0.04, 0.20, 9),
        np.linspace(0.02, 0.18, 9),
    )
    for parameters in grid:
        metrics = EVALUATOR.evaluate(threshold_policy(*parameters))
        count += 1
        if best is None or metrics["combined_score"] > best[0]:
            best = (metrics["combined_score"], parameters, metrics)
    results["shortcut_probe"] = {
        "strategy_count": count,
        "best_parameters": list(best[1]),
        **_summary(best[2]),
    }
    best = None
    count = 0
    for parameters in itertools.product(
        (6, 8, 10, 12), (0.28, 0.38, 0.48), (0.0, 0.08, 0.16),
        (0.03, 0.05, 0.08), (-1, 0, 1), (0.003, 0.006, 0.014, 0.02, 0.03),
    ):
        metrics = EVALUATOR.evaluate(sign_count_policy(*parameters))
        count += 1
        if best is None or metrics["combined_score"] > best[0]:
            best = (metrics["combined_score"], parameters, metrics)
    results["sign_count_shortcut_probe"] = {
        "strategy_count": count, "best_parameters": list(best[1]), **_summary(best[2])}
    best = None
    count = 0
    for parameters in itertools.product(
        (12, 15, 19), (0.10, 0.15, 0.22), (0.10, 0.15, 0.22),
        (1, 2), (0.003, 0.0045, 0.006, 0.02),
    ):
        metrics = EVALUATOR.evaluate(morphology_policy(*parameters))
        count += 1
        if best is None or metrics["combined_score"] > best[0]:
            best = (metrics["combined_score"], parameters, metrics)
    results["morphology_shortcut_probe"] = {
        "strategy_count": count, "best_parameters": list(best[1]), **_summary(best[2])}
    results["selection_protocol"] = "Development-only selection; trusted in-process sweep. Replay selected policies through the sandbox separately."
    payload = json.dumps(results, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
