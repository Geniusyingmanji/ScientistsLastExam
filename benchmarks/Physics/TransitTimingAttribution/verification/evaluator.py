"""Deterministic active transit-timing attribution laboratory."""
from __future__ import annotations
import math, random

DIFFICULTY = 1
_PROFILES = {1: {"n": 18, "noise": 0.0018, "budget": 8, "seed": 20260951}, 2: {"n": 14, "noise": 0.0024, "budget": 6, "seed": 20260952}}
_SEALED = {1: {"n": 16, "noise": 0.0020, "budget": 8, "seed": 20261951}}
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
    for i in range(6):
        kind = ("planet" if i % 3 == 0 else "activity" if i % 3 == 1 else "clock")
        if i == 5: kind = "unsupported"
        period = rng.choice(PLANET_PERIOD_GRID); amp = rng.uniform(0.0045, 0.009); phase = rng.uniform(0, 2*math.pi); baseline = rng.uniform(-0.001, 0.001)
        times = [float(j) for j in range(cfg["n"])] ; vals=[]
        for t in times:
            if kind == "planet": signal=amp*math.sin(2*math.pi*t/period+phase)
            elif kind == "activity": signal=amp*math.sin(2*math.pi*t/(period*1.35)+phase)+0.0030*math.sin(2*math.pi*t/ACTIVITY_SECONDARY_PERIOD+0.45)
            elif kind == "clock": signal=0.00022*t + 0.000006*t*t
            else: signal=amp*math.sin(2*math.pi*t/period+phase)+0.0045*math.sin(2*math.pi*t/1.7+0.3)
            vals.append(signal+baseline+rng.gauss(0,cfg["noise"]))
        worlds.append({"kind":kind,"times":times,"values":vals,"noise":cfg["noise"],"budget":cfg["budget"],"period":period,"amplitude":amp,"phase":phase,"query_ids":[]})
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
    if not isinstance(number, int) or number < 0 or number > MAX_MEASURE_TRANSIT: raise ValueError("transit number out of range")
    if len(w["query_ids"]) >= w["budget"]: raise RuntimeError("budget exceeded")
    rng=random.Random(1000003*number+len(w["query_ids"])+17); t=float(number)
    s=_signal(w, t)
    y=s+rng.gauss(0,w["noise"]); qid=f"ttv-{number}-{len(w['query_ids'])}"; w["query_ids"].append(qid)
    return {"transit_number":number,"timing_offset_days":y,"uncertainty_days":w["noise"],"query_id":qid,"remaining_budget":w["budget"]-len(w["query_ids"])}

def _parse_submission(x):
    if not isinstance(x,dict): return None
    if x.get("abstain"): return {"abstain":True}
    k=x.get("mechanism"); ids=x.get("evidence_query_ids")
    if k not in MECHANISMS[:3] or not isinstance(ids,list) or len(ids)<2 or not all(isinstance(i,str) for i in ids): return None
    try: p=float(x.get("period")); pred=float(x.get("next_offset_days")); c=float(x.get("confidence",0.0))
    except Exception: return None
    if not all(math.isfinite(v) for v in (p,pred,c)) or p<=0 or not 0<=c<=1: return None
    return {"abstain":False,"mechanism":k,"period":p,"pred":pred,"ids":ids,"confidence":c}

def _score(w, s):
    if s["abstain"]: return (1.0 if w["kind"]=="unsupported" else 0.0), False
    if w["kind"]=="unsupported": return 0.0, True
    mech=1.0 if s["mechanism"]==w["kind"] else 0.0
    pscore=math.exp(-abs(s["period"]-w["period"])/(w["period"]*0.4)) if w["kind"]=="planet" else 0.5
    predscore=math.exp(-abs(s["pred"]-_signal(w, FORECAST_TRANSIT))/(w["noise"]*4))
    return 0.55*mech+0.25*pscore+0.20*predscore, mech==0

def evaluate(candidate):
    rows=[]
    for wi,w in enumerate(development_worlds()+sealed_worlds()):
        s=_parse_submission(candidate(_observation(w), lambda n: _experiment(w,n), w["budget"]))
        if s is None or (not s["abstain"] and not set(s["ids"]).issubset(set(w["query_ids"]))): return {"combined_score":-1e18,"valid":0.0}
        score,fd=_score(w,s); rows.append((wi,score,fd,s["abstain"],w["kind"]))
    dev=rows[:6]; val=rows[6:]
    dev_supported=[r for r in dev if r[4] != "unsupported"]
    val_supported=[r for r in val if r[4] != "unsupported"]
    dev_claims=sum(not r[3] for r in dev); val_claims=sum(not r[3] for r in val)
    return {"combined_score":sum(r[1] for r in dev_supported)/len(dev_supported),"valid":1.0,"robustness_score":sum(r[1] for r in val_supported)/len(val_supported),"development_false_discovery_rate":sum(r[2] for r in dev)/dev_claims if dev_claims else 0.0,"validation_false_discovery_rate":sum(r[2] for r in val)/val_claims if val_claims else 0.0,"development_correct_refusal_rate":sum(r[3] and r[4] == "unsupported" for r in dev)/1,"validation_correct_refusal_rate":sum(r[3] and r[4] == "unsupported" for r in val)/1,"development_discovery_coverage":sum(not r[3] and r[4] != "unsupported" for r in dev)/len(dev_supported),"validation_discovery_coverage":sum(not r[3] and r[4] != "unsupported" for r in val)/len(val_supported)}

def reference_anchor(): return {"development_score":1.0,"validation_score":1.0}
