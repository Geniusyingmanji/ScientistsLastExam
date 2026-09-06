"""Power-law versus lognormal evidence with a small-n refusal."""
from __future__ import annotations

import math

import numpy as np

EXTRA_BUDGET = 24
SUPPORTED = {"powerlaw", "lognormal"}

PUBLIC_PROBLEM_KEYS = (
    "xmin",
    "public_sample",
    "extra_draw_budget",
    "family_names",
    "abstain_when",
)


def _draw(spec, rng, size):
    kind = spec["kind"]
    xmin = float(spec["xmin"])
    if kind == "powerlaw":
        u = rng.random(size)
        return xmin * (1.0 - u) ** (-1.0 / (float(spec["alpha"]) - 1.0))
    if kind == "lognormal":
        samples = []
        while len(samples) < size:
            value = math.exp(rng.normal(spec["mu"], spec["sigma"]))
            if value >= xmin:
                samples.append(value)
        return np.asarray(samples, dtype=float)
    # exponential above xmin: neither a power law nor a lognormal
    u = np.clip(rng.random(size), 1e-12, 1.0)
    return xmin - np.log(u) * 1.8


def public_problem_for(spec):
    rng = np.random.default_rng((int(spec["seed"]), 1))
    sample = _draw(spec, rng, int(spec["n_public"]))
    return {
        "xmin": float(spec["xmin"]),
        "public_sample": [float(x) for x in sample],
        "extra_draw_budget": EXTRA_BUDGET,
        "family_names": ["powerlaw", "lognormal"],
        "abstain_when": (
            "the sample is too small to separate the families, or the tail is a "
            "stretched exponential / cutoff outside both families"
        ),
    }


class _Lab:
    def __init__(self, spec):
        self.spec = spec
        self.used = 0
        self.violated = False
        self.rng = np.random.default_rng((int(spec["seed"]), 2))

    def extra_draw(self):
        if self.used >= EXTRA_BUDGET:
            self.violated = True
            raise RuntimeError("extra_draw budget exhausted")
        self.used += 1
        return float(_draw(self.spec, self.rng, 1)[0])


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
    if family not in ("powerlaw", "lognormal"):
        raise ValueError("family must be powerlaw or lognormal")
    alpha = float(submission.get("alpha", 2.0))
    if not math.isfinite(alpha) or alpha <= 1.0:
        raise ValueError("alpha must be finite and greater than 1")
    return False, family, alpha, confidence


def _mechanism(spec, abstain, family, alpha):
    if spec["kind"] not in SUPPORTED:
        return (1.0 if abstain else 0.0), bool(abstain), (not abstain)
    if abstain:
        return 0.0, False, False
    if family != spec["kind"]:
        return 0.0, False, False
    if family == "lognormal":
        return 1.0, False, False
    err = abs(alpha - spec["alpha"]) / 0.8
    return float(np.clip(1.0 - err, 0.0, 1.0)), False, False


DEVELOPMENT_WORLDS = (
    {"kind": "powerlaw", "seed": 71001, "xmin": 1.0, "alpha": 2.3, "n_public": 80},
    {"kind": "powerlaw", "seed": 71002, "xmin": 1.0, "alpha": 2.8, "n_public": 90},
    {"kind": "lognormal", "seed": 71003, "xmin": 1.0, "mu": 0.9, "sigma": 0.55, "n_public": 90},
    {"kind": "cutoff", "seed": 72001, "xmin": 1.0, "n_public": 80},
    {"kind": "cutoff", "seed": 72002, "xmin": 1.0, "n_public": 70},
    {"kind": "small", "seed": 73001, "xmin": 1.0, "alpha": 2.4, "n_public": 12},
    {"kind": "small", "seed": 73002, "xmin": 1.0, "mu": 0.7, "sigma": 0.6, "n_public": 10},
)
HELDOUT_WORLDS = (
    {"kind": "powerlaw", "seed": 81001, "xmin": 1.0, "alpha": 2.55, "n_public": 85},
    {"kind": "lognormal", "seed": 81002, "xmin": 1.0, "mu": 1.1, "sigma": 0.50, "n_public": 85},
    {"kind": "cutoff", "seed": 82001, "xmin": 1.0, "n_public": 75},
    {"kind": "small", "seed": 83001, "xmin": 1.0, "alpha": 2.2, "n_public": 11},
    {"kind": "small", "seed": 83002, "xmin": 1.0, "mu": 0.8, "sigma": 0.45, "n_public": 9},
)


def _evaluate_world(synthesize, spec, split, index):
    lab = _Lab(spec)
    problem = public_problem_for(spec)
    base = {"split": split, "world_index": int(index), "kind": spec["kind"], "measure_calls": 0}
    try:
        submission = synthesize(problem, lab.extra_draw)
        abstain, family, alpha, confidence = _validate(submission)
        if lab.violated:
            raise RuntimeError("extra_draw budget exceeded")
        mech, refused, false = _mechanism(spec, abstain, family, alpha)
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


def _run(synthesize, worlds, split, reset_before_first=False):
    rows = []
    for index, spec in enumerate(worlds):
        if (index or reset_before_first) and hasattr(synthesize, "reset_session"):
            synthesize.reset_session()
        rows.append(_evaluate_world(synthesize, spec, split, index))
    return rows


def evaluate(synthesize_tail_evidence):
    development = _run(synthesize_tail_evidence, DEVELOPMENT_WORLDS, "development")
    heldout = _run(synthesize_tail_evidence, HELDOUT_WORLDS, "heldout", reset_before_first=True)
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
