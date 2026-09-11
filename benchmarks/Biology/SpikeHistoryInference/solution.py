"""Weak valid baseline: decline spike-history interpretation."""


def infer_spike_history(problem):
    return {
        "intercept": -3.0,
        "stimulus_gain": 0.0,
        "refractory_amplitude": 0.0,
        "refractory_tau_ms": 20.0,
        "prediction_probabilities": [0.5 for _ in problem["prediction_contexts"]],
        "diagnosis": "undetermined",
        "confidence": 0.0,
        "abstain": True,
        "evidence_trial_ids": [trial["trial_id"] for trial in problem["trials"]],
    }
