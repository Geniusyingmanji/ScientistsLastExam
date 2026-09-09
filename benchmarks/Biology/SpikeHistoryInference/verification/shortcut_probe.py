"""Sweep low-dimensional moment thresholds without fitting the point-process model."""
from __future__ import annotations

import itertools
import json
import math

import numpy as np

import evaluator


def _features(problem):
    trial_rates = []
    stimuli, outcomes, recent, delayed = [], [], [], []
    horizon = int(round(problem["history_horizon_ms"] / problem["bin_width_ms"]))
    for trial in problem["trials"]:
        stimulus = np.asarray(trial["stimulus"], dtype=float)
        spikes = np.asarray(trial["spikes"], dtype=float)
        trial_rates.append(float(np.mean(spikes)))
        for t in range(horizon, len(spikes)):
            stimuli.append(stimulus[t])
            outcomes.append(spikes[t])
            recent.append(float(np.any(spikes[t - 4:t] > 0.0)))
            delayed.append(float(np.any(spikes[t - 7:t - 2] > 0.0)))
    stimuli = np.asarray(stimuli)
    outcomes = np.asarray(outcomes)
    recent = np.asarray(recent, dtype=bool)
    delayed = np.asarray(delayed, dtype=bool)
    mean_rate = float(np.mean(outcomes))
    expected_trial_variance = max(mean_rate * (1.0 - mean_rate) / len(problem["trials"][0]["spikes"]), 1e-9)
    trial_overdispersion = float(np.var(trial_rates, ddof=1) / expected_trial_variance)

    delayed_lift = float(np.mean(outcomes[delayed]) - np.mean(outcomes[~delayed]))
    suppressions = []
    for mask in (stimuli <= 0.0, stimuli > 0.0):
        with_history = outcomes[mask & recent]
        without_history = outcomes[mask & ~recent]
        suppressions.append(float(np.mean(without_history) - np.mean(with_history)))
    interaction_contrast = suppressions[1] - suppressions[0]
    return mean_rate, trial_overdispersion, delayed_lift, interaction_contrast


def _candidate(problem, thresholds):
    mean_rate, overdispersion, delayed_lift, interaction = _features(problem)
    burst_threshold, mixture_threshold, interaction_threshold = thresholds
    diagnosis, abstain = "supported", False
    if delayed_lift > burst_threshold:
        diagnosis, abstain = "burst_history", True
    elif overdispersion > mixture_threshold:
        diagnosis, abstain = "trial_gain_mixture", True
    elif interaction > interaction_threshold:
        diagnosis, abstain = "stimulus_history_interaction", True

    intercept = float(np.clip(
        math.log(max(mean_rate, 1e-4) / max(1.0 - mean_rate, 1e-4)),
        *problem["parameter_bounds"]["intercept"],
    ))
    gain, amplitude, tau_ms = 0.6, 2.0, 20.0
    probabilities = []
    for context in problem["prediction_contexts"]:
        history = sum(math.exp(-lag / tau_ms) for lag in context["recent_spike_lags_ms"])
        eta = intercept + gain * context["stimulus"] - amplitude * history
        probabilities.append(float(1.0 / (1.0 + math.exp(-eta))))
    return {
        "intercept": intercept,
        "stimulus_gain": gain,
        "refractory_amplitude": amplitude,
        "refractory_tau_ms": tau_ms,
        "prediction_probabilities": probabilities,
        "diagnosis": diagnosis,
        "confidence": 0.6,
        "abstain": abstain,
        "evidence_trial_ids": [trial["trial_id"] for trial in problem["trials"]],
    }


def _cached_worlds():
    return {
        "development": [(spec, evaluator.public_problem(spec)) for spec in evaluator.DEVELOPMENT_WORLDS],
        "heldout": [(spec, evaluator.public_problem(spec)) for spec in evaluator.HELDOUT_WORLDS],
    }


def _evaluate_cached(worlds, thresholds):
    summaries = {}
    for split, entries in worlds.items():
        rows = []
        for spec, problem in entries:
            result = evaluator._validate(_candidate(problem, thresholds), problem)
            score = evaluator._score(spec, result, problem)
            rows.append({
                "kind": spec["kind"],
                "abstained": result["abstain"],
                "valid": True,
                **score,
            })
        summaries[split] = evaluator._summary(rows)
    return summaries


def run_sweep():
    worlds = _cached_worlds()
    grids = itertools.product(
        (0.000, 0.008, 0.016, 0.024),
        (1.4, 1.8, 2.2, 2.6, 3.0, 3.4),
        (0.000, 0.010, 0.020, 0.030, 0.040, 0.050, 0.060, 0.080),
    )
    best = None
    count = 0
    for thresholds in grids:
        count += 1
        summary = _evaluate_cached(worlds, thresholds)
        key = summary["development"]["combined_score"]
        if best is None or key > best[0]:
            best = (key, thresholds, summary)
    return {
        "strategy_count": count,
        "best_thresholds": {
            "delayed_lift": best[1][0],
            "trial_overdispersion": best[1][1],
            "interaction_contrast": best[1][2],
        },
        "development": best[2]["development"],
        "heldout": best[2]["heldout"],
    }


if __name__ == "__main__":
    print(json.dumps(run_sweep(), indent=2, sort_keys=True))
