"""Deterministic reduced-order microlensing observation and scoring oracle."""
from __future__ import annotations

import hashlib
import math

import numpy as np

TIMES = tuple(round(-24.0 + 2.0 * i, 3) for i in range(25))
FILTERS = ("g", "r")
BUDGET = 24
MIN_EVIDENCE = 6
MAX_EVIDENCE = 128


def _paczynski(t, t0, timescale, u0):
    u = math.sqrt(u0 * u0 + ((t - t0) / timescale) ** 2)
    return (u * u + 2.0) / (u * math.sqrt(u * u + 4.0))


def _point_duration(timescale, u0):
    """Full width at half maximum of the point-lens excess flux."""
    peak = _paczynski(0.0, 0.0, 1.0, u0)
    target = 1.0 + 0.5 * (peak - 1.0)
    lower, upper = u0, 10.0
    for _ in range(60):
        middle = 0.5 * (lower + upper)
        value = (middle * middle + 2.0) / (middle * math.sqrt(middle * middle + 4.0))
        if value > target:
            lower = middle
        else:
            upper = middle
    half_width = timescale * math.sqrt((0.5 * (lower + upper)) ** 2 - u0 * u0)
    return 2.0 * half_width


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
        elif kind == "ambiguous":
            value += world["variability_amp"] * band_scale * math.sin(
                2.0 * math.pi * (t - world["phase"]) / world["period"])
    else:
        value = base + world["variability_amp"] * band_scale * math.sin(
            2.0 * math.pi * (t - world["phase"]) / world["period"])
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
            # This is the instrument reporting floor, not an oracle leak of the
            # evaluator-only realization noise used to generate this world.
            "uncertainty": 0.03,
            "budget_used": self.used,
        }


PUBLIC_PROBLEM = {
    "candidate_times": list(TIMES),
    "filters": ["g", "r"],
    "filter_costs": {"g": 1, "r": 1},
    "observation_budget_units": BUDGET,
    "minimum_evidence_queries": MIN_EVIDENCE,
    "model_labels": ["point_lens", "binary_lens", "variable_source"],
    "timescale_bounds_days": [2.0, 24.0],
    "timescale_definition": "point/binary: full width at half maximum of the underlying point-lens excess flux; variable: period",
    "feature_time_bounds_days": [-24.0, 24.0],
    "amplitude_bounds": [0.0, 1.0],
    "r_band_baseline_flux": 1.0,
    "source_fraction_bounds": [0.08, 1.0],
    "impact_parameter_bounds": [0.15, 1.05],
    "anomaly_width_bounds_days": [0.55, 3.25],
    "magnification_model": "Paczynski point-lens magnification with a possible positive Gaussian binary-lens anomaly",
    "variability_model": "smooth sinusoidal source variability with a band-independent period",
    "abstain_when": "the observations do not distinguish a supported single-family model from a mixed out-of-family event",
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
    if (not isinstance(evidence, list) or len(evidence) < MIN_EVIDENCE
            or len(evidence) > MAX_EVIDENCE):
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
    feature_time = float(submission.get("feature_time_days", float("nan")))
    if not math.isfinite(timescale) or not 2.0 <= timescale <= 24.0:
        raise ValueError("timescale_days outside bounds")
    if not math.isfinite(amplitude) or not 0.0 <= amplitude <= 1.0:
        raise ValueError("amplitude outside bounds")
    if not math.isfinite(feature_time) or not -24.0 <= feature_time <= 24.0:
        raise ValueError("feature_time_days outside bounds")
    return {"abstain": False, "model": model, "timescale": timescale,
            "amplitude": amplitude, "feature_time": feature_time,
            "confidence": confidence, "evidence": evidence}


def _score(world, claim):
    unsupported = world["kind"] == "ambiguous"
    row = {"model_correct": False, "parameter_score": 0.0, "amplitude_score": 0.0,
           "feature_time_score": 0.0,
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
    true_scale = (world["period"] if world["kind"] == "variable" else
                  _point_duration(world["timescale"], world["u0"]))
    true_amp = world.get("anomaly_amp", 0.0) if world["kind"] == "binary" else world.get("variability_amp", 0.0)
    row["parameter_score"] = max(0.0, 1.0 - abs(claim["timescale"] - true_scale) / 1.8)
    row["amplitude_score"] = max(0.0, 1.0 - abs(claim["amplitude"] - true_amp) / 0.075)
    if world["kind"] == "point":
        true_feature_time = world["t0"]
        feature_error = abs(claim["feature_time"] - true_feature_time)
    elif world["kind"] == "binary":
        true_feature_time = world["anomaly_time"]
        feature_error = abs(claim["feature_time"] - true_feature_time)
    else:
        true_feature_time = world["phase"] + 0.25 * world["period"]
        feature_error = abs((claim["feature_time"] - true_feature_time
                             + 0.5 * world["period"]) % world["period"]
                            - 0.5 * world["period"])
    row["feature_time_score"] = max(0.0, 1.0 - feature_error / 1.5)
    continuous_correctness = (0.40 + 0.20 * row["parameter_score"]
                              + 0.15 * row["amplitude_score"]
                              + 0.15 * row["feature_time_score"])
    calibration = max(0.0, 1.0 - abs(claim["confidence"] - continuous_correctness))
    row["mechanism_score"] = continuous_correctness + 0.10 * calibration
    return row


DEVELOPMENT_WORLDS = tuple(_world(spec) for spec in (
    {"kind": "point", "seed": 5101, "t0": -3.37, "timescale": 6.73, "u0": 0.32, "source_scale": 0.30, "noise": 0.030},
    {"kind": "point", "seed": 5102, "t0": 2.47, "timescale": 11.38, "u0": 0.50, "source_scale": 0.65, "noise": 0.032},
    {"kind": "point", "seed": 5103, "t0": 0.83, "timescale": 15.27, "u0": 0.21, "source_scale": 0.22, "noise": 0.029},
    {"kind": "binary", "seed": 5111, "t0": -2.36, "timescale": 8.42, "u0": 0.42, "source_scale": 0.38, "anomaly_time": 5.63, "anomaly_width": 0.82, "anomaly_amp": 0.31, "noise": 0.030},
    {"kind": "binary", "seed": 5112, "t0": 3.18, "timescale": 10.74, "u0": 0.58, "source_scale": 0.72, "anomaly_time": -4.67, "anomaly_width": 1.47, "anomaly_amp": 0.19, "noise": 0.032},
    {"kind": "binary", "seed": 5113, "t0": -0.71, "timescale": 14.16, "u0": 0.27, "source_scale": 0.24, "anomaly_time": 8.34, "anomaly_width": 2.18, "anomaly_amp": 0.14, "noise": 0.029},
    {"kind": "variable", "seed": 5121, "period": 9.73, "phase": -1.91, "variability_amp": 0.34, "noise": 0.031},
    {"kind": "variable", "seed": 5122, "period": 14.37, "phase": -3.71, "variability_amp": 0.47, "noise": 0.030},
    {"kind": "variable", "seed": 5123, "period": 20.63, "phase": 3.27, "variability_amp": 0.58, "noise": 0.033},
    {"kind": "ambiguous", "seed": 5131, "t0": 0.43, "timescale": 8.17, "u0": 0.62, "source_scale": 0.31, "period": 12.41, "phase": -2.2, "variability_amp": 0.24, "noise": 0.032},
    {"kind": "ambiguous", "seed": 5132, "t0": 1.29, "timescale": 10.41, "u0": 0.73, "source_scale": 0.42, "period": 17.63, "phase": 2.7, "variability_amp": 0.31, "noise": 0.031},
    {"kind": "ambiguous", "seed": 5133, "t0": -2.18, "timescale": 15.22, "u0": 0.48, "source_scale": 0.20, "period": 22.17, "phase": -4.1, "variability_amp": 0.39, "noise": 0.034},
))

HELDOUT_WORLDS = tuple(_world(spec) for spec in (
    {"kind": "point", "seed": 5201, "t0": -4.24, "timescale": 5.61, "u0": 0.39, "source_scale": 0.43, "noise": 0.031},
    {"kind": "point", "seed": 5202, "t0": 4.16, "timescale": 12.71, "u0": 0.61, "source_scale": 0.78, "noise": 0.033},
    {"kind": "point", "seed": 5203, "t0": -0.42, "timescale": 17.31, "u0": 0.24, "source_scale": 0.19, "noise": 0.030},
    {"kind": "binary", "seed": 5211, "t0": 0.31, "timescale": 9.27, "u0": 0.47, "source_scale": 0.44, "anomaly_time": 6.74, "anomaly_width": 1.03, "anomaly_amp": 0.27, "noise": 0.031},
    {"kind": "binary", "seed": 5212, "t0": 2.42, "timescale": 12.16, "u0": 0.66, "source_scale": 0.83, "anomaly_time": -5.82, "anomaly_width": 1.71, "anomaly_amp": 0.17, "noise": 0.033},
    {"kind": "binary", "seed": 5213, "t0": -1.73, "timescale": 16.08, "u0": 0.31, "source_scale": 0.27, "anomaly_time": 9.18, "anomaly_width": 2.36, "anomaly_amp": 0.12, "noise": 0.030},
    {"kind": "variable", "seed": 5221, "period": 10.42, "phase": 1.38, "variability_amp": 0.37, "noise": 0.032},
    {"kind": "variable", "seed": 5222, "period": 16.42, "phase": -2.38, "variability_amp": 0.51, "noise": 0.031},
    {"kind": "variable", "seed": 5223, "period": 22.14, "phase": 4.63, "variability_amp": 0.55, "noise": 0.034},
    {"kind": "ambiguous", "seed": 5231, "t0": -1.18, "timescale": 9.23, "u0": 0.67, "source_scale": 0.36, "period": 13.57, "phase": 1.4, "variability_amp": 0.27, "noise": 0.033},
    {"kind": "ambiguous", "seed": 5232, "t0": 2.31, "timescale": 10.84, "u0": 0.78, "source_scale": 0.48, "period": 18.29, "phase": -3.0, "variability_amp": 0.34, "noise": 0.032},
    {"kind": "ambiguous", "seed": 5233, "t0": -3.07, "timescale": 14.33, "u0": 0.53, "source_scale": 0.24, "period": 21.36, "phase": 3.8, "variability_amp": 0.41, "noise": 0.035},
))


def _evaluate_one(candidate, world):
    observer = _Observer(world)
    try:
        if hasattr(candidate, "reset_session"):
            candidate.reset_session()
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
    all_valid = all(r["valid"] for r in records)
    if not all_valid:
        combined = 0.0
    return {
        "combined_score": combined, "valid": 1.0 if all_valid else 0.0,
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
