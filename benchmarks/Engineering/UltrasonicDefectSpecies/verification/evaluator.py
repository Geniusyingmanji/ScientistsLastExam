"""Frozen pulse-echo A-scan oracle for defect-species identification."""
from __future__ import annotations

import math

import numpy as np

MEASURE_BUDGET = 14
T_BOUNDS = (0.8, 20.0)
WAVE_SPEED = 5.9  # mm / us, longitudinal steel
SUPPORTED = {"crack", "pore", "lack_of_fusion", "none"}

PUBLIC_PROBLEM = {
    "time_bounds_us": list(T_BOUNDS),
    "measure_budget_calls": MEASURE_BUDGET,
    "family_names": ["crack", "pore", "lack_of_fusion", "none"],
    "wave_speed_mm_per_us": WAVE_SPEED,
    "measurement_model": (
        "measure(time_us) returns a frozen pulse-echo amplitude plus Gaussian noise"
    ),
    "abstain_when": (
        "two defect species are present, or a mode-converted extra echo makes a "
        "single-species family non-unique"
    ),
}


def public_problem():
    return dict(PUBLIC_PROBLEM)


def _echo(time, center, amplitude, width):
    return amplitude * math.exp(-0.5 * ((time - center) / max(width, 1e-6)) ** 2)


def _arrival(depth_mm):
    return 2.0 * float(depth_mm) / WAVE_SPEED


def true_trace(spec, time):
    kind = spec["kind"]
    time = float(time)
    if kind == "none":
        return 0.0
    if kind == "crack":
        return _echo(time, _arrival(spec["depth_mm"]), -1.15, 0.16)
    if kind == "pore":
        t0 = _arrival(spec["depth_mm"])
        return (
            _echo(time, t0, 0.58, 0.32)
            + _echo(time, t0 + 0.85, 0.20, 0.28)
        )
    if kind == "lack_of_fusion":
        t0 = _arrival(spec["depth_mm"])
        return (
            _echo(time, t0, 0.72, 0.18)
            + _echo(time, t0 + 0.55, 0.62, 0.18)
        )
    if kind == "mixture":
        crack = _echo(time, _arrival(spec["depth_mm"]), -1.10, 0.16)
        pore = _echo(time, _arrival(spec["second_depth_mm"]), 0.55, 0.30)
        return crack + pore
    if kind == "mode_convert":
        t0 = _arrival(spec["depth_mm"])
        return (
            _echo(time, t0, -1.05, 0.16)
            + _echo(time, t0 + spec["delay_us"], 0.70, 0.20)
        )
    raise ValueError("unknown family")


class _Lab:
    def __init__(self, spec):
        self.spec = spec
        self.used = 0
        self.violated = False

    def measure(self, time_us):
        time = float(time_us)
        if not math.isfinite(time):
            raise ValueError("time must be finite")
        if not (T_BOUNDS[0] <= time <= T_BOUNDS[1]):
            raise ValueError("assay outside time_bounds_us")
        if self.used >= MEASURE_BUDGET:
            self.violated = True
            raise RuntimeError("measure budget exhausted")
        self.used += 1
        rng = np.random.default_rng((int(self.spec["seed"]), 11, self.used))
        return float(true_trace(self.spec, time) + 0.028 * rng.normal())


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
    family = submission.get("species")
    if family not in PUBLIC_PROBLEM["family_names"]:
        raise ValueError("species must be one of family_names")
    return False, family, confidence


def _mechanism(spec, abstain, family):
    if spec["kind"] not in SUPPORTED:
        return (1.0 if abstain else 0.0), bool(abstain), (not abstain)
    if abstain:
        return 0.0, False, False
    return (1.0 if family == spec["kind"] else 0.0), False, False


DEVELOPMENT_WORLDS = (
    {"kind": "crack", "seed": 51001, "depth_mm": 11.0},
    {"kind": "pore", "seed": 51002, "depth_mm": 18.0},
    {"kind": "lack_of_fusion", "seed": 51003, "depth_mm": 14.0},
    {"kind": "none", "seed": 51004},
    {"kind": "mixture", "seed": 52001, "depth_mm": 10.325, "second_depth_mm": 23.6},
    {"kind": "mode_convert", "seed": 52002, "depth_mm": 10.325, "delay_us": 4.5},
    {"kind": "mixture", "seed": 52003, "depth_mm": 13.275, "second_depth_mm": 29.5},
)
HELDOUT_WORLDS = (
    {"kind": "crack", "seed": 61001, "depth_mm": 13.0},
    {"kind": "pore", "seed": 61002, "depth_mm": 16.0},
    {"kind": "lack_of_fusion", "seed": 61003, "depth_mm": 12.0},
    {"kind": "none", "seed": 61004},
    {"kind": "mode_convert", "seed": 62001, "depth_mm": 7.375, "delay_us": 5.5},
    {"kind": "mixture", "seed": 62002, "depth_mm": 16.225, "second_depth_mm": 29.5},
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


def evaluate(identify_species):
    development = _run(identify_species, DEVELOPMENT_WORLDS, "development")
    heldout = _run(identify_species, HELDOUT_WORLDS, "heldout", reset_before_first=True)
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
