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
    def logit_rate(values):
        # The supported refractory term is additive in log odds.  Comparing
        # probability differences confounds it with stimulus-dependent base
        # rate, so use the matching logit-scale conditional contrast.
        rate = float(np.mean(values))
        rate = float(np.clip(rate, 1e-4, 1.0 - 1e-4))
        return math.log(rate / (1.0 - rate))

    suppressions = []
    for mask in (stimuli <= 0.0, stimuli > 0.0):
        with_history = outcomes[mask & recent]
        without_history = outcomes[mask & ~recent]
        suppressions.append(logit_rate(without_history) - logit_rate(with_history))
    interaction_contrast = suppressions[1] - suppressions[0]
    return mean_rate, trial_overdispersion, delayed_lift, interaction_contrast


def _two_point_parameters(problem):
    values, outcomes = [], []
    for trial in problem["trials"]:
        values.extend(trial["stimulus"])
        outcomes.extend(trial["spikes"])
    values = np.asarray(values, dtype=float)
    outcomes = np.asarray(outcomes, dtype=float)

    def logit_rate(mask):
        rate = float(np.clip(np.mean(outcomes[mask]), 1e-4, 1.0 - 1e-4))
        return math.log(rate / (1.0 - rate))

    low, high = values <= 0.0, values > 0.0
    gain = (logit_rate(high) - logit_rate(low)) / max(float(np.mean(values[high]) - np.mean(values[low])), 1e-6)
    intercept = logit_rate(np.ones_like(values, dtype=bool)) - gain * float(np.mean(values))
    return intercept, gain


def _candidate(problem, thresholds, parameters, features=None, two_point=False):
    features = features or _features(problem) + _two_point_parameters(problem)
    mean_rate, overdispersion, delayed_lift, interaction = features[:4]
    burst_threshold, mixture_threshold, interaction_threshold = thresholds
    diagnosis, abstain = "supported", False
    if delayed_lift > burst_threshold:
        diagnosis, abstain = "burst_history", True
    elif overdispersion > mixture_threshold:
        diagnosis, abstain = "trial_gain_mixture", True
    elif interaction > interaction_threshold:
        diagnosis, abstain = "stimulus_history_interaction", True

    if two_point:
        intercept, gain = features[4:6]
    else:
        intercept = math.log(max(mean_rate, 1e-4) / max(1.0 - mean_rate, 1e-4))
        gain = parameters[0]
    intercept = float(np.clip(intercept, *problem["parameter_bounds"]["intercept"]))
    gain, amplitude, tau_ms = parameters
    if two_point:
        gain = float(np.clip(gain, *problem["parameter_bounds"]["stimulus_gain"]))
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
        "development": [
            (spec, problem, _features(problem) + _two_point_parameters(problem))
            for spec in evaluator.DEVELOPMENT_WORLDS
            for problem in [evaluator.public_problem(spec)]
        ],
        "heldout": [
            (spec, problem, _features(problem) + _two_point_parameters(problem))
            for spec in evaluator.HELDOUT_WORLDS
            for problem in [evaluator.public_problem(spec)]
        ],
    }


def _evaluate_cached(worlds, thresholds, parameters, two_point=False):
    summaries = {}
    for split, entries in worlds.items():
        rows = []
        for spec, problem, features in entries:
            result = evaluator._validate(
                _candidate(problem, thresholds, parameters, features, two_point), problem
            )
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
    threshold_grid = itertools.product(
        (0.000, 0.008, 0.016, 0.024),
        (1.4, 2.0, 2.6, 3.2),
        (0.40, 0.55, 0.70, 0.85, 1.00, 1.20),
    )
    parameter_grid = itertools.product(
        (0.4, 0.8, 1.2),
        (1.2, 2.4, 3.6),
        (12.0, 36.0),
    )
    best = None
    count = 0
    for thresholds, parameters, two_point in itertools.product(
        tuple(threshold_grid), tuple(parameter_grid), (False, True),
    ):
        count += 1
        summary = _evaluate_cached(worlds, thresholds, parameters, two_point)
        key = summary["development"]["combined_score"]
        if best is None or key > best[0]:
            best = (key, thresholds, parameters, two_point, summary)
    return {
        "strategy_count": count,
        "best_thresholds": {
            "delayed_lift": best[1][0],
            "trial_overdispersion": best[1][1],
            "interaction_contrast": best[1][2],
        },
        "constant_parameters": {
            "stimulus_gain": best[2][0],
            "refractory_amplitude": best[2][1],
            "refractory_tau_ms": best[2][2],
        },
        "uses_two_point_logit_drive": best[3],
        "development": best[4]["development"],
        "heldout": best[4]["heldout"],
    }


if __name__ == "__main__":
    print(json.dumps(run_sweep(), indent=2, sort_keys=True))
