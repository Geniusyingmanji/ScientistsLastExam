"""Deterministic point-process laboratory for spike-history inference."""
from __future__ import annotations

import copy
import math
from typing import Any

import numpy as np


BIN_WIDTH_MS = 5.0
HISTORY_HORIZON_BINS = 20
N_TRIALS = 30
N_BINS = 200
VALID_DIAGNOSES = {
    "supported",
    "burst_history",
    "trial_gain_mixture",
    "stimulus_history_interaction",
    "undetermined",
}

PREDICTION_CONTEXTS = [
    {"stimulus": stimulus, "recent_spike_lags_ms": lags}
    for lags in ([], [5.0], [10.0, 25.0], [5.0, 15.0, 35.0])
    for stimulus in (-1.2, 0.0, 1.2)
]

PARAMETER_TOLERANCES = {
    "intercept": 0.35,
    "stimulus_gain": 0.25,
    "refractory_amplitude": 0.55,
    "refractory_tau_ms": 15.0,
}

PUBLIC_TEMPLATE = {
    "schema_version": 1,
    "bin_width_ms": BIN_WIDTH_MS,
    "history_horizon_ms": BIN_WIDTH_MS * HISTORY_HORIZON_BINS,
    "supported_model": (
        "logit P(spike_t=1) = intercept + stimulus_gain*stimulus_t "
        "- refractory_amplitude*sum_j exp(-lag_j/refractory_tau_ms)"
    ),
    "diagnosis_values": sorted(VALID_DIAGNOSES),
    "parameter_bounds": {
        "intercept": [-5.0, -1.0],
        "stimulus_gain": [0.0, 2.0],
        "refractory_amplitude": [0.0, 5.0],
        "refractory_tau_ms": [5.0, 80.0],
    },
    "prediction_contexts": PREDICTION_CONTEXTS,
    "abstain_when": (
        "burst-like spike history, trial-to-trial latent gain mixtures, or "
        "stimulus-dependent refractory history are resolved"
    ),
}

DEVELOPMENT_WORLDS = (
    {"kind": "supported", "seed": 4101, "intercept": -3.00, "gain": 0.78, "amplitude": 2.20, "tau_ms": 14.0},
    {"kind": "supported", "seed": 4102, "intercept": -2.72, "gain": 0.58, "amplitude": 1.80, "tau_ms": 42.0},
    {"kind": "supported", "seed": 4103, "intercept": -3.28, "gain": 0.96, "amplitude": 2.75, "tau_ms": 10.0},
    {"kind": "burst_history", "seed": 4104, "intercept": -3.05, "gain": 0.72, "amplitude": 2.10, "tau_ms": 13.0, "burst": 1.35},
    {"kind": "trial_gain_mixture", "seed": 4105, "intercept": -3.00, "gain": 0.80, "amplitude": 2.00, "tau_ms": 18.0, "mixture": 0.72},
    {"kind": "stimulus_history_interaction", "seed": 4106, "intercept": -2.88, "gain": 0.68, "amplitude": 1.85, "tau_ms": 20.0, "interaction": 1.35},
)

HELDOUT_WORLDS = (
    {"kind": "supported", "seed": 5101, "intercept": -3.30, "gain": 0.55, "amplitude": 1.60, "tau_ms": 20.0},
    {"kind": "supported", "seed": 5102, "intercept": -2.65, "gain": 1.15, "amplitude": 3.10, "tau_ms": 38.0},
    {"kind": "burst_history", "seed": 5103, "intercept": -2.96, "gain": 0.64, "amplitude": 1.90, "tau_ms": 16.0, "burst": 1.20},
    {"kind": "trial_gain_mixture", "seed": 5104, "intercept": -3.10, "gain": 0.74, "amplitude": 2.25, "tau_ms": 15.0, "mixture": 0.64},
    {"kind": "stimulus_history_interaction", "seed": 5105, "intercept": -3.02, "gain": 0.84, "amplitude": 2.05, "tau_ms": 17.0, "interaction": 1.20},
)


def _sigmoid(value: float | np.ndarray) -> float | np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(value, -30.0, 30.0)))


def _history_sum(spikes: np.ndarray, index: int, tau_ms: float) -> float:
    count = min(index, HISTORY_HORIZON_BINS)
    if count == 0:
        return 0.0
    lags = np.arange(1, count + 1, dtype=float)
    return float(np.dot(spikes[index - count:index][::-1], np.exp(-lags * BIN_WIDTH_MS / tau_ms)))


def _burst_sum(spikes: np.ndarray, index: int) -> float:
    count = min(index, HISTORY_HORIZON_BINS)
    if count == 0:
        return 0.0
    lags = np.arange(1, count + 1, dtype=float)
    bump = np.exp(-0.5 * ((lags - 4.0) / 1.45) ** 2)
    return float(np.dot(spikes[index - count:index][::-1], bump))


def _make_trials(spec: dict[str, Any]) -> list[dict[str, Any]]:
    rng = np.random.default_rng(spec["seed"])
    mixture_signs = np.asarray([-1.0, 1.0] * (N_TRIALS // 2))
    rng.shuffle(mixture_signs)
    trials = []
    for trial_index in range(N_TRIALS):
        innovation = rng.normal(0.0, 1.0, size=N_BINS)
        stimulus = np.empty(N_BINS, dtype=float)
        stimulus[0] = innovation[0]
        for t in range(1, N_BINS):
            stimulus[t] = 0.62 * stimulus[t - 1] + math.sqrt(1.0 - 0.62 ** 2) * innovation[t]
        stimulus = np.clip(stimulus, -2.5, 2.5)
        spikes = np.zeros(N_BINS, dtype=int)
        for t in range(N_BINS):
            history = _history_sum(spikes, t, spec["tau_ms"])
            amplitude = spec["amplitude"]
            if spec["kind"] == "stimulus_history_interaction":
                amplitude *= 1.0 + spec["interaction"] * max(float(stimulus[t]), 0.0)
            eta = spec["intercept"] + spec["gain"] * stimulus[t] - amplitude * history
            if spec["kind"] == "burst_history":
                eta += spec["burst"] * _burst_sum(spikes, t)
            elif spec["kind"] == "trial_gain_mixture":
                eta += spec["mixture"] * mixture_signs[trial_index]
            probability = float(_sigmoid(eta))
            spikes[t] = int(rng.random() < probability)
        trials.append({
            "trial_id": f"trial_{trial_index:02d}",
            "stimulus": [round(float(value), 6) for value in stimulus],
            "spikes": [int(value) for value in spikes],
        })
    return trials


def public_problem(spec: dict[str, Any]) -> dict[str, Any]:
    problem = dict(PUBLIC_TEMPLATE)
    problem["parameter_bounds"] = dict(PUBLIC_TEMPLATE["parameter_bounds"])
    problem["prediction_contexts"] = [dict(context) for context in PREDICTION_CONTEXTS]
    problem["trials"] = _make_trials(spec)
    return problem


def _truth_probabilities(spec: dict[str, Any], problem: dict[str, Any]) -> np.ndarray:
    values = []
    for context in problem["prediction_contexts"]:
        history = sum(math.exp(-lag / spec["tau_ms"]) for lag in context["recent_spike_lags_ms"])
        eta = spec["intercept"] + spec["gain"] * context["stimulus"] - spec["amplitude"] * history
        values.append(float(_sigmoid(eta)))
    return np.asarray(values)


def _validate(submission: Any, problem: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    required = {
        "intercept", "stimulus_gain", "refractory_amplitude", "refractory_tau_ms",
        "prediction_probabilities", "diagnosis", "confidence", "abstain",
        "evidence_trial_ids",
    }
    if set(submission) != required:
        raise ValueError("submission keys must match the public contract exactly")
    if not isinstance(submission["abstain"], bool):
        raise ValueError("abstain must be boolean")
    if submission["diagnosis"] not in VALID_DIAGNOSES:
        raise ValueError("unknown diagnosis")
    confidence = float(submission["confidence"])
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be finite and in [0,1]")
    scalars = {}
    for name in ("intercept", "stimulus_gain", "refractory_amplitude", "refractory_tau_ms"):
        value = float(submission[name])
        bounds = problem["parameter_bounds"][name]
        if not math.isfinite(value) or not bounds[0] <= value <= bounds[1]:
            raise ValueError(f"{name} is outside its public bounds")
        scalars[name] = value
    probabilities = submission["prediction_probabilities"]
    if not isinstance(probabilities, (list, tuple)) or len(probabilities) != len(PREDICTION_CONTEXTS):
        raise ValueError("prediction_probabilities has the wrong length")
    probabilities = np.asarray(probabilities, dtype=float)
    if not np.all(np.isfinite(probabilities)) or np.any(probabilities < 0.0) or np.any(probabilities > 1.0):
        raise ValueError("prediction probabilities must be finite and in [0,1]")
    ids = submission["evidence_trial_ids"]
    allowed = {trial["trial_id"] for trial in problem["trials"]}
    if not isinstance(ids, list) or len(ids) < 4 or len(ids) != len(set(ids)) or not set(ids).issubset(allowed):
        raise ValueError("evidence_trial_ids must contain at least four unique supplied trial IDs")
    return {
        **scalars,
        "prediction_probabilities": probabilities,
        "diagnosis": submission["diagnosis"],
        "confidence": confidence,
        "abstain": submission["abstain"],
        "evidence_trial_ids": ids,
    }


def _score(spec: dict[str, Any], result: dict[str, Any], problem: dict[str, Any]) -> dict[str, Any]:
    unsupported = spec["kind"] != "supported"
    correct_refusal = unsupported and result["abstain"] and result["diagnosis"] == spec["kind"]
    false_discovery = unsupported and not result["abstain"]
    if unsupported:
        parameter_score = 0.0
        science = 1.0 if correct_refusal else 0.0
        prediction = 1.0 if correct_refusal else 0.0
    elif result["abstain"]:
        parameter_score = science = prediction = 0.0
    else:
        intercept_score = float(np.clip(
            1.0 - abs(result["intercept"] - spec["intercept"]) / PARAMETER_TOLERANCES["intercept"],
            0.0,
            1.0,
        ))
        gain_score = float(np.clip(
            1.0 - abs(result["stimulus_gain"] - spec["gain"]) / PARAMETER_TOLERANCES["stimulus_gain"],
            0.0,
            1.0,
        ))
        amplitude_score = float(np.clip(
            1.0 - abs(result["refractory_amplitude"] - spec["amplitude"]) / PARAMETER_TOLERANCES["refractory_amplitude"],
            0.0,
            1.0,
        ))
        tau_score = float(np.clip(
            1.0 - abs(result["refractory_tau_ms"] - spec["tau_ms"]) / PARAMETER_TOLERANCES["refractory_tau_ms"],
            0.0,
            1.0,
        ))
        parameter_score = 0.20 * intercept_score + 0.20 * gain_score + 0.35 * amplitude_score + 0.25 * tau_score
        diagnosis_score = float(result["diagnosis"] == "supported")
        science = 0.85 * parameter_score + 0.15 * diagnosis_score
        target = _truth_probabilities(spec, problem)
        mae = float(np.mean(np.abs(result["prediction_probabilities"] - target)))
        prediction = float(np.clip(1.0 - mae / 0.20, 0.0, 1.0))
    confidence_score = float(np.clip(1.0 - abs(result["confidence"] - science), 0.0, 1.0))
    if unsupported:
        combined = float(correct_refusal)
    elif result["abstain"]:
        combined = 0.0
    else:
        combined = diagnosis_score * (
            0.70 * parameter_score + 0.20 * prediction + 0.10 * confidence_score
        )
    return {
        "science_score": round(science, 6),
        "parameter_recovery_score": round(parameter_score, 6),
        "prediction_score": round(prediction, 6),
        "confidence_calibration_score": round(confidence_score, 6),
        "correct_refusal": bool(correct_refusal),
        "false_discovery": bool(false_discovery),
        "combined_score": round(combined, 6),
    }


def _evaluate_world(spec: dict[str, Any], split: str, index: int, candidate) -> dict[str, Any]:
    problem = public_problem(spec)
    base = {"split": split, "world_index": index, "kind": spec["kind"]}
    try:
        result = _validate(candidate(copy.deepcopy(problem)), problem)
        row = {**base, **_score(spec, result, problem)}
        row.update({
            "valid": True,
            "abstained": result["abstain"],
            "mechanism_correct": bool(
                result["diagnosis"] == "supported" and not result["abstain"]
                if spec["kind"] == "supported"
                else row["correct_refusal"]
            ),
            "confidence": round(result["confidence"], 6),
            "evidence_count": len(result["evidence_trial_ids"]),
        })
        return row
    except Exception as exc:  # noqa: BLE001
        return {
            **base,
            "combined_score": 0.0,
            "science_score": 0.0,
            "parameter_recovery_score": 0.0,
            "prediction_score": 0.0,
            "confidence_calibration_score": 0.0,
            "correct_refusal": False,
            "false_discovery": False,
            "valid": False,
            "abstained": True,
            "mechanism_correct": False,
            "confidence": 0.0,
            "evidence_count": 0,
            "reason": f"{type(exc).__name__}: {exc}",
        }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    unsupported = [row for row in rows if row["kind"] != "supported"]
    supported = [row for row in rows if row["kind"] == "supported"]
    attempts = [row for row in rows if not row["abstained"]]
    supported_quality = float(np.mean([row["combined_score"] for row in supported]))
    correct_refusal_rate = float(np.mean([row["correct_refusal"] for row in unsupported]))
    return {
        "combined_score": round(supported_quality * correct_refusal_rate, 6),
        "valid": float(all(row["valid"] for row in rows)),
        "science_score": round(float(np.mean([row["science_score"] for row in rows])), 6),
        "parameter_recovery_score": round(float(np.mean([row["parameter_recovery_score"] for row in supported])), 6),
        "prediction_score": round(float(np.mean([row["prediction_score"] for row in supported])), 6),
        "correct_refusal_rate": round(correct_refusal_rate, 6),
        "correct_refusal_count": sum(row["correct_refusal"] for row in unsupported),
        "false_discovery_rate": round(float(np.mean([row["false_discovery"] for row in unsupported])), 6),
        "false_discovery_count": sum(row["false_discovery"] for row in unsupported),
        "unsupported_world_count": len(unsupported),
        "supported_discovery_coverage": round(float(np.mean([not row["abstained"] for row in supported])), 6),
        "supported_discovery_count": sum(not row["abstained"] for row in supported),
        "supported_world_count": len(supported),
        "attempted_discovery_rate": round(len(attempts) / len(rows), 6),
        "attempted_discovery_count": len(attempts),
        "world_count": len(rows),
    }


def evaluate(candidate) -> dict[str, Any]:
    def evaluate_split(worlds, split):
        rows = []
        for i, spec in enumerate(worlds):
            reset = getattr(candidate, "reset_session", None)
            if callable(reset):
                reset()
            rows.append(_evaluate_world(spec, split, i, candidate))
        return rows

    development = evaluate_split(DEVELOPMENT_WORLDS, "development")
    heldout = evaluate_split(HELDOUT_WORLDS, "heldout")
    dev = _summary(development)
    held = _summary(heldout)
    return {
        "combined_score": dev["combined_score"],
        "valid": dev["valid"],
        "raw_score": dev["combined_score"],
        "development": dev,
        "heldout": held,
        "development_combined_score": dev["combined_score"],
        "heldout_combined_score": held["combined_score"],
        "development_mechanism_score": sum(r["valid"] and r["mechanism_correct"] for r in development) / len(development),
        "heldout_mechanism_score": sum(r["valid"] and r["mechanism_correct"] for r in heldout) / len(heldout),
        "development_mechanism_correct_count": sum(r["valid"] and r["mechanism_correct"] for r in development),
        "heldout_mechanism_correct_count": sum(r["valid"] and r["mechanism_correct"] for r in heldout),
        "development_mechanism_total_count": len(development),
        "heldout_mechanism_total_count": len(heldout),
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "development_discovery_coverage": dev["supported_discovery_coverage"],
        "heldout_discovery_coverage": held["supported_discovery_coverage"],
        "per_instance": development + heldout,
    }
