"""Frozen SAXS-like oracle for diblock melt morphology identification."""
from __future__ import annotations

import math

import numpy as np

MEASURE_BUDGET = 16
Q_BOUNDS = (0.15, 2.4)
SUPPORTED = {"lamella", "hex", "bcc", "gyroid", "disorder"}
RATIOS = {
    "lamella": (1.0, 2.0, 3.0, 4.0),
    "hex": (1.0, math.sqrt(3.0), 2.0, math.sqrt(7.0)),
    "bcc": (1.0, math.sqrt(2.0), math.sqrt(3.0), 2.0),
    "gyroid": (1.0, math.sqrt(4.0 / 3.0), math.sqrt(7.0 / 3.0), math.sqrt(8.0 / 3.0)),
}

PUBLIC_PROBLEM = {
    "q_bounds_nm_inv": list(Q_BOUNDS),
    "measure_budget_calls": MEASURE_BUDGET,
    "family_names": ["lamella", "hex", "bcc", "gyroid", "disorder"],
    "measurement_model": (
        "measure(q_nm_inv) returns I(q) from a frozen one-dimensional SAXS trace "
        "plus Gaussian noise; q is in 1/nm"
    ),
    "abstain_when": (
        "the trace is a kinetically trapped mixture of two lattices, or an ABC "
        "triblock with two independent q* families"
    ),
}


def public_problem():
    return dict(PUBLIC_PROBLEM)


def _trace(spec, q):
    kind = spec["kind"]
    qstar = float(spec["qstar"])
    q = max(float(q), 1e-6)
    if kind == "disorder":
        # Leibler-like RPA peak, no Bragg harmonics.
        x = (q / qstar - 1.0) ** 2
        return 1.4 / (0.12 + x)
    if kind == "mixture":
        first = _ordered("lamella", qstar, q)
        second = _ordered("hex", 1.22 * qstar, q)
        return 0.55 * first + 0.45 * second
    if kind == "abc":
        return _ordered("lamella", qstar, q) + 0.7 * _ordered("bcc", 1.55 * qstar, q)
    return _ordered(kind, qstar, q)


def _ordered(kind, qstar, q):
    intensity = 0.15
    for index, ratio in enumerate(RATIOS[kind]):
        center = qstar * ratio
        width = 0.024 * (1.0 + 0.28 * index)
        height = 2.4 / (1.0 + 0.55 * index)
        intensity += height * math.exp(-0.5 * ((q - center) / width) ** 2)
    return intensity


class _Lab:
    def __init__(self, spec):
        self.spec = spec
        self.used = 0
        self.violated = False

    def measure(self, q_nm_inv):
        q = float(q_nm_inv)
        if not math.isfinite(q):
            raise ValueError("q must be finite")
        if not (Q_BOUNDS[0] <= q <= Q_BOUNDS[1]):
            raise ValueError("q outside q_bounds_nm_inv")
        if self.used >= MEASURE_BUDGET:
            self.violated = True
            raise RuntimeError("measure budget exhausted")
        self.used += 1
        rng = np.random.default_rng((int(self.spec["seed"]), 5, self.used))
        return float(_trace(self.spec, q) + 0.05 * rng.normal())


def _validate(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = submission.get("abstain", False)
    if not isinstance(abstain, bool):
        raise ValueError("abstain must be a boolean")
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must lie in [0, 1]")
    if abstain:
        return True, None, confidence
    family = submission.get("morphology")
    if family not in PUBLIC_PROBLEM["family_names"]:
        raise ValueError("morphology must be one of family_names")
    return False, family, confidence


def _mechanism(spec, abstain, family):
    if spec["kind"] not in SUPPORTED:
        return (1.0 if abstain else 0.0), bool(abstain), (not abstain)
    if abstain:
        return 0.0, False, False
    return (1.0 if family == spec["kind"] else 0.0), False, False


DEVELOPMENT_WORLDS = (
    {"kind": "lamella", "seed": 31001, "qstar": 0.42},
    {"kind": "hex", "seed": 31002, "qstar": 0.51},
    {"kind": "bcc", "seed": 31003, "qstar": 0.37},
    {"kind": "gyroid", "seed": 31004, "qstar": 0.46},
    {"kind": "mixture", "seed": 32001, "qstar": 0.40},
    {"kind": "abc", "seed": 32002, "qstar": 0.33},
    {"kind": "disorder", "seed": 33001, "qstar": 0.55},
)
HELDOUT_WORLDS = (
    {"kind": "lamella", "seed": 41001, "qstar": 0.48},
    {"kind": "hex", "seed": 41002, "qstar": 0.36},
    {"kind": "gyroid", "seed": 41003, "qstar": 0.44},
    {"kind": "mixture", "seed": 42001, "qstar": 0.52},
    {"kind": "abc", "seed": 42002, "qstar": 0.41},
)


def _evaluate_world(identify, spec, split, index):
    lab = _Lab(spec)
    base = {"split": split, "world_index": int(index), "kind": spec["kind"], "measure_calls": 0}
    try:
        submission = identify(public_problem(), lab.measure)
        abstain, family, confidence = _validate(submission)
        if lab.violated:
            raise RuntimeError("measure budget exceeded")
        mech, refused, false = _mechanism(spec, abstain, family)
        return {
            **base,
            "mechanism_score": round(float(mech), 6),
            "correct_refusal": refused,
            "false_discovery": false,
            "valid": True,
            "abstained": bool(abstain),
            "confidence": round(confidence, 6),
            "measure_calls": lab.used,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            **base,
            "mechanism_score": 0.0,
            "correct_refusal": False,
            "false_discovery": False,
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "confidence": 0.0,
            "measure_calls": lab.used,
        }


def _split_summary(records):
    supported = [row for row in records if row["kind"] in SUPPORTED]
    unsupported = [row for row in records if row["kind"] not in SUPPORTED]
    raw = float(np.mean([row["mechanism_score"] for row in records]))
    always_abstain = len(unsupported) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "signal_recovery_rate": float(np.mean([row["mechanism_score"] for row in supported])),
        "false_discovery_rate": float(np.mean([row["false_discovery"] for row in unsupported])),
        "correct_refusal_rate": float(np.mean([row["correct_refusal"] for row in unsupported])),
        "discovery_coverage": float(np.mean([not row["abstained"] for row in supported])),
        "valid_count": sum(bool(row["valid"]) for row in records),
        "world_count": len(records),
    }


def _run(identify, worlds, split, reset_before_first=False):
    rows = []
    for index, spec in enumerate(worlds):
        if (index or reset_before_first) and hasattr(identify, "reset_session"):
            identify.reset_session()
        rows.append(_evaluate_world(identify, spec, split, index))
    return rows


def evaluate(identify_morphology):
    development = _run(identify_morphology, DEVELOPMENT_WORLDS, "development")
    heldout = _run(identify_morphology, HELDOUT_WORLDS, "heldout", reset_before_first=True)
    dev = _split_summary(development)
    held = _split_summary(heldout)
    return {
        "combined_score": dev["normalized_mechanism"],
        "valid": 1.0 if dev["valid_count"] > 0 else 0.0,
        "feasibility_rate": dev["valid_count"] / dev["world_count"],
        "raw_score": dev["normalized_mechanism"],
        "development_mechanism_score": dev["normalized_mechanism"],
        "development_signal_recovery_rate": dev["signal_recovery_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_signal_recovery_rate": held["signal_recovery_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
