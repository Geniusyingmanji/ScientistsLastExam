"""Truth-blind ablations used to establish the task's difficulty ladder."""
from __future__ import annotations

import math

import numpy as np

from reference_solver import infer_spike_history


def fixed_tau_20(problem):
    result = infer_spike_history(problem)
    if result["abstain"]:
        return result
    tau_ms = 20.0
    result["refractory_tau_ms"] = tau_ms
    predictions = []
    for context in problem["prediction_contexts"]:
        history = sum(math.exp(-lag / tau_ms) for lag in context["recent_spike_lags_ms"])
        eta = (
            result["intercept"]
            + result["stimulus_gain"] * context["stimulus"]
            - result["refractory_amplitude"] * history
        )
        predictions.append(float(1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, eta))))))
    result["prediction_probabilities"] = predictions
    return result


def never_refuse(problem):
    result = infer_spike_history(problem)
    result["diagnosis"] = "supported"
    result["abstain"] = False
    result["confidence"] = 0.5
    return result


def rate_only(problem):
    spikes = np.concatenate([
        np.asarray(trial["spikes"], dtype=float) for trial in problem["trials"]
    ])
    rate = float(np.clip(np.mean(spikes), 1e-4, 1.0 - 1e-4))
    intercept = float(np.clip(
        math.log(rate / (1.0 - rate)), *problem["parameter_bounds"]["intercept"]
    ))
    probability = float(1.0 / (1.0 + math.exp(-intercept)))
    return {
        "intercept": intercept,
        "stimulus_gain": 0.0,
        "refractory_amplitude": 0.0,
        "refractory_tau_ms": 20.0,
        "prediction_probabilities": [probability for _ in problem["prediction_contexts"]],
        "diagnosis": "supported",
        "confidence": 0.5,
        "abstain": False,
        "evidence_trial_ids": [trial["trial_id"] for trial in problem["trials"]],
    }
