"""Deterministic reduced-order transient-waveform oracle."""
from __future__ import annotations
import copy
import hashlib, math, random
import numpy as np

TIMES = tuple(float(i) for i in range(19))
DETECTORS = ("H1", "L1")
BUDGET = 24
MIN_EVIDENCE = 6
NOISE_SIGMA = 0.04
SLOPE_TOLERANCE = 0.003
FREQUENCY_TOLERANCE = 0.008

def _noise(seed, t, d, sigma):
    h = hashlib.sha256(f"{seed}|{t:.3f}|{d}".encode()).digest()
    s = int.from_bytes(h[:8], "little") & 0xffffffff
    return float(np.random.default_rng(s).normal(0.0, sigma))

def _strain(w, t, d):
    t = float(t)
    sigma = w["noise"]
    if w["kind"] in {"chirp", "line"}:
        phase = 2 * math.pi * (w["f0"] * t + 0.5 * w["slope"] * t * t) + w["phase"]
        value = w["amplitude"] * math.sin(phase)
        if d == "L1":
            value *= w["coherence"]
    elif w["kind"] == "glitch":
        value = w["amplitude"] * math.exp(-0.5 * ((t - w["event_time"]) / w["width"]) ** 2)
        if d == "L1":
            value *= 0.08
    else:
        value = w["amplitude"] * math.sin(2 * math.pi * w["f0"] * t + w["phase"])
        if d == "L1":
            value *= 0.7
    return value + _noise(w["seed"], t, d, sigma)

class _Observer:
    def __init__(self, world):
        self.world, self.used, self.calls, self.seen, self.violated = world, 0, 0, set(), False
    def __call__(self, time, detector):
        try: time = float(time)
        except (TypeError, ValueError) as exc:
            self.violated = True; raise ValueError("time must be numeric") from exc
        if not any(abs(time - x) < 1e-9 for x in TIMES): self.violated = True; raise ValueError("unknown epoch")
        if detector not in DETECTORS: self.violated = True; raise ValueError("unknown detector")
        key = (round(time, 3), detector)
        if key in self.seen: self.violated = True; raise ValueError("duplicate observation")
        if self.used + 1 > BUDGET: self.violated = True; raise RuntimeError("budget exceeded")
        self.seen.add(key); self.used += 1; self.calls += 1
        return {"query_id": f"q{self.calls:02d}", "time": key[0], "detector": detector,
                "strain": _strain(self.world, key[0], detector), "uncertainty": self.world["noise"],
                "budget_used": self.used}

PUBLIC_PROBLEM = {
    "candidate_times": list(TIMES), "detectors": ["H1", "L1"],
    "detector_costs": {"H1": 1, "L1": 1}, "observation_budget_units": BUDGET,
    "minimum_evidence_queries": MIN_EVIDENCE, "model_labels": ["chirp", "line", "glitch"],
    "initial_frequency_bounds": [0.04, 0.18], "frequency_slope_bounds": [0.0, 0.05], "event_time_bounds": [0.0, 18.0],
    "amplitude_bounds": [0.0, 1.0],
    "signal_model": "coherent sinusoid with phase 2*pi*(f0*t + 0.5*slope*t^2) + phase0; f0 in [0.04, 0.18] cycles/day; line slope is zero",
    "glitch_model": "localized Gaussian transient confined primarily to one detector",
    "abstain_when": "signal-to-noise is too low to distinguish the supported families",
    "evidence_requirement": "cite at least six distinct query_id values from current-world observations",
}

def _validate(s, ids):
    if not isinstance(s, dict): raise ValueError("mapping required")
    abstain = s.get("abstain", False)
    if not isinstance(abstain, bool): raise ValueError("abstain must be boolean")
    conf = float(s.get("confidence", 0.0))
    if not math.isfinite(conf) or not 0 <= conf <= 1: raise ValueError("bad confidence")
    ev = s.get("evidence_query_ids", [])
    if not isinstance(ev, list) or len(ev) < MIN_EVIDENCE or len(ev) != len(set(ev)) or not set(ev) <= ids: raise ValueError("bad evidence")
    if abstain: return {"abstain": True, "confidence": conf}
    if s.get("model") not in set(PUBLIC_PROBLEM["model_labels"]): raise ValueError("bad model")
    frequency, slope, et, amp = (float(s.get("initial_frequency", float("nan"))),
        float(s.get("frequency_slope", float("nan"))), float(s.get("event_time", float("nan"))),
        float(s.get("amplitude", float("nan"))))
    if (not math.isfinite(frequency) or not .04 <= frequency <= .18 or not math.isfinite(slope)
            or not 0 <= slope <= .05 or not math.isfinite(et) or not 0 <= et <= 18
            or not math.isfinite(amp) or not 0 <= amp <= 1): raise ValueError("bad parameter")
    return {"abstain": False, "model": s["model"], "frequency": frequency, "slope": slope,
            "event_time": et, "amplitude": amp, "confidence": conf}

def _score(w, c):
    row = {"model_correct": False, "science_score": 0.0, "parameter_score": 0.0,
           "amplitude_score": 0.0, "confidence_score": 1.0 - c["confidence"],
           "false_discovery": False, "correct_refusal": False,
           "claimed": not c["abstain"], "supported": w["kind"] != "ambiguous"}
    if w["kind"] == "ambiguous":
        row["correct_refusal"] = bool(c["abstain"])
        row["false_discovery"] = not c["abstain"]
        row["science_score"] = float(c["abstain"])
        row["confidence_score"] = c["confidence"] if c["abstain"] else 1.0 - c["confidence"]
        return row
    if c["abstain"]: return row
    truth = {"chirp": "chirp", "line": "line", "glitch": "glitch"}[w["kind"]]
    row["model_correct"] = c["model"] == truth; row["false_discovery"] = not row["model_correct"]
    if not row["model_correct"]: return row
    slope = w.get("slope", 0.0); et = w.get("event_time", 9.0); amp = w["amplitude"]
    if truth in {"chirp", "line"}:
        slope_quality = max(0.0, 1 - abs(c["slope"] - slope) / SLOPE_TOLERANCE)
        frequency_quality = max(0.0, 1 - abs(c["frequency"] - w["f0"]) / FREQUENCY_TOLERANCE)
        parameter = 0.5 * (slope_quality + frequency_quality)
    else:
        parameter = max(0.0, 1 - abs(c["event_time"] - et) / 1.0)
    pa = max(0.0, 1 - abs(c["amplitude"] - amp) / .25)
    row["parameter_score"] = parameter
    row["amplitude_score"] = pa
    row["confidence_score"] = c["confidence"]
    row["science_score"] = .30 + .50 * parameter + .20 * pa
    return row

DEVELOPMENT_WORLDS = ({"kind":"chirp","seed":5101,"f0":.0567,"slope":.01731,"phase":.2,"amplitude":.72,"coherence":.92,"noise":.035}, {"kind":"chirp","seed":5102,"f0":.0734,"slope":.02743,"phase":1.1,"amplitude":.64,"coherence":.88,"noise":.038}, {"kind":"line","seed":5103,"f0":.1217,"slope":0.0,"phase":.4,"amplitude":.68,"coherence":.94,"noise":.035}, {"kind":"line","seed":5104,"f0":.1583,"slope":0.0,"phase":2.0,"amplitude":.58,"coherence":.90,"noise":.04}, {"kind":"glitch","seed":5105,"event_time":8.35,"width":.85,"amplitude":.78,"noise":.035}, {"kind":"glitch","seed":5106,"event_time":11.65,"width":1.0,"amplitude":.66,"noise":.04}, {"kind":"ambiguous","seed":5107,"f0":.0913,"phase":.7,"amplitude":.13,"noise":.12}, {"kind":"ambiguous","seed":5108,"f0":.1376,"phase":1.8,"amplitude":.11,"noise":.13})
HELDOUT_WORLDS = ({"kind":"chirp","seed":5201,"f0":.0619,"slope":.01367,"phase":.8,"amplitude":.69,"coherence":.90,"noise":.04}, {"kind":"chirp","seed":5202,"f0":.0862,"slope":.03121,"phase":1.5,"amplitude":.61,"coherence":.86,"noise":.042}, {"kind":"line","seed":5203,"f0":.1064,"slope":0.0,"phase":.1,"amplitude":.62,"coherence":.92,"noise":.04}, {"kind":"line","seed":5204,"f0":.1468,"slope":0.0,"phase":2.4,"amplitude":.55,"coherence":.88,"noise":.042}, {"kind":"glitch","seed":5205,"event_time":7.4,"width":.9,"amplitude":.73,"noise":.04}, {"kind":"glitch","seed":5206,"event_time":13.55,"width":1.05,"amplitude":.60,"noise":.042}, {"kind":"ambiguous","seed":5207,"f0":.1011,"phase":.3,"amplitude":.12,"noise":.13}, {"kind":"ambiguous","seed":5208,"f0":.1287,"phase":2.1,"amplitude":.10,"noise":.135})

def _harden_worlds(worlds, seed, extra_chirps):
    result = [dict(w, noise=NOISE_SIGMA) for w in worlds]
    for w in result:
        if w["kind"] == "ambiguous":
            w["amplitude"] = 0.04
    # Paired lines match a slow chirp's midpoint frequency and phase.
    for index, (frequency, slope, phase) in enumerate(extra_chirps):
        midpoint = 5.5
        common = {"amplitude": 0.64, "coherence": 0.90, "noise": NOISE_SIGMA}
        result.append(dict(common, kind="chirp", seed=seed + 10 * index,
                           f0=frequency, slope=slope, phase=phase))
        result.append(dict(common, kind="line", seed=seed + 10 * index + 1,
                           f0=frequency + slope * midpoint, slope=0.0,
                           phase=phase - math.pi * slope * midpoint * midpoint))
    for index, frequency in enumerate((0.065, 0.165)):
        result.append({"kind": "ambiguous", "seed": seed + 100 + index,
                       "f0": frequency, "phase": 0.9 + index, "amplitude": 0.04,
                       "noise": NOISE_SIGMA})
    random.Random(seed + 104729).shuffle(result)
    return tuple(result)


DEVELOPMENT_WORLDS = _harden_worlds(DEVELOPMENT_WORLDS, 53100,
                                  ((0.0917, 0.00341, 0.4), (0.1136, 0.00637, 1.2)))
HELDOUT_WORLDS = _harden_worlds(HELDOUT_WORLDS, 54100,
                              ((0.0843, 0.00357, 0.7), (0.1061, 0.00523, 1.6), (0.0818, 0.00719, 0.2)))


def _evaluate_one(candidate, w):
    o = _Observer(w)
    try:
        if hasattr(candidate, "reset_session"):
            candidate.reset_session()
        s = candidate(copy.deepcopy(PUBLIC_PROBLEM), o); c = _validate(s, {f"q{i:02d}" for i in range(1, o.calls + 1)})
        if o.violated: raise ValueError("observer violation")
        return _score(w, c), True, o.used
    except Exception:
        return {"science_score": 0.0, "model_correct": False, "parameter_score": 0.0,
                "amplitude_score": 0.0, "confidence_score": 0.0, "false_discovery": False,
                "correct_refusal": False, "claimed": False, "supported": w["kind"] != "ambiguous"}, False, o.used

def _aggregate(rows):
    supported = [r for r in rows if r["supported"]]
    unsupported = len(rows) - len(supported)
    claims = sum(r["claimed"] for r in rows)
    correct = sum(r["model_correct"] for r in supported)
    false = sum(r["false_discovery"] for r in rows)
    refused = sum(r["correct_refusal"] for r in rows)
    covered = sum(r["claimed"] for r in supported)
    refusal = refused / unsupported if unsupported else 0.0
    score = max(0.0, (sum(r["science_score"] for r in rows) - unsupported) / len(supported)) if supported else 0.0
    score *= refusal if unsupported else 1.0
    def mean(key, population):
        return sum(r[key] for r in population) / len(population) if population else 0.0
    return {
        "combined_score": score,
        "science_score": mean("science_score", rows),
        "mechanism_score": correct / len(supported) if supported else 0.0,
        "mechanism_correct_count": correct, "mechanism_denominator": len(supported),
        "model_accuracy": correct / len(supported) if supported else 0.0,
        "model_accuracy_denominator": len(supported),
        "false_discovery_rate": false / claims if claims else 0.0,
        "false_discovery_count": false, "false_discovery_denominator": claims,
        "correct_refusal_rate": refusal, "correct_refusal_count": refused,
        "correct_refusal_denominator": unsupported,
        "discovery_coverage": covered / len(supported) if supported else 0.0,
        "discovery_count": covered, "discovery_coverage_denominator": len(supported),
        "attempted_discovery": float(claims > 0), "claim_count": claims,
        "parameter_recovery_score": mean("parameter_score", supported),
        "amplitude_recovery_score": mean("amplitude_score", supported),
        "confidence_score": mean("confidence_score", rows),
        "mean_budget_used": mean("budget_used", rows),
    }


def evaluate(candidate):
    records = []
    metrics = {}
    for split, worlds in (("development", DEVELOPMENT_WORLDS), ("heldout", HELDOUT_WORLDS)):
        rows = []
        for w in worlds:
            row, valid, budget = _evaluate_one(candidate, w)
            row.update(split=split, valid=valid, budget_used=budget)
            rows.append(row)
        records.extend(rows)
        metrics.update({split + "_" + k: v for k, v in _aggregate(rows).items()})
    valid = all(r["valid"] for r in records)
    metrics.update(combined_score=metrics["development_combined_score"] if valid else 0.0,
                   robustness_score=metrics["heldout_combined_score"] if valid else 0.0,
                   valid=float(valid), feasibility_rate=sum(r["valid"] for r in records) / len(records),
                   per_instance=records)
    return metrics
