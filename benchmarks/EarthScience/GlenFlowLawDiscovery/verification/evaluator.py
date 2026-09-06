"""Frozen Glen-flow oracle: recover n, or refuse when sliding mixes the slope."""
from __future__ import annotations

import math

import numpy as np

MEASURE_BUDGET = 12
TAU_BOUNDS = (20.0, 200.0)
SUPPORTED = {"glen", "newtonian"}

PUBLIC_PROBLEM = {
    "stress_bounds_kPa": list(TAU_BOUNDS),
    "measure_budget_calls": MEASURE_BUDGET,
    "family_names": ["glen", "newtonian"],
    "rate_law": (
        "v = A * tau^n; Glen ice has n near 3; Newtonian viscous ice has n = 1"
    ),
    "measurement_model": (
        "measure(stress_kPa) returns ln of surface speed plus frozen Gaussian noise"
    ),
    "abstain_when": (
        "basal sliding makes the log-log slope curved or puts n outside the family"
    ),
}


def public_problem():
    return dict(PUBLIC_PROBLEM)


def true_speed(spec, stress):
    stress = max(float(stress), 1e-6)
    kind = spec["kind"]
    if kind == "glen":
        return float(spec["A"]) * stress ** 3.0
    if kind == "newtonian":
        return float(spec["A"]) * stress
    if kind == "sliding":
        return float(spec["A"]) * stress ** 3.0 + float(spec["C"]) * stress
    if kind == "plug":
        return float(spec["C"])
    raise ValueError("unknown family")


class _Lab:
    def __init__(self, spec):
        self.spec = spec
        self.used = 0
        self.violated = False

    def measure(self, stress_kPa):
        stress = float(stress_kPa)
        if not math.isfinite(stress):
            raise ValueError("stress must be finite")
        if not (TAU_BOUNDS[0] <= stress <= TAU_BOUNDS[1]):
            raise ValueError("assay outside stress_bounds_kPa")
        if self.used >= MEASURE_BUDGET:
            self.violated = True
            raise RuntimeError("measure budget exhausted")
        self.used += 1
        rng = np.random.default_rng((int(self.spec["seed"]), 19, self.used))
        return float(math.log(max(true_speed(self.spec, stress), 1e-30)) + 0.03 * rng.normal())


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
        return True, None, None, confidence
    family = submission.get("family")
    if family not in PUBLIC_PROBLEM["family_names"]:
        raise ValueError("family must be one of family_names")
    exponent = float(submission.get("n"))
    if not math.isfinite(exponent) or exponent <= 0.0:
        raise ValueError("n must be a positive finite number")
    return False, family, exponent, confidence


def _mechanism(spec, abstain, family, exponent):
    if spec["kind"] not in SUPPORTED:
        return (1.0 if abstain else 0.0), bool(abstain), (not abstain)
    if abstain:
        return 0.0, False, False
    true_n = 3.0 if spec["kind"] == "glen" else 1.0
    family_err = 0.0 if family == spec["kind"] else 0.85
    n_err = min(abs(float(exponent) - true_n) / 0.35, 1.0)
    err = 0.55 * family_err + 0.45 * n_err
    return float(np.clip(1.0 - err / 0.55, 0.0, 1.0)), False, False


DEVELOPMENT_WORLDS = (
    {"kind": "glen", "seed": 71001, "A": 2.0e-7},
    {"kind": "glen", "seed": 71002, "A": 5.5e-7},
    {"kind": "newtonian", "seed": 71003, "A": 0.012},
    {"kind": "sliding", "seed": 72001, "A": 1.0e-5, "C": 0.05},
    {"kind": "sliding", "seed": 72002, "A": 3.0e-6, "C": 0.01},
    {"kind": "sliding", "seed": 72003, "A": 2.0e-7, "C": 8.0e-7},
    {"kind": "plug", "seed": 73001, "C": 0.45},
    {"kind": "plug", "seed": 73002, "C": 1.2},
)
HELDOUT_WORLDS = (
    {"kind": "glen", "seed": 81001, "A": 3.4e-7},
    {"kind": "newtonian", "seed": 81002, "A": 0.008},
    {"kind": "sliding", "seed": 82001, "A": 1.0e-5, "C": 0.05},
    {"kind": "plug", "seed": 83001, "C": 0.7},
    {"kind": "sliding", "seed": 82002, "A": 3.0e-5, "C": 0.2},
    {"kind": "sliding", "seed": 82003, "A": 3.4e-7, "C": 1.2e-6},
)


def _evaluate_world(identify, spec, split, index):
    lab = _Lab(spec)
    base = {"split": split, "world_index": int(index), "kind": spec["kind"], "measure_calls": 0}
    try:
        submission = identify(public_problem(), lab.measure)
        abstain, family, exponent, confidence = _validate(submission)
        if lab.violated:
            raise RuntimeError("measure budget exceeded")
        mech, refused, false = _mechanism(spec, abstain, family, exponent)
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


def evaluate(identify_flow_law):
    development = _run(identify_flow_law, DEVELOPMENT_WORLDS, "development")
    heldout = _run(identify_flow_law, HELDOUT_WORLDS, "heldout", reset_before_first=True)
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
