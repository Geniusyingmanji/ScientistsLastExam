"""Deterministic oracle for active FRAP diffusion-binding inference."""
from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np


RADII = (0.8, 1.2, 1.8, 2.6)
TIMES = (0.05, 0.10, 0.20, 0.40, 0.80, 1.60, 3.20, 6.40, 12.80, 25.60)
BUDGET = 16
RADIUS_SETUP_COST = 4
MIN_EVIDENCE = 4
PREDICTION_CONTEXTS = (
    (0.9, 0.15), (1.0, 1.0), (1.4, 0.55), (1.5, 5.0),
    (2.1, 2.2), (2.2, 16.0), (3.0, 7.5), (3.2, 30.0),
)
PARAMETER_BOUNDS = {
    "diffusion_coefficient_um2_s": (0.08, 2.5),
    "mobile_fraction": (0.55, 0.99),
    "binding_on_rate_s": (0.03, 1.8),
    "binding_off_rate_s": (0.015, 0.8),
}
ALLOWED_DIAGNOSES = {
    "supported",
    "anomalous_transport",
    "two_mobile_pools",
    "spatially_varying_binding",
    "undetermined",
}


DEVELOPMENT_WORLDS = (
    {"kind": "supported", "seed": 73101, "d": 0.28, "mobile": 0.84, "kon": 0.22, "koff": 0.08, "noise": 0.008},
    {"kind": "supported", "seed": 73102, "d": 0.85, "mobile": 0.76, "kon": 0.65, "koff": 0.20, "noise": 0.009},
    {"kind": "supported", "seed": 73103, "d": 1.55, "mobile": 0.91, "kon": 0.12, "koff": 0.35, "noise": 0.007},
    {"kind": "anomalous_transport", "seed": 73104, "d": 0.62, "mobile": 0.82, "alpha": 0.58, "noise": 0.008},
    {"kind": "two_mobile_pools", "seed": 73105, "mobile": 0.88, "d1": 0.12, "d2": 1.65, "weight": 0.46, "noise": 0.008},
    {"kind": "spatially_varying_binding", "seed": 73106, "d": 0.72, "mobile": 0.80, "kon": 0.38, "koff": 0.14, "slope": 1.15, "noise": 0.008},
)

HELDOUT_WORLDS = (
    {"kind": "supported", "seed": 73201, "d": 0.45, "mobile": 0.88, "kon": 0.95, "koff": 0.12, "noise": 0.009},
    {"kind": "supported", "seed": 73202, "d": 1.15, "mobile": 0.72, "kon": 0.35, "koff": 0.06, "noise": 0.008},
    {"kind": "anomalous_transport", "seed": 73203, "d": 1.10, "mobile": 0.77, "alpha": 0.68, "noise": 0.009},
    {"kind": "two_mobile_pools", "seed": 73204, "mobile": 0.83, "d1": 0.20, "d2": 2.05, "weight": 0.62, "noise": 0.008},
    {"kind": "spatially_varying_binding", "seed": 73205, "d": 0.36, "mobile": 0.90, "kon": 0.72, "koff": 0.09, "slope": -1.05, "noise": 0.008},
)


def supported_recovery(d, mobile, kon, koff, radius, time):
    """Single radial-mode reaction-diffusion recovery from the public model."""
    d = float(d)
    mobile = float(mobile)
    kon = float(kon)
    koff = np.asarray(koff, dtype=float)
    radius = np.asarray(radius, dtype=float)
    time = np.asarray(time, dtype=float)
    lam = 4.0 * d / np.square(radius)
    free_fraction = koff / (kon + koff)
    trace = lam + kon + koff
    discriminant = np.sqrt(np.maximum(trace * trace - 4.0 * lam * koff, 1e-14))
    fast = 0.5 * (trace + discriminant)
    slow = 0.5 * (trace - discriminant)
    fast_weight = (lam * free_fraction - slow) / discriminant
    deficit = fast_weight * np.exp(-fast * time) + (1.0 - fast_weight) * np.exp(-slow * time)
    return np.clip(mobile * (1.0 - deficit), 0.0, 1.0)


def _truth_recovery(spec, radius, time):
    kind = spec["kind"]
    radius = np.asarray(radius, dtype=float)
    time = np.asarray(time, dtype=float)
    if kind == "supported":
        return supported_recovery(spec["d"], spec["mobile"], spec["kon"], spec["koff"], radius, time)
    if kind == "anomalous_transport":
        scaled = np.power(np.maximum(4.0 * spec["d"] * time / np.square(radius), 0.0), spec["alpha"])
        return np.clip(spec["mobile"] * (1.0 - np.exp(-scaled)), 0.0, 1.0)
    if kind == "two_mobile_pools":
        first = np.exp(-4.0 * spec["d1"] * time / np.square(radius))
        second = np.exp(-4.0 * spec["d2"] * time / np.square(radius))
        deficit = spec["weight"] * first + (1.0 - spec["weight"]) * second
        return np.clip(spec["mobile"] * (1.0 - deficit), 0.0, 1.0)
    varying_koff = spec["koff"] * np.power(radius / 1.5, spec["slope"])
    return supported_recovery(spec["d"], spec["mobile"], spec["kon"], varying_koff, radius, time)


def public_problem():
    return {
        "bleach_radii_um": list(RADII),
        "sample_times_s": list(TIMES),
        "measurement_budget_units": BUDGET,
        "minimum_evidence_measurements": MIN_EVIDENCE,
        "prediction_contexts": [
            {"radius_um": radius, "time_s": time}
            for radius, time in PREDICTION_CONTEXTS
        ],
        "parameter_bounds": {key: list(value) for key, value in PARAMETER_BOUNDS.items()},
        "model_family": "one freely diffusing pool reversibly exchanges with one immobile bound pool; radial transport rate is 4*D/radius_um**2 and binding rates are radius-independent",
        "unsupported_families": ["anomalous_transport", "two_mobile_pools", "spatially_varying_binding"],
        "measurement_model": "the first measure call at each distinct radius costs five units (four setup plus one measurement); later calls at that radius cost one unit; each returns a noisy normalized recovery fraction with a standard error and immutable measurement_id",
        "abstain_when": "use the matching unsupported diagnosis and abstain when cross-radius recovery is inconsistent with the supported diffusion-binding family; use undetermined only when evidence is insufficient",
    }


class _Measurement:
    def __init__(self, spec):
        self.spec = spec
        self.spent = 0
        self.calls = 0
        self.repeat_counts = {}
        self.configured_radii = set()
        self.ids = set()
        self.violated = False

    def _reject(self, message, exc_type=ValueError):
        self.violated = True
        raise exc_type(message)

    def __call__(self, radius_um, time_s):
        if isinstance(radius_um, bool) or isinstance(time_s, bool):
            self._reject("radius_um and time_s must be numbers")
        try:
            radius = float(radius_um)
            time = float(time_s)
        except (TypeError, ValueError):
            self._reject("radius_um and time_s must be numbers")
        if not math.isfinite(radius) or not any(abs(radius - value) < 1e-9 for value in RADII):
            self._reject("radius_um is not in bleach_radii_um")
        if not math.isfinite(time) or not any(abs(time - value) < 1e-9 for value in TIMES):
            self._reject("time_s is not in sample_times_s")
        cost = 1 + (RADIUS_SETUP_COST if radius not in self.configured_radii else 0)
        if self.spent + cost > BUDGET:
            self._reject("measurement budget exceeded", RuntimeError)
        pair = (radius, time)
        repeat = self.repeat_counts.get(pair, 0) + 1
        self.repeat_counts[pair] = repeat
        self.calls += 1
        self.spent += cost
        self.configured_radii.add(radius)
        token = "%s|%.8f|%.8f|%d" % (self.spec["seed"], radius, time, repeat)
        seed = int.from_bytes(hashlib.sha256(token.encode("ascii")).digest()[:8], "little")
        noise = float(np.random.default_rng(seed).normal(0.0, self.spec["noise"]))
        truth = float(_truth_recovery(self.spec, radius, time))
        measurement_id = "m%02d" % self.calls
        self.ids.add(measurement_id)
        return {
            "measurement_id": measurement_id,
            "radius_um": radius,
            "time_s": time,
            "recovery_fraction": round(float(np.clip(truth + noise, 0.0, 1.0)), 7),
            "recovery_standard_error": float(self.spec["noise"]),
            "cost_units": cost,
            "spent_units": self.spent,
        }


def _finite_number(value, name):
    if isinstance(value, bool):
        raise ValueError(name + " must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(name + " must be finite")
    return number


def _validate(submission, measurement):
    required = {
        "diagnosis", "diffusion_coefficient_um2_s", "mobile_fraction",
        "binding_on_rate_s", "binding_off_rate_s", "predicted_recovery",
        "confidence", "abstain", "evidence_measurement_ids",
    }
    if not isinstance(submission, dict) or set(submission) != required:
        raise ValueError("submission must contain exactly the documented keys")
    diagnosis = submission["diagnosis"]
    if not isinstance(diagnosis, str) or diagnosis not in ALLOWED_DIAGNOSES:
        raise ValueError("diagnosis is not allowed")
    abstain = submission["abstain"]
    if not isinstance(abstain, bool):
        raise ValueError("abstain must be a boolean")
    if (diagnosis == "supported") == abstain or (diagnosis != "supported") != abstain:
        raise ValueError("supported requires abstain=false and every other diagnosis requires abstain=true")
    values = {}
    for key, bounds in PARAMETER_BOUNDS.items():
        value = _finite_number(submission[key], key)
        if not bounds[0] <= value <= bounds[1]:
            raise ValueError(key + " is outside parameter_bounds")
        values[key] = value
    confidence = _finite_number(submission["confidence"], "confidence")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must lie in [0, 1]")
    predictions = submission["predicted_recovery"]
    if not isinstance(predictions, list) or len(predictions) != len(PREDICTION_CONTEXTS):
        raise ValueError("predicted_recovery has the wrong length")
    predictions = [_finite_number(value, "predicted_recovery") for value in predictions]
    if any(not 0.0 <= value <= 1.0 for value in predictions):
        raise ValueError("predicted_recovery values must lie in [0, 1]")
    evidence = submission["evidence_measurement_ids"]
    if not isinstance(evidence, list) or any(not isinstance(value, str) for value in evidence):
        raise ValueError("evidence_measurement_ids must be a list of strings")
    if len(evidence) != len(set(evidence)) or not set(evidence).issubset(measurement.ids):
        raise ValueError("evidence_measurement_ids must cite distinct current-world measurements")
    required_evidence = 1 if diagnosis == "undetermined" else MIN_EVIDENCE
    if len(evidence) < required_evidence:
        raise ValueError("insufficient evidence for this diagnosis")
    return {
        **values,
        "diagnosis": diagnosis,
        "abstain": abstain,
        "confidence": confidence,
        "predictions": np.asarray(predictions, dtype=float),
        "evidence": evidence,
    }


def _score(spec, claim):
    kind = spec["kind"]
    supported = kind == "supported"
    false_discovery = not supported and not claim["abstain"]
    correct_refusal = not supported and claim["abstain"] and claim["diagnosis"] == kind
    unwarranted_refusal = supported and claim["abstain"]
    parameter_score = 0.0
    prediction_score = 0.0
    science_score = 0.0
    if supported and not claim["abstain"] and claim["diagnosis"] == "supported":
        component_scores = (
            math.exp(-abs(math.log(claim["diffusion_coefficient_um2_s"] / spec["d"])) / 0.30),
            math.exp(-abs(claim["mobile_fraction"] - spec["mobile"]) / 0.08),
            math.exp(-abs(math.log(claim["binding_on_rate_s"] / spec["kon"])) / 0.45),
            math.exp(-abs(math.log(claim["binding_off_rate_s"] / spec["koff"])) / 0.45),
        )
        parameter_score = float(np.prod(component_scores) ** 0.25)
        truth = _truth_recovery(
            spec,
            np.array([item[0] for item in PREDICTION_CONTEXTS]),
            np.array([item[1] for item in PREDICTION_CONTEXTS]),
        )
        rmse = float(np.sqrt(np.mean(np.square(claim["predictions"] - truth))))
        prediction_score = math.exp(-((rmse / 0.08) ** 2))
        science_score = 0.68 * parameter_score + 0.32 * prediction_score
    elif correct_refusal:
        science_score = 1.0
        prediction_score = 1.0
    confidence_score = max(0.0, 1.0 - abs(claim["confidence"] - science_score))
    combined = science_score * (0.9 + 0.1 * confidence_score)
    return {
        "combined_score": round(combined, 6),
        "science_score": round(science_score, 6),
        "parameter_recovery_score": round(parameter_score, 6),
        "prediction_score": round(prediction_score, 6),
        "confidence_calibration_score": round(confidence_score, 6),
        "correct_refusal": bool(correct_refusal),
        "false_discovery": bool(false_discovery),
        "unwarranted_refusal": bool(unwarranted_refusal),
    }


def _evaluate_world(spec, split, index, candidate):
    measurement = _Measurement(spec)
    base = {"split": split, "world_index": index, "kind": spec["kind"]}
    try:
        claim = _validate(candidate(public_problem(), measurement), measurement)
        if measurement.violated:
            raise ValueError("candidate violated the measurement contract")
        return {
            **base,
            **_score(spec, claim),
            "valid": True,
            "abstained": claim["abstain"],
            "confidence": round(claim["confidence"], 6),
            "evidence_count": len(claim["evidence"]),
            "budget_used": measurement.spent,
        }
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
            "unwarranted_refusal": False,
            "valid": False,
            "abstained": True,
            "confidence": 0.0,
            "evidence_count": 0,
            "budget_used": measurement.spent,
            "reason": "%s: %s" % (type(exc).__name__, exc),
        }


def _summary(rows):
    supported = [row for row in rows if row["kind"] == "supported"]
    unsupported = [row for row in rows if row["kind"] != "supported"]
    attempts = [row for row in rows if not row["abstained"]]
    refusal_rate = float(np.mean([row["correct_refusal"] for row in unsupported])) if unsupported else 0.0
    supported_science = float(np.mean([row["combined_score"] for row in supported])) if supported else 0.0
    return {
        "combined_score": round(supported_science * refusal_rate, 6),
        "valid": float(all(row["valid"] for row in rows)),
        "science_score": round(float(np.mean([row["science_score"] for row in rows])), 6),
        "parameter_recovery_score": round(float(np.mean([row["parameter_recovery_score"] for row in supported])), 6),
        "prediction_score": round(float(np.mean([row["prediction_score"] for row in supported])), 6),
        "correct_refusal_rate": round(float(np.mean([row["correct_refusal"] for row in unsupported])), 6),
        "correct_refusal_count": sum(row["correct_refusal"] for row in unsupported),
        "false_discovery_rate": round(float(np.mean([row["false_discovery"] for row in unsupported])), 6),
        "false_discovery_count": sum(row["false_discovery"] for row in unsupported),
        "unsupported_world_count": len(unsupported),
        "supported_discovery_coverage": round(float(np.mean([not row["abstained"] for row in supported])), 6),
        "supported_discovery_count": sum(not row["abstained"] for row in supported),
        "supported_world_count": len(supported),
        "unwarranted_refusal_rate": round(float(np.mean([row["unwarranted_refusal"] for row in supported])), 6),
        "attempted_discovery_rate": round(len(attempts) / len(rows), 6),
        "attempted_discovery_count": len(attempts),
        "world_count": len(rows),
    }


def _mechanism_correct(row):
    if not row["valid"]:
        return False
    if row["kind"] == "supported":
        return row.get("science_score", 0.0) >= 0.5
    return row["correct_refusal"]


def evaluate(candidate) -> dict[str, Any]:
    development = [_evaluate_world(spec, "development", i, candidate) for i, spec in enumerate(DEVELOPMENT_WORLDS)]
    heldout = [_evaluate_world(spec, "heldout", i, candidate) for i, spec in enumerate(HELDOUT_WORLDS)]
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
        "development_mechanism_score": sum(map(_mechanism_correct, development)) / len(development),
        "heldout_mechanism_score": sum(map(_mechanism_correct, heldout)) / len(heldout),
        "development_mechanism_correct_count": sum(map(_mechanism_correct, development)),
        "heldout_mechanism_correct_count": sum(map(_mechanism_correct, heldout)),
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
