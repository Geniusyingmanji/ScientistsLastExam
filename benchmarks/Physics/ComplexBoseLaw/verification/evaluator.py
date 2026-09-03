"""Frozen oracle for ComplexBoseLaw (hidden from the agent).

NewtonBench's hardest Bose–Einstein cell keeps the minus sign in the occupation number and
shifts the exponents. This task does the same, then hides the occupation behind a cavity that
mixes nearby modes. A Fermi (+1) occupation and a T-independent blank must be refused. This is
not DynamicalSystems/ActiveLawDiscovery (a two-state polynomial ODE) and not a fold-year
extrapolation.
"""
from __future__ import annotations

import math

import numpy as np

MEASURE_BUDGET = 36
OMEGA_BOUNDS = (0.45, 3.8)
TEMP_BOUNDS = (0.45, 2.4)
NOISE = 0.035

PUBLIC_PROBLEM = {
    "omega_bounds": [OMEGA_BOUNDS[0], OMEGA_BOUNDS[1]],
    "temperature_bounds": [TEMP_BOUNDS[0], TEMP_BOUNDS[1]],
    "measure_budget_calls": MEASURE_BUDGET,
    "family_names": ["bose", "fermi"],
    "in_family_occupation": (
        "bose: n = 1 / (exp(C * omega**alpha / temperature**beta) - 1)"
    ),
    "measurement_model": (
        "measure(omega, temperature) returns a cavity occupancy that mixes the hidden "
        "occupation at omega with two nearby frequencies; weights are unknown and fixed "
        "inside a world"
    ),
    "abstain_when": (
        "the occupancy is Fermi (+1 in the denominator) or independent of temperature"
    ),
}


def public_problem():
    return {
        "omega_bounds": list(PUBLIC_PROBLEM["omega_bounds"]),
        "temperature_bounds": list(PUBLIC_PROBLEM["temperature_bounds"]),
        "measure_budget_calls": MEASURE_BUDGET,
        "family_names": list(PUBLIC_PROBLEM["family_names"]),
        "in_family_occupation": PUBLIC_PROBLEM["in_family_occupation"],
        "measurement_model": PUBLIC_PROBLEM["measurement_model"],
        "abstain_when": PUBLIC_PROBLEM["abstain_when"],
    }


def occupation_number(family, omega, temperature, C, alpha, beta):
    omega = max(float(omega), 1e-8)
    temperature = max(float(temperature), 1e-8)
    expo = float(C) * (omega ** float(alpha)) / (temperature ** float(beta))
    expo = min(max(expo, 1e-8), 40.0)
    if family == "bose":
        return 1.0 / (math.exp(expo) - 1.0)
    if family == "fermi":
        return 1.0 / (math.exp(expo) + 1.0)
    raise ValueError("unknown family")


def _mixing(seed):
    rng = np.random.default_rng((int(seed), 3))
    weights = np.array([0.58 + 0.12 * rng.random(), 0.22 + 0.08 * rng.random(),
                        0.10 + 0.06 * rng.random()])
    weights = weights / weights.sum()
    scales = np.array([1.0, 1.12 + 0.10 * rng.random(), 0.84 - 0.08 * rng.random()])
    return weights, scales


def _hidden_n(spec, omega, temperature):
    if spec["kind"] == "blank":
        return float(spec["a"] + spec["b"] * (float(omega) ** spec["gamma"]))
    return occupation_number(
        spec["kind"], omega, temperature, spec["C"], spec["alpha"], spec["beta"]
    )


def _mixed(spec, omega, temperature, weights, scales):
    total = 0.0
    for weight, scale in zip(weights, scales):
        total += float(weight) * _hidden_n(spec, float(scale) * float(omega), temperature)
    return total


class _Lab:
    def __init__(self, spec, weights, scales):
        self.spec = spec
        self.weights = weights
        self.scales = scales
        self.used = 0
        self.violated = False
        self.calls = 0

    def measure(self, omega, temperature):
        omega = float(omega)
        temperature = float(temperature)
        if not math.isfinite(omega) or not math.isfinite(temperature):
            raise ValueError("omega and temperature must be finite")
        if not (OMEGA_BOUNDS[0] <= omega <= OMEGA_BOUNDS[1]):
            raise ValueError("omega outside omega_bounds")
        if not (TEMP_BOUNDS[0] <= temperature <= TEMP_BOUNDS[1]):
            raise ValueError("temperature outside temperature_bounds")
        if self.used >= MEASURE_BUDGET:
            self.violated = True
            raise RuntimeError("measure budget exhausted")
        self.used += 1
        self.calls += 1
        rng = np.random.default_rng((int(self.spec["seed"]), 11, self.calls))
        value = _mixed(self.spec, omega, temperature, self.weights, self.scales)
        return float(value + NOISE * rng.normal())


def _validate_submission(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = submission.get("abstain", False)
    if not isinstance(abstain, bool):
        raise ValueError("abstain must be a boolean")
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence):
        raise ValueError("confidence must be finite")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must lie in [0, 1]")
    if abstain:
        return None, None, None, None, confidence, True
    family = submission.get("family")
    if family not in PUBLIC_PROBLEM["family_names"]:
        raise ValueError("family must be one of family_names")
    C = float(submission.get("C"))
    alpha = float(submission.get("alpha"))
    beta = float(submission.get("beta"))
    if not all(math.isfinite(v) for v in (C, alpha, beta)):
        raise ValueError("C, alpha and beta must be finite")
    if C <= 0.0 or alpha <= 0.0 or beta <= 0.0:
        raise ValueError("C, alpha and beta must be positive")
    return family, C, alpha, beta, confidence, False


def _bose_mechanism(spec, family, C, alpha, beta, abstain):
    """Score exponent recovery. Mixing renormalizes C, so log-C is a weak nuisance term."""
    if abstain or family != "bose":
        return 0.0
    e_a = abs(float(alpha) - spec["alpha"]) / max(spec["alpha"], 0.5)
    e_b = abs(float(beta) - spec["beta"]) / max(spec["beta"], 0.5)
    e_c = min(1.0, abs(math.log(max(float(C), 1e-8) / spec["C"])) / 1.2)
    err = 0.45 * e_a + 0.45 * e_b + 0.10 * e_c
    return float(np.clip(1.0 - err / 0.50, 0.0, 1.0))


def _metrics(spec, family, C, alpha, beta, abstain):
    row = {
        "mechanism_score": 0.0,
        "correct_refusal": False,
        "false_discovery": False,
        "family_correct": False,
    }
    if spec["kind"] != "bose":
        claimed_bose = (not abstain) and family == "bose"
        row.update({
            "mechanism_score": 1.0 if abstain else 0.0,
            "correct_refusal": bool(abstain),
            "false_discovery": claimed_bose,
        })
        return row
    score = _bose_mechanism(spec, family, C, alpha, beta, abstain)
    row.update({
        "mechanism_score": score,
        "family_correct": (not abstain) and family == "bose" and score > 0.5,
    })
    return row


DEVELOPMENT_WORLDS = (
    {"kind": "bose", "seed": 71001, "C": 0.82, "alpha": 1.42, "beta": 1.88},
    {"kind": "bose", "seed": 71002, "C": 1.18, "alpha": 1.58, "beta": 2.16},
    {"kind": "bose", "seed": 71003, "C": 0.70, "alpha": 1.35, "beta": 2.05},
    {"kind": "fermi", "seed": 72001, "C": 1.05, "alpha": 1.50, "beta": 2.00},
    {"kind": "fermi", "seed": 72002, "C": 0.88, "alpha": 1.40, "beta": 1.90},
    {"kind": "blank", "seed": 73001, "a": 0.22, "b": 0.35, "gamma": 1.15},
    {"kind": "blank", "seed": 73002, "a": 0.40, "b": 0.18, "gamma": 0.70},
)

HELDOUT_WORLDS = (
    {"kind": "bose", "seed": 81001, "C": 0.95, "alpha": 1.52, "beta": 1.78},
    {"kind": "bose", "seed": 81002, "C": 1.25, "alpha": 1.68, "beta": 2.22},
    {"kind": "fermi", "seed": 82001, "C": 0.78, "alpha": 1.62, "beta": 2.10},
    {"kind": "blank", "seed": 83001, "a": 0.15, "b": 0.50, "gamma": 0.90},
    {"kind": "blank", "seed": 83002, "a": 0.55, "b": 0.12, "gamma": 1.40},
)

ROW_KEYS = ("mechanism_score", "correct_refusal", "false_discovery", "family_correct")


def _evaluate_world(interpret_cavity, spec, split, index):
    weights, scales = _mixing(spec["seed"])
    lab = _Lab(spec, weights, scales)
    problem = public_problem()
    base = {"split": split, "world_index": int(index), "kind": spec["kind"], "measure_calls": 0}
    try:
        submission = interpret_cavity(problem, lab.measure)
        family, C, alpha, beta, confidence, abstain = _validate_submission(submission)
        if lab.violated:
            raise RuntimeError("measure budget exceeded")
        metrics = _metrics(spec, family, C, alpha, beta, abstain)
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": bool(abstain),
            "claimed_bose": (not abstain) and family == "bose",
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(
                1.0 - (confidence - metrics["mechanism_score"]) ** 2, 6
            ),
            "measure_calls": lab.used,
        })
        row["mechanism_score"] = round(float(row["mechanism_score"]), 6)
        return row
    except Exception as exc:  # noqa: BLE001
        row = dict(base)
        row.update({key: (0.0 if key.endswith("_score") else False) for key in ROW_KEYS})
        row.update({
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "claimed_bose": False,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "measure_calls": lab.used,
        })
        return row


def _split_summary(records):
    determinable = [r for r in records if r["kind"] == "bose"]
    unsupported = [r for r in records if r["kind"] != "bose"]
    raw = float(np.mean([r["mechanism_score"] for r in records]))
    always_abstain = len(unsupported) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "signal_recovery_rate": float(np.mean([r["mechanism_score"] for r in determinable])),
        "false_discovery_rate": float(np.mean([r["false_discovery"] for r in unsupported])),
        "correct_refusal_rate": float(np.mean([r["correct_refusal"] for r in unsupported])),
        "discovery_coverage": float(np.mean([not r["abstained"] for r in determinable])),
        "confidence_calibration": float(np.mean([r["confidence_calibration_score"] for r in records])),
        "mean_measure_calls": float(np.mean([r["measure_calls"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def _evaluate_specs(interpret_cavity, specs, split, *, reset_before_first=False):
    records = []
    for index, spec in enumerate(specs):
        if (index or reset_before_first) and hasattr(interpret_cavity, "reset_session"):
            interpret_cavity.reset_session()
        records.append(_evaluate_world(interpret_cavity, spec, split, index))
    return records


def evaluate(interpret_cavity):
    development = _evaluate_specs(interpret_cavity, DEVELOPMENT_WORLDS, "development")
    heldout = _evaluate_specs(
        interpret_cavity, HELDOUT_WORLDS, "heldout", reset_before_first=True
    )
    dev = _split_summary(development)
    held = _split_summary(heldout)
    return {
        "combined_score": dev["normalized_mechanism"],
        "valid": 1.0 if dev["valid_count"] > 0 else 0.0,
        "feasibility_rate": dev["valid_count"] / dev["world_count"],
        "raw_score": dev["normalized_mechanism"],
        "development_mechanism_score": dev["normalized_mechanism"],
        "development_raw_mechanism": dev["raw_mechanism"],
        "development_signal_recovery_rate": dev["signal_recovery_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_measure_calls": dev["mean_measure_calls"],
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_signal_recovery_rate": held["signal_recovery_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
