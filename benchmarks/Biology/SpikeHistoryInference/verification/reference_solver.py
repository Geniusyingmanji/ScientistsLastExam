"""Truth-blind reference policy for SpikeHistoryInference."""
from __future__ import annotations

import math

import numpy as np


def _sigmoid(values):
    return 1.0 / (1.0 + np.exp(-np.clip(values, -30.0, 30.0)))


def _irls(X, y, ridge=1e-3, iterations=35):
    beta = np.zeros(X.shape[1], dtype=float)
    penalty = np.eye(X.shape[1]) * ridge
    penalty[0, 0] = 0.0
    for _ in range(iterations):
        probability = np.clip(_sigmoid(X @ beta), 1e-6, 1.0 - 1e-6)
        weight = probability * (1.0 - probability)
        hessian = X.T @ (weight[:, None] * X) + penalty
        gradient = X.T @ (y - probability) - penalty @ beta
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(hessian, gradient, rcond=None)[0]
        beta += np.clip(step, -2.0, 2.0)
        if float(np.max(np.abs(step))) < 1e-7:
            break
    probability = np.clip(_sigmoid(X @ beta), 1e-9, 1.0 - 1e-9)
    nll = float(-np.sum(y * np.log(probability) + (1.0 - y) * np.log(1.0 - probability)))
    return beta, probability, nll


def _arrays(problem):
    horizon = int(round(problem["history_horizon_ms"] / problem["bin_width_ms"]))
    stimuli, outcomes, trial_indices, lag_rows = [], [], [], []
    for trial_index, trial in enumerate(problem["trials"]):
        stimulus = np.asarray(trial["stimulus"], dtype=float)
        spikes = np.asarray(trial["spikes"], dtype=float)
        for t in range(horizon, len(spikes)):
            stimuli.append(stimulus[t])
            outcomes.append(spikes[t])
            trial_indices.append(trial_index)
            lag_rows.append(spikes[t - horizon:t][::-1])
    return (
        np.asarray(stimuli),
        np.asarray(outcomes),
        np.asarray(trial_indices),
        np.asarray(lag_rows),
    )


def _fit_supported(problem, stimuli, outcomes, lag_rows):
    bin_ms = float(problem["bin_width_ms"])
    lags = np.arange(1, lag_rows.shape[1] + 1, dtype=float) * bin_ms
    best = None
    for tau_ms in np.linspace(6.0, 60.0, 28):
        trace = lag_rows @ np.exp(-lags / tau_ms)
        X = np.column_stack([np.ones(len(outcomes)), stimuli, -trace])
        beta, probability, nll = _irls(X, outcomes)
        if beta[2] < 0.0:
            nll += 100.0 * abs(float(beta[2]))
        candidate = (nll, tau_ms, beta, probability, trace)
        if best is None or candidate[0] < best[0]:
            best = candidate
    return best


def infer_spike_history(problem):
    stimuli, outcomes, trial_indices, lag_rows = _arrays(problem)
    base_nll, tau_ms, beta, base_probability, trace = _fit_supported(
        problem, stimuli, outcomes, lag_rows
    )
    intercept, gain, amplitude = [float(value) for value in beta]

    flexible_X = np.column_stack([np.ones(len(outcomes)), stimuli, lag_rows[:, :12]])
    flexible_beta, _, flexible_nll = _irls(flexible_X, outcomes, ridge=0.02)
    positive_bump = float(np.max(flexible_beta[4:10]))
    burst_lr = 2.0 * (base_nll - flexible_nll)

    trial_columns = np.zeros((len(outcomes), len(problem["trials"]) - 1), dtype=float)
    for column in range(1, len(problem["trials"])):
        trial_columns[:, column - 1] = trial_indices == column
    trial_X = np.column_stack([np.ones(len(outcomes)), stimuli, -trace, trial_columns])
    _, _, trial_nll = _irls(trial_X, outcomes, ridge=0.05)
    mixture_bic_gain = 2.0 * (base_nll - trial_nll) - trial_columns.shape[1] * math.log(len(outcomes))
    trial_z = []
    for trial_index in range(len(problem["trials"])):
        mask = trial_indices == trial_index
        variance = float(np.sum(base_probability[mask] * (1.0 - base_probability[mask])))
        trial_z.append(float(np.sum(outcomes[mask] - base_probability[mask])) / max(math.sqrt(variance), 1e-6))
    trial_overdispersion = float(np.var(trial_z, ddof=1))

    interaction_feature = -trace * np.maximum(stimuli, 0.0)
    interaction_X = np.column_stack([np.ones(len(outcomes)), stimuli, -trace, interaction_feature])
    interaction_beta, _, interaction_nll = _irls(interaction_X, outcomes, ridge=0.01)
    interaction_lr = 2.0 * (base_nll - interaction_nll)
    interaction_strength = float(interaction_beta[3])

    diagnosis = "supported"
    abstain = False
    confidence = 0.88
    if positive_bump > 0.28 and burst_lr > 18.0:
        diagnosis, abstain, confidence = "burst_history", True, 0.92
    elif trial_overdispersion > 2.45 and mixture_bic_gain > -175.0:
        diagnosis, abstain, confidence = "trial_gain_mixture", True, 0.92
    elif interaction_strength > 1.00 and interaction_lr > 4.0:
        diagnosis, abstain, confidence = "stimulus_history_interaction", True, 0.92

    predictions = []
    for context in problem["prediction_contexts"]:
        history = sum(math.exp(-lag / tau_ms) for lag in context["recent_spike_lags_ms"])
        eta = intercept + gain * context["stimulus"] - amplitude * history
        predictions.append(float(_sigmoid(eta)))
    bounds = problem["parameter_bounds"]
    return {
        "intercept": float(np.clip(intercept, *bounds["intercept"])),
        "stimulus_gain": float(np.clip(gain, *bounds["stimulus_gain"])),
        "refractory_amplitude": float(np.clip(amplitude, *bounds["refractory_amplitude"])),
        "refractory_tau_ms": float(np.clip(tau_ms, *bounds["refractory_tau_ms"])),
        "prediction_probabilities": predictions,
        "diagnosis": diagnosis,
        "confidence": confidence,
        "abstain": abstain,
        "evidence_trial_ids": [trial["trial_id"] for trial in problem["trials"]],
    }
