"""Deterministic reduced-order transient-waveform oracle."""
from __future__ import annotations
import copy
import hashlib, math
import numpy as np

TIMES = tuple(float(i) for i in range(19))
DETECTORS = ("H1", "L1")
BUDGET = 24
MIN_EVIDENCE = 6
NOISE_SIGMA = 0.065
SLOPE_TOLERANCE = 0.004
FREQUENCY_TOLERANCE = 0.010
EVENT_TIME_TOLERANCE = 1.2

def _noise(seed, t, d, sigma):
    h = hashlib.sha256(f"{seed}|{t:.3f}|{d}".encode()).digest()
    s = int.from_bytes(h[:8], "little") & 0xffffffff
    return float(np.random.default_rng(s).normal(0.0, sigma))

def _strain(w, t, d):
    t = float(t)
    sigma = w["noise"]
    if w["kind"] in {"chirp", "line", "glitch"}:
        phase = 2 * math.pi * (w["f0"] * t + 0.5 * w["slope"] * t * t) + w["phase"]
        envelope = math.exp(-0.5 * ((t - w["event_time"]) / w["width"]) ** 2)
        value = w["amplitude"] * envelope * math.sin(phase)
        if d == "L1":
            value *= w["coherence"] if w["kind"] != "glitch" else w["leakage"]
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
    "signal_model": "Gaussian-windowed coherent sinusoid with phase 2*pi*(f0*t + 0.5*slope*t^2) + phase0; f0 in [0.04, 0.18] cycles/day; line slope is zero",
    "glitch_model": "the same Gaussian-windowed chirplet morphology in H1 but localized primarily to one detector; paired coherent/localized worlds require L1 evidence",
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
        parameter = max(0.0, 1 - abs(c["event_time"] - et) / EVENT_TIME_TOLERANCE)
    pa = max(0.0, 1 - abs(c["amplitude"] - amp) / .30)
    row["parameter_score"] = parameter
    row["amplitude_score"] = pa
    row["confidence_score"] = c["confidence"]
    row["science_score"] = .45 + .35 * parameter + .20 * pa
    return row

def _coherent(kind, seed, f0, slope, phase, amplitude, event_time, width, coherence):
    return {"kind": kind, "seed": seed, "f0": f0, "slope": slope, "phase": phase,
            "amplitude": amplitude, "event_time": event_time, "width": width,
            "coherence": coherence, "noise": NOISE_SIGMA}


def _glitch(seed, event_time, width, f0, slope, phase, amplitude):
    return {"kind": "glitch", "seed": seed, "event_time": event_time, "width": width,
            "f0": f0, "slope": slope, "phase": phase, "amplitude": amplitude,
            "leakage": 0.05, "noise": NOISE_SIGMA}


def _ambiguous(seed, f0, phase):
    return {"kind": "ambiguous", "seed": seed, "f0": f0, "phase": phase,
            "amplitude": 0.055, "noise": NOISE_SIGMA}


DEVELOPMENT_WORLDS = (
    _coherent("chirp", 7101, .0567, .01731, .2, .45, 5.4, 3.8, .92),
    _glitch(7101, 5.4, 3.8, .0567, .01731, .2, .45),
    _coherent("chirp", 7102, .0917, .00471, 1.1, .42, 9.4, 4.2, .88),
    _glitch(7102, 9.4, 4.2, .0917, .00471, 1.1, .42),
    _coherent("line", 7103, .1217, 0.0, .4, .44, 12.6, 3.6, .94),
    _glitch(7103, 12.6, 3.6, .1217, 0.0, .4, .44),
    _coherent("line", 7104, .1583, 0.0, 2.0, .40, 7.2, 4.4, .90),
    _glitch(7104, 7.2, 4.4, .1583, 0.0, 2.0, .40),
    _coherent("chirp", 7105, .0734, .02743, 1.7, .43, 13.8, 4.0, .86),
    _glitch(7105, 13.8, 4.0, .0734, .02743, 1.7, .43),
    _ambiguous(6131, .065, .9), _ambiguous(6132, .101, 1.7),
    _ambiguous(6133, .137, 2.4), _ambiguous(6134, .165, .2),
)

HELDOUT_WORLDS = (
    _coherent("chirp", 7201, .0619, .01367, .8, .44, 4.8, 4.1, .90),
    _glitch(7201, 4.8, 4.1, .0619, .01367, .8, .44),
    _coherent("chirp", 7202, .0862, .03121, 1.5, .41, 8.6, 3.7, .86),
    _glitch(7202, 8.6, 3.7, .0862, .03121, 1.5, .41),
    _coherent("chirp", 7203, .1043, .00657, .7, .46, 13.2, 4.3, .93),
    _glitch(7203, 13.2, 4.3, .1043, .00657, .7, .46),
    _coherent("line", 7204, .1468, 0.0, 2.4, .42, 6.4, 3.9, .88),
    _glitch(7204, 6.4, 3.9, .1468, 0.0, 2.4, .42),
    _coherent("line", 7205, .0759, 0.0, 1.7, .43, 10.8, 4.5, .90),
    _glitch(7205, 10.8, 4.5, .0759, 0.0, 1.7, .43),
    _coherent("line", 7206, .1691, 0.0, .6, .39, 14.1, 3.5, .86),
    _glitch(7206, 14.1, 3.5, .1691, 0.0, .6, .39),
    _ambiguous(6231, .058, .4), _ambiguous(6232, .098, 1.2),
    _ambiguous(6233, .132, 2.0), _ambiguous(6234, .171, 2.7),
)

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
