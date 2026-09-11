"""Deterministic reduced-order transient-waveform oracle."""
from __future__ import annotations
import hashlib, math
import numpy as np

TIMES = tuple(float(i) for i in range(19))
DETECTORS = ("H1", "L1")
BUDGET = 24
MIN_EVIDENCE = 6

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
    "frequency_slope_bounds": [0.0, 0.05], "event_time_bounds": [0.0, 18.0],
    "amplitude_bounds": [0.0, 1.0],
    "signal_model": "coherent sinusoid with phase 2*pi*(f0*t + 0.5*slope*t^2)",
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
    slope, et, amp = float(s.get("frequency_slope", float("nan"))), float(s.get("event_time", float("nan"))), float(s.get("amplitude", float("nan")))
    if not math.isfinite(slope) or not 0 <= slope <= .05 or not math.isfinite(et) or not 0 <= et <= 18 or not math.isfinite(amp) or not 0 <= amp <= 1: raise ValueError("bad parameter")
    return {"abstain": False, "model": s["model"], "slope": slope, "event_time": et, "amplitude": amp, "confidence": conf}

def _score(w, c):
    row = {"model_correct": False, "mechanism_score": 0.0, "false_discovery": False, "correct_refusal": False}
    if w["kind"] == "ambiguous":
        row["correct_refusal"] = bool(c["abstain"]); row["false_discovery"] = not c["abstain"]; row["mechanism_score"] = float(c["abstain"]); return row
    if c["abstain"]: return row
    truth = {"chirp": "chirp", "line": "line", "glitch": "glitch"}[w["kind"]]
    row["model_correct"] = c["model"] == truth; row["false_discovery"] = not row["model_correct"]
    if not row["model_correct"]: return row
    slope = w.get("slope", 0.0); et = w.get("event_time", 9.0); amp = w["amplitude"]
    ps = max(0.0, 1 - abs(c["slope"] - slope) / .012) if truth == "chirp" else 1.0
    pt = max(0.0, 1 - abs(c["event_time"] - et) / 3.0) if truth == "glitch" else 1.0
    pa = max(0.0, 1 - abs(c["amplitude"] - amp) / .25)
    row["mechanism_score"] = .55 + .10 * ps + .10 * pt + .15 * pa + .10 * c["confidence"]
    return row

DEVELOPMENT_WORLDS = ({"kind":"chirp","seed":5101,"f0":.055,"slope":.018,"phase":.2,"amplitude":.72,"coherence":.92,"noise":.035}, {"kind":"chirp","seed":5102,"f0":.075,"slope":.028,"phase":1.1,"amplitude":.64,"coherence":.88,"noise":.038}, {"kind":"line","seed":5103,"f0":.12,"slope":0.0,"phase":.4,"amplitude":.68,"coherence":.94,"noise":.035}, {"kind":"line","seed":5104,"f0":.16,"slope":0.0,"phase":2.0,"amplitude":.58,"coherence":.90,"noise":.04}, {"kind":"glitch","seed":5105,"event_time":8.0,"width":.85,"amplitude":.78,"noise":.035}, {"kind":"glitch","seed":5106,"event_time":12.0,"width":1.0,"amplitude":.66,"noise":.04}, {"kind":"ambiguous","seed":5107,"f0":.09,"phase":.7,"amplitude":.13,"noise":.12}, {"kind":"ambiguous","seed":5108,"f0":.14,"phase":1.8,"amplitude":.11,"noise":.13})
HELDOUT_WORLDS = ({"kind":"chirp","seed":5201,"f0":.06,"slope":.014,"phase":.8,"amplitude":.69,"coherence":.90,"noise":.04}, {"kind":"chirp","seed":5202,"f0":.085,"slope":.032,"phase":1.5,"amplitude":.61,"coherence":.86,"noise":.042}, {"kind":"line","seed":5203,"f0":.105,"slope":0.0,"phase":.1,"amplitude":.62,"coherence":.92,"noise":.04}, {"kind":"line","seed":5204,"f0":.145,"slope":0.0,"phase":2.4,"amplitude":.55,"coherence":.88,"noise":.042}, {"kind":"glitch","seed":5205,"event_time":7.0,"width":.9,"amplitude":.73,"noise":.04}, {"kind":"glitch","seed":5206,"event_time":14.0,"width":1.05,"amplitude":.60,"noise":.042}, {"kind":"ambiguous","seed":5207,"f0":.1,"phase":.3,"amplitude":.12,"noise":.13}, {"kind":"ambiguous","seed":5208,"f0":.13,"phase":2.1,"amplitude":.10,"noise":.135})

def _evaluate_one(candidate, w):
    o = _Observer(w)
    try:
        s = candidate(PUBLIC_PROBLEM, o); c = _validate(s, {f"q{i:02d}" for i in range(1, o.calls + 1)})
        if o.violated: raise ValueError("observer violation")
        return _score(w, c), True, o.used
    except Exception:
        return {"mechanism_score": 0.0, "false_discovery": True, "correct_refusal": False}, False, o.used

def evaluate(candidate):
    records = []
    for split, worlds in (("development", DEVELOPMENT_WORLDS), ("heldout", HELDOUT_WORLDS)):
        for w in worlds:
            row, valid, budget = _evaluate_one(candidate, w); row.update(split=split, valid=valid, budget_used=budget); records.append(row)
    unsupported = 2 / 8; dev = [r for r in records if r["split"] == "development"]; raw = float(np.mean([r["mechanism_score"] for r in dev])); combined = max(0.0, (raw - unsupported) / (1 - unsupported))
    def mean(k, split): return float(np.mean([r.get(k, 0.0) for r in records if r["split"] == split]))
    def cond(k, split, supported):
        worlds = DEVELOPMENT_WORLDS if split == "development" else HELDOUT_WORLDS; rows = [r for r in records if r["split"] == split]
        return float(np.mean([r.get(k, 0.0) for r, w in zip(rows, worlds) if (w["kind"] != "ambiguous") == supported]))
    return {"combined_score": combined, "valid": 1.0 if all(r["valid"] for r in records) else 0.0, "feasibility_rate": mean("valid", "development"), "development_mechanism_score": mean("mechanism_score", "development"), "heldout_mechanism_score": mean("mechanism_score", "heldout"), "development_model_accuracy": cond("model_correct", "development", True), "heldout_model_accuracy": cond("model_correct", "heldout", True), "development_false_discovery_rate": mean("false_discovery", "development"), "heldout_false_discovery_rate": mean("false_discovery", "heldout"), "development_correct_refusal_rate": cond("correct_refusal", "development", False), "heldout_correct_refusal_rate": cond("correct_refusal", "heldout", False), "development_discovery_coverage": float(np.mean([r["mechanism_score"] > 0 for r,w in zip([x for x in records if x["split"] == "development"], DEVELOPMENT_WORLDS) if w["kind"] != "ambiguous"])), "heldout_discovery_coverage": float(np.mean([r["mechanism_score"] > 0 for r,w in zip([x for x in records if x["split"] == "heldout"], HELDOUT_WORLDS) if w["kind"] != "ambiguous"])), "development_attempted_discovery": 1.0, "development_mean_budget_used": mean("budget_used", "development"), "heldout_mean_budget_used": mean("budget_used", "heldout"), "per_instance": records}
