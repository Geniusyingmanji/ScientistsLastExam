"""Deterministic active transit-timing attribution laboratory."""
from __future__ import annotations
import math, random

DIFFICULTY = 1
_PROFILES = {1: {"n": 18, "noise": 0.0018, "budget": 4, "seed": 20260951, "counts": (2, 2, 1, 3)}, 2: {"n": 14, "noise": 0.0024, "budget": 4, "seed": 20260952, "counts": (2, 2, 1, 3)}}
_SEALED = {1: {"n": 16, "noise": 0.0020, "budget": 4, "seed": 20261951, "counts": (2, 2, 2, 4)}}
MECHANISMS = ("planet", "activity", "clock", "unsupported")
PLANET_PERIOD_GRID = (3.7, 5.2, 8.4, 13.0)
ACTIVITY_PERIOD_GRID = tuple(1.35 * p for p in PLANET_PERIOD_GRID)
ACTIVITY_SECONDARY_PERIOD = 2.1
FORECAST_TRANSIT = 44
MAX_MEASURE_TRANSIT = 39

def _profile(level, sealed=False):
    d = (_SEALED if sealed else _PROFILES).get(int(level))
    if d is None: raise ValueError("unsupported difficulty")
    return d

def _make_worlds(cfg):
    rng = random.Random(cfg["seed"]); worlds=[]
    kinds = [kind for kind, count in zip(MECHANISMS, cfg["counts"]) for _ in range(count)]
    for kind in kinds:
        period = rng.choice(PLANET_PERIOD_GRID); amp = rng.uniform(0.0045, 0.009); phase = rng.uniform(0, 2*math.pi); baseline = rng.uniform(-0.001, 0.001)
        times = [float(j) for j in range(cfg["n"])] ; vals=[]
        for t in times:
            if kind == "planet": signal=amp*math.sin(2*math.pi*t/period+phase)
            elif kind == "activity": signal=amp*math.sin(2*math.pi*t/(period*1.35)+phase)+0.0030*math.sin(2*math.pi*t/ACTIVITY_SECONDARY_PERIOD+0.45)
            elif kind == "clock": signal=0.00022*t + 0.000006*t*t
            else: signal=amp*math.sin(2*math.pi*t/period+phase)+0.0045*math.sin(2*math.pi*t/1.7+0.3)
            vals.append(signal+baseline+rng.gauss(0,cfg["noise"]))
        worlds.append({"kind":kind,"times":times,"values":vals,"noise":cfg["noise"],"budget":cfg["budget"],"period":period,"amplitude":amp,"phase":phase,"query_ids":[]})
    # Independent deterministic ordering; no seed or world index is candidate-visible.
    random.Random(cfg["seed"] + 104729).shuffle(worlds)
    return worlds

def development_worlds(): return _make_worlds(_profile(DIFFICULTY))
def sealed_worlds(): return _make_worlds(_profile(DIFFICULTY, True))

def _observation(w):
    return {"transit_numbers": list(range(len(w["times"]))), "timing_offsets_days": list(w["values"]), "timing_uncertainties_days": [w["noise"]]*len(w["times"]), "budget_transits": w["budget"], "query_ids": list(w["query_ids"]), "planet_period_grid": list(PLANET_PERIOD_GRID), "activity_period_grid": list(ACTIVITY_PERIOD_GRID), "activity_secondary_period": ACTIVITY_SECONDARY_PERIOD, "clock_polynomial_degree": 2, "forecast_transit_number": FORECAST_TRANSIT, "maximum_followup_transit_number": MAX_MEASURE_TRANSIT, "note":"Choose integer transit numbers for follow-up; offsets are relative to a linear ephemeris."}

def _signal(w, t):
    if w["kind"] == "planet": return w["amplitude"]*math.sin(2*math.pi*t/w["period"]+w["phase"])
    if w["kind"] == "activity": return w["amplitude"]*math.sin(2*math.pi*t/(w["period"]*1.35)+w["phase"])+0.0030*math.sin(2*math.pi*t/ACTIVITY_SECONDARY_PERIOD+0.45)
    if w["kind"] == "clock": return 0.00022*t+0.000006*t*t
    return w["amplitude"]*math.sin(2*math.pi*t/w["period"]+w["phase"])+0.0045*math.sin(2*math.pi*t/1.7+0.3)

def _experiment(w, number):
    if type(number) is not int or number < 0 or number > MAX_MEASURE_TRANSIT:
        w["invalid_query"] = True
        raise ValueError("transit number out of range")
    if len(w["query_ids"]) >= w["budget"]:
        w["invalid_query"] = True
        raise RuntimeError("budget exceeded")
    rng=random.Random(1000003*number+len(w["query_ids"])+17); t=float(number)
    s=_signal(w, t)
    y=s+rng.gauss(0,w["noise"]); qid=f"ttv-{number}-{len(w['query_ids'])}"; w["query_ids"].append(qid)
    return {"transit_number":number,"timing_offset_days":y,"uncertainty_days":w["noise"],"query_id":qid,"remaining_budget":w["budget"]-len(w["query_ids"])}

def _parse_submission(x):
    if not isinstance(x,dict): return None
    if "abstain" in x and type(x["abstain"]) is not bool: return None
    if x.get("abstain"): return {"abstain":True}
    k=x.get("mechanism"); ids=x.get("evidence_query_ids")
    if k not in MECHANISMS[:3] or not isinstance(ids,list) or len(ids)<2 or not all(isinstance(i,str) for i in ids): return None
    if len(set(ids)) != len(ids): return None
    try: p=float(x.get("period")); pred=float(x.get("next_offset_days")); c=float(x.get("confidence",0.0))
    except Exception: return None
    if not all(math.isfinite(v) for v in (p,pred,c)) or p<=0 or not 0<=c<=1: return None
    return {"abstain":False,"mechanism":k,"period":p,"pred":pred,"ids":ids,"confidence":c}

def _score(w, s):
    if s["abstain"]: return (1.0 if w["kind"]=="unsupported" else 0.0), False
    if w["kind"]=="unsupported": return 0.0, True
    if s["mechanism"] != w["kind"]: return 0.0, True
    pscore=math.exp(-abs(s["period"]-w["period"])/(w["period"]*0.4)) if w["kind"]=="planet" else 0.5
    predscore=math.exp(-abs(s["pred"]-_signal(w, FORECAST_TRANSIT))/(w["noise"]*4))
    return 0.55+0.25*pscore+0.20*predscore, False

def _aggregate(rows):
    supported = sum(r["supported"] for r in rows)
    unsupported = len(rows) - supported
    claims = sum(not r["abstain"] for r in rows)
    correct = sum(r["correct"] for r in rows)
    false = sum(r["fd"] for r in rows)
    refused = sum(r["abstain"] and not r["supported"] for r in rows)
    covered = sum(not r["abstain"] and r["supported"] for r in rows)
    # Subtract the raw reward of blanket refusal, including every unsupported world.
    score = max(0.0, (sum(r["score"] for r in rows) - unsupported) / supported) if supported else 0.0
    # Discovery requires both supported inference and rejection of unsupported signals.
    # The additive correction alone still rewards a fitted never-refuse strategy.
    score *= refused / unsupported if unsupported else 1.0
    return {
        "combined_score": score,
        "mechanism_score": correct / supported if supported else 0.0,
        "mechanism_correct_count": correct, "mechanism_total_count": supported,
        "false_discovery_rate": false / claims if claims else 0.0,
        "false_discovery_count": false, "false_discovery_denominator": claims,
        "correct_refusal_rate": refused / unsupported if unsupported else 0.0,
        "correct_refusal_count": refused, "correct_refusal_denominator": unsupported,
        "discovery_coverage": covered / supported if supported else 0.0,
        "discovery_count": covered, "discovery_coverage_denominator": supported,
        "attempted_discovery": float(claims > 0),
    }


def _invalid_metrics():
    metrics = {"combined_score": 0.0, "robustness_score": 0.0, "valid": 0.0}
    for prefix in ("development", "validation"):
        metrics.update({prefix + "_" + key: 0.0 for key in _aggregate([])})
    return metrics


def evaluate(candidate):
    metrics = {"valid": 1.0}
    try:
        for prefix, worlds in (("development", development_worlds()), ("validation", sealed_worlds())):
            rows = []
            for w in worlds:
                if hasattr(candidate, "reset_session"):
                    candidate.reset_session()
                s = _parse_submission(candidate(_observation(w), lambda n: _experiment(w, n), w["budget"]))
                if w.get("invalid_query") or s is None or (not s["abstain"] and not set(s["ids"]).issubset(w["query_ids"])):
                    return _invalid_metrics()
                score, fd = _score(w, s)
                supported = w["kind"] != "unsupported"
                rows.append({"score": score, "fd": fd, "abstain": s["abstain"],
                             "supported": supported,
                             "correct": supported and not s["abstain"] and s["mechanism"] == w["kind"]})
            summary = _aggregate(rows)
            metrics.update({prefix + "_" + key: value for key, value in summary.items()})
            metrics["combined_score" if prefix == "development" else "robustness_score"] = summary["combined_score"]
    except Exception:
        return _invalid_metrics()
    return metrics

def reference_anchor(): return {"development_score":1.0,"validation_score":1.0}
