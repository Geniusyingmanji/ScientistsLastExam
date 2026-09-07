"""Deterministic reduced-order microlensing observation and scoring oracle."""
from __future__ import annotations

import hashlib
import math

import numpy as np

TIMES = tuple(round(-24.0 + 2.0 * i, 3) for i in range(25))
FILTERS = ("g", "r")
BUDGET = 24
MIN_EVIDENCE = 6


def _paczynski(t, t0, timescale, u0):
    u = math.sqrt(u0 * u0 + ((t - t0) / timescale) ** 2)
    return (u * u + 2.0) / (u * math.sqrt(u * u + 4.0))


def _world(spec):
    return dict(spec)


def _flux(world, time, band):
    t = float(time)
    base = 1.0 if band == "r" else 0.78
    band_scale = 1.0 if band == "r" else 0.82
    kind = world["kind"]
    if kind in {"point", "binary", "ambiguous"}:
        magnification = _paczynski(t, world["t0"], world["timescale"], world["u0"])
        value = base + band_scale * world["source_scale"] * (magnification - 1.0)
        if kind == "binary":
            value += world["anomaly_amp"] * band_scale * math.exp(
                -0.5 * ((t - world["anomaly_time"]) / world["anomaly_width"]) ** 2)
    else:
        value = base + world["variability_amp"] * band_scale * math.sin(
            2.0 * math.pi * (t - world["phase"]) / world["period"])
        value += 0.035 * band_scale * math.cos(2.0 * math.pi * t / 11.0)
    digest = hashlib.sha256(
        ("%d|%.3f|%s" % (world["seed"], t, band)).encode("ascii")
    ).digest()
    seed = int.from_bytes(digest[:8], "little") & 0xFFFFFFFF
    noise = float(np.random.default_rng(seed).normal(0.0, world["noise"]))
    return value + noise


class _Observer:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.seen = set()
        self.violated = False

    def __call__(self, time, band):
        try:
            time = float(time)
        except (TypeError, ValueError) as exc:
            self.violated = True
            raise ValueError("time must be numeric") from exc
        if not any(abs(time - allowed) < 1e-9 for allowed in TIMES):
            self.violated = True
            raise ValueError("time is not an allowed epoch")
        if band not in FILTERS:
            self.violated = True
            raise ValueError("band must be g or r")
        key = (round(time, 3), band)
        if key in self.seen:
            self.violated = True
            raise ValueError("duplicate observation")
        if self.used + 1 > BUDGET:
            self.violated = True
            raise RuntimeError("observation budget exceeded")
        self.seen.add(key)
        self.used += 1
        self.calls += 1
        return {
            "query_id": "q%02d" % self.calls,
            "time": key[0],
            "band": band,
            "flux": _flux(self.world, key[0], band),
            "uncertainty": self.world["noise"],
            "budget_used": self.used,
        }


PUBLIC_PROBLEM = {
    "candidate_times": list(TIMES),
    "filters": ["g", "r"],
    "filter_costs": {"g": 1, "r": 1},
    "observation_budget_units": BUDGET,
    "minimum_evidence_queries": MIN_EVIDENCE,
    "model_labels": ["point_lens", "binary_lens", "variable_source"],
    "timescale_bounds_days": [2.0, 20.0],
    "amplitude_bounds": [0.0, 1.0],
    "magnification_model": "Paczynski point-lens magnification with a possible localized binary-lens anomaly",
    "variability_model": "smooth sinusoidal source variability with a band-independent period",
    "abstain_when": "the observations do not distinguish a supported model from the ambiguous low-SNR family",
    "evidence_requirement": "cite at least six distinct query_id values from current-world observations",
}


def _validate(submission, query_ids):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = submission.get("abstain", False)
    if not isinstance(abstain, bool):
        raise ValueError("abstain must be boolean")
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be finite in [0,1]")
    evidence = submission.get("evidence_query_ids", [])
    if not isinstance(evidence, list) or len(evidence) < MIN_EVIDENCE:
        raise ValueError("at least six evidence ids are required")
    if len(evidence) != len(set(evidence)) or not set(evidence).issubset(query_ids):
        raise ValueError("evidence ids must be distinct current-world queries")
    if abstain:
        return {"abstain": True, "confidence": confidence, "evidence": evidence}
    model = submission.get("model")
    if model not in {"point_lens", "binary_lens", "variable_source"}:
        raise ValueError("unknown model")
    timescale = float(submission.get("timescale_days", float("nan")))
    amplitude = float(submission.get("amplitude", float("nan")))
    if not math.isfinite(timescale) or not 2.0 <= timescale <= 20.0:
        raise ValueError("timescale_days outside bounds")
    if not math.isfinite(amplitude) or not 0.0 <= amplitude <= 1.0:
        raise ValueError("amplitude outside bounds")
    return {"abstain": False, "model": model, "timescale": timescale,
            "amplitude": amplitude, "confidence": confidence, "evidence": evidence}


def _score(world, claim):
    unsupported = world["kind"] == "ambiguous"
    row = {"model_correct": False, "parameter_score": 0.0, "amplitude_score": 0.0,
           "mechanism_score": 0.0, "false_discovery": False, "correct_refusal": False}
    if unsupported:
        row["correct_refusal"] = bool(claim["abstain"])
        row["false_discovery"] = not claim["abstain"]
        row["mechanism_score"] = 1.0 if claim["abstain"] else 0.0
        return row
    if claim["abstain"]:
        return row
    true_model = {"point": "point_lens", "binary": "binary_lens", "variable": "variable_source"}[world["kind"]]
    row["model_correct"] = claim["model"] == true_model
    row["false_discovery"] = not row["model_correct"]
    if not row["model_correct"]:
        return row
    true_scale = world["period"] if world["kind"] == "variable" else world["timescale"]
    true_amp = world.get("anomaly_amp", 0.0) if world["kind"] == "binary" else world.get("variability_amp", 0.0)
    row["parameter_score"] = max(0.0, 1.0 - abs(claim["timescale"] - true_scale) / 5.0)
    row["amplitude_score"] = max(0.0, 1.0 - abs(claim["amplitude"] - true_amp) / 0.18)
    row["mechanism_score"] = 0.50 + 0.25 * row["parameter_score"] + 0.15 * row["amplitude_score"] + 0.10 * claim["confidence"]
    return row


DEVELOPMENT_WORLDS = tuple(_world(spec) for spec in (
    {"kind": "point", "seed": 4101, "t0": -1.0, "timescale": 7.0, "u0": 0.22, "source_scale": 0.95, "noise": 0.018},
    {"kind": "point", "seed": 4102, "t0": 2.0, "timescale": 11.0, "u0": 0.35, "source_scale": 0.80, "noise": 0.020},
    {"kind": "binary", "seed": 4103, "t0": -2.0, "timescale": 8.0, "u0": 0.27, "source_scale": 0.90, "anomaly_time": 6.0, "anomaly_width": 1.3, "anomaly_amp": 0.26, "noise": 0.018},
    {"kind": "binary", "seed": 4104, "t0": 3.0, "timescale": 10.0, "u0": 0.31, "source_scale": 0.85, "anomaly_time": -5.0, "anomaly_width": 1.0, "anomaly_amp": 0.22, "noise": 0.020},
    {"kind": "variable", "seed": 4105, "period": 15.0, "phase": -4.0, "variability_amp": 0.18, "noise": 0.022},
    {"kind": "variable", "seed": 4106, "period": 21.0, "phase": 3.0, "variability_amp": 0.14, "noise": 0.020},
    {"kind": "ambiguous", "seed": 4107, "t0": 0.0, "timescale": 8.0, "u0": 0.72, "source_scale": 0.25, "noise": 0.075},
    {"kind": "ambiguous", "seed": 4108, "t0": 1.0, "timescale": 10.0, "u0": 0.65, "source_scale": 0.22, "noise": 0.070},
))

HELDOUT_WORLDS = tuple(_world(spec) for spec in (
    {"kind": "point", "seed": 4201, "t0": -3.0, "timescale": 5.5, "u0": 0.25, "source_scale": 0.88, "noise": 0.021},
    {"kind": "point", "seed": 4202, "t0": 4.0, "timescale": 13.0, "u0": 0.32, "source_scale": 0.78, "noise": 0.022},
    {"kind": "binary", "seed": 4203, "t0": 0.0, "timescale": 9.0, "u0": 0.29, "source_scale": 0.86, "anomaly_time": 7.0, "anomaly_width": 1.1, "anomaly_amp": 0.24, "noise": 0.021},
    {"kind": "binary", "seed": 4204, "t0": 2.0, "timescale": 12.0, "u0": 0.34, "source_scale": 0.82, "anomaly_time": -6.0, "anomaly_width": 1.4, "anomaly_amp": 0.20, "noise": 0.022},
    {"kind": "variable", "seed": 4205, "period": 17.0, "phase": -2.0, "variability_amp": 0.16, "noise": 0.023},
    {"kind": "variable", "seed": 4206, "period": 19.0, "phase": 5.0, "variability_amp": 0.13, "noise": 0.022},
    {"kind": "ambiguous", "seed": 4207, "t0": -1.0, "timescale": 9.0, "u0": 0.70, "source_scale": 0.24, "noise": 0.075},
    {"kind": "ambiguous", "seed": 4208, "t0": 2.0, "timescale": 11.0, "u0": 0.68, "source_scale": 0.23, "noise": 0.072},
))


def _evaluate_one(candidate, world):
    observer = _Observer(world)
    try:
        submission = candidate(PUBLIC_PROBLEM | {"candidate_times": list(TIMES)}, observer)
        claim = _validate(submission, {"q%02d" % i for i in range(1, observer.calls + 1)})
        if observer.violated:
            raise ValueError("observer contract violated")
        return _score(world, claim), True, observer.used
    except Exception:
        return {"mechanism_score": 0.0, "false_discovery": True, "correct_refusal": False}, False, observer.used


def evaluate(candidate):
    records = []
    for split, worlds in (("development", DEVELOPMENT_WORLDS), ("heldout", HELDOUT_WORLDS)):
        for world in worlds:
            row, valid, budget = _evaluate_one(candidate, world)
            row.update({"split": split, "valid": valid, "budget_used": budget})
            records.append(row)
    unsupported = sum(world["kind"] == "ambiguous" for world in DEVELOPMENT_WORLDS) / len(DEVELOPMENT_WORLDS)
    dev = [r for r in records if r["split"] == "development"]
    raw = float(np.mean([r["mechanism_score"] for r in dev]))
    combined = max(0.0, (raw - unsupported) / (1.0 - unsupported))
    def mean(key, split):
        rows = [r for r in records if r["split"] == split]
        return float(np.mean([r.get(key, 0.0) for r in rows]))
    def conditional(key, split, supported):
        worlds = DEVELOPMENT_WORLDS if split == "development" else HELDOUT_WORLDS
        pairs = [(row, world) for row, world in zip(
            [r for r in records if r["split"] == split], worlds)
            if (world["kind"] != "ambiguous") == supported]
        return float(np.mean([row.get(key, 0.0) for row, _ in pairs]))
    dev_supported = sum(w["kind"] != "ambiguous" for w in DEVELOPMENT_WORLDS)
    dev_unsupported = len(DEVELOPMENT_WORLDS) - dev_supported
    held_supported = sum(w["kind"] != "ambiguous" for w in HELDOUT_WORLDS)
    held_unsupported = len(HELDOUT_WORLDS) - held_supported
    return {
        "combined_score": combined, "valid": 1.0 if all(r["valid"] for r in records) else 0.0,
        "feasibility_rate": float(np.mean([r["valid"] for r in records])),
        "development_mechanism_score": mean("mechanism_score", "development"),
        "heldout_mechanism_score": mean("mechanism_score", "heldout"),
        "development_model_accuracy": conditional("model_correct", "development", True),
        "heldout_model_accuracy": conditional("model_correct", "heldout", True),
        "development_false_discovery_rate": mean("false_discovery", "development"),
        "development_false_discovery_denominator": len(DEVELOPMENT_WORLDS),
        "heldout_false_discovery_rate": mean("false_discovery", "heldout"),
        "heldout_false_discovery_denominator": len(HELDOUT_WORLDS),
        "development_correct_refusal_rate": conditional("correct_refusal", "development", False),
        "development_correct_refusal_denominator": dev_unsupported,
        "heldout_correct_refusal_rate": conditional("correct_refusal", "heldout", False),
        "heldout_correct_refusal_denominator": held_unsupported,
        "development_discovery_coverage": float(np.mean([
            r["mechanism_score"] > 0.0 for r, w in zip(dev, DEVELOPMENT_WORLDS)
            if w["kind"] != "ambiguous"])),
        "development_discovery_coverage_denominator": dev_supported,
        "heldout_discovery_coverage": float(np.mean([
            r["mechanism_score"] > 0.0 for r, w in zip(
                [x for x in records if x["split"] == "heldout"], HELDOUT_WORLDS)
            if w["kind"] != "ambiguous"])),
        "heldout_discovery_coverage_denominator": held_supported,
        "development_attempted_discovery": float(any(
            r["mechanism_score"] > 0.0 for r, w in zip(dev, DEVELOPMENT_WORLDS)
            if w["kind"] != "ambiguous")),
        "development_mean_budget_used": mean("budget_used", "development"),
        "heldout_mean_budget_used": mean("budget_used", "heldout"),
        "per_instance": records,
    }
