"""Deterministic active transit-timing attribution laboratory."""
from __future__ import annotations
import math, random

DIFFICULTY = 1
_PROFILES = {1: {"n_range": (10, 15), "noise_range": (0.0018, 0.0028),
                 "budget": 5, "seed": 20260951,
                 "seeds": (20260951, 20260952, 20260953),
                 "counts": (6, 6, 5, 3, 3)}}
_SEALED = {1: {"n_range": (9, 16), "noise_range": (0.0019, 0.0030),
               "budget": 5, "seed": 20266951,
               "seeds": (20266951, 20266952, 20266953),
               "counts": (5, 5, 4, 3, 3)}}
MECHANISMS = ("planet", "activity", "clock")
WORLD_KINDS = MECHANISMS + ("unsupported_resonant", "unsupported_chirp")
PLANET_PERIOD_GRID = (3.7, 5.2, 8.4, 13.0)
ACTIVITY_PERIOD_GRID = tuple(1.35 * p for p in PLANET_PERIOD_GRID)

def _profile(level, sealed=False):
    d = (_SEALED if sealed else _PROFILES).get(int(level))
    if d is None: raise ValueError("unsupported difficulty")
    return d

def _make_worlds(cfg):
    rng = random.Random(cfg["seed"]); worlds=[]
    kinds = [kind for kind, count in zip(WORLD_KINDS, cfg["counts"]) for _ in range(count)]
    for index, kind in enumerate(kinds):
        world_seed = cfg["seed"] + 7919 * (index + 1)
        n = rng.randint(*cfg["n_range"])
        maximum_followup = rng.randint(48, 64)
        forecast_transit = maximum_followup + rng.randint(12, 24)
        noise = rng.uniform(*cfg["noise_range"])
        period = rng.choice(PLANET_PERIOD_GRID) * rng.uniform(0.82, 1.18)
        amp = rng.uniform(0.0028, 0.0090); phase = rng.uniform(0, 2*math.pi)
        baseline = rng.uniform(-0.001, 0.001)
        secondary_period = rng.uniform(1.75, 2.45)
        secondary_amplitude = rng.uniform(0.0018, 0.0046)
        secondary_phase = rng.uniform(0, 2*math.pi)
        clock_linear = rng.uniform(0.00012, 0.00034)
        clock_quadratic = rng.uniform(0.0000035, 0.0000090)
        resonant_period = rng.uniform(1.35, 3.05)
        resonant_amplitude = rng.uniform(0.0020, 0.0058)
        resonant_phase = rng.uniform(0, 2*math.pi)
        phase_drift = rng.choice((-1.0, 1.0)) * rng.uniform(0.0045, 0.0145)
        times = [float(j) for j in range(n)] ; vals=[]
        for t in times:
            if kind == "planet": signal=amp*math.sin(2*math.pi*t/period+phase)
            elif kind == "activity": signal=amp*math.sin(2*math.pi*t/(period*1.35)+phase)+secondary_amplitude*math.sin(2*math.pi*t/secondary_period+secondary_phase)
            elif kind == "clock": signal=clock_linear*t + clock_quadratic*t*t
            elif kind == "unsupported_resonant": signal=amp*math.sin(2*math.pi*t/period+phase)+resonant_amplitude*math.sin(2*math.pi*t/resonant_period+resonant_phase)
            else:
                # A drifting phase represents a non-stationary timing process outside all three
                # declared stationary/quadratic families. It is deliberately not another fixed
                # harmonic mixture, so refusal is tested for two independent reasons.
                signal=amp*math.sin(2*math.pi*t/period+phase+phase_drift*t*t)
            vals.append(signal+baseline+rng.gauss(0,noise))
        worlds.append({"kind":kind,"seed":world_seed,"panel_seed":cfg["seed"],
                       "times":times,"values":vals,
                       "noise":noise,"budget":cfg["budget"],"period":period,
                       "amplitude":amp,"phase":phase,"secondary_period":secondary_period,
                       "secondary_amplitude":secondary_amplitude,"secondary_phase":secondary_phase,
                       "clock_linear":clock_linear,"clock_quadratic":clock_quadratic,
                       "resonant_period":resonant_period,"resonant_amplitude":resonant_amplitude,
                       "resonant_phase":resonant_phase,"phase_drift":phase_drift,
                       "forecast_transit":forecast_transit,"maximum_followup":maximum_followup,
                       "query_ids":[],"query_numbers":[],"query_repeats":{}})
    # Independent deterministic ordering; no seed or world index is candidate-visible.
    random.Random(cfg["seed"] + 104729).shuffle(worlds)
    return worlds

def development_worlds():
    cfg=_profile(DIFFICULTY)
    worlds=[]
    for seed in cfg.get("seeds",(cfg["seed"],)):
        panel=dict(cfg); panel["seed"]=seed; panel.pop("seeds",None)
        worlds.extend(_make_worlds(panel))
    random.Random(cfg["seed"]+32452843).shuffle(worlds)
    return worlds
def sealed_worlds():
    cfg=_profile(DIFFICULTY,True)
    worlds=[]
    for seed in cfg.get("seeds",(cfg["seed"],)):
        panel=dict(cfg); panel["seed"]=seed; panel.pop("seeds",None)
        worlds.extend(_make_worlds(panel))
    random.Random(cfg["seed"]+49979687).shuffle(worlds)
    return worlds

def _observation(w):
    return {"transit_numbers": list(range(len(w["times"]))), "timing_offsets_days": list(w["values"]), "timing_uncertainties_days": [w["noise"]]*len(w["times"]), "budget_transits": w["budget"], "query_ids": list(w["query_ids"]), "planet_period_grid": list(PLANET_PERIOD_GRID), "activity_period_grid": list(ACTIVITY_PERIOD_GRID), "activity_secondary_period": w["secondary_period"], "clock_polynomial_degree": 2, "forecast_transit_number": w["forecast_transit"], "maximum_followup_transit_number": w["maximum_followup"], "note":"Choose integer transit numbers for follow-up; offsets are relative to a linear ephemeris."}

def _signal(w, t):
    if w["kind"] == "planet": return w["amplitude"]*math.sin(2*math.pi*t/w["period"]+w["phase"])
    if w["kind"] == "activity": return w["amplitude"]*math.sin(2*math.pi*t/(w["period"]*1.35)+w["phase"])+w["secondary_amplitude"]*math.sin(2*math.pi*t/w["secondary_period"]+w["secondary_phase"])
    if w["kind"] == "clock": return w["clock_linear"]*t+w["clock_quadratic"]*t*t
    if w["kind"] == "unsupported_resonant":
        return w["amplitude"]*math.sin(2*math.pi*t/w["period"]+w["phase"])+w["resonant_amplitude"]*math.sin(2*math.pi*t/w["resonant_period"]+w["resonant_phase"])
    return w["amplitude"]*math.sin(2*math.pi*t/w["period"]+w["phase"]+w["phase_drift"]*t*t)

def _experiment(w, number):
    if type(number) is not int or number < 0 or number > w["maximum_followup"]:
        w["invalid_query"] = True
        raise ValueError("transit number out of range")
    if len(w["query_ids"]) >= w["budget"]:
        w["invalid_query"] = True
        raise RuntimeError("budget exceeded")
    repeat = w["query_repeats"].get(number, 0)
    w["query_repeats"][number] = repeat + 1
    rng=random.Random(1000003*number + 1009*w["seed"] + 9176*repeat + 17); t=float(number)
    s=_signal(w, t)
    y=s+rng.gauss(0,w["noise"]); qid=f"ttv-{number}-{repeat}"; w["query_ids"].append(qid)
    w["query_numbers"].append(number)
    return {"transit_number":number,"timing_offset_days":y,"uncertainty_days":w["noise"],"query_id":qid,"remaining_budget":w["budget"]-len(w["query_ids"])}

def _parse_submission(x):
    if not isinstance(x,dict): return None
    if "abstain" in x and type(x["abstain"]) is not bool: return None
    if x.get("abstain"): return {"abstain":True}
    k=x.get("mechanism"); ids=x.get("evidence_query_ids")
    if k not in MECHANISMS or not isinstance(ids,list) or len(ids)<2 or not all(isinstance(i,str) for i in ids): return None
    if len(set(ids)) != len(ids): return None
    try: p=float(x.get("period")); pred=float(x.get("next_offset_days")); c=float(x.get("confidence",0.0))
    except Exception: return None
    if not all(math.isfinite(v) for v in (p,pred,c)) or p<=0 or not 0<=c<=1: return None
    return {"abstain":False,"mechanism":k,"period":p,"pred":pred,"ids":ids,"confidence":c}

def _design_score(w,s):
    if s["abstain"] or w["kind"] not in MECHANISMS:
        return 0.0
    number_by_id=dict(zip(w["query_ids"],w["query_numbers"]))
    selected={number_by_id[query_id] for query_id in s["ids"]}
    if w["kind"]=="clock":
        utility=lambda t:float(t)**4
    else:
        period=w["period"]*(1.35 if w["kind"]=="activity" else 1.0)
        utility=lambda t:(w["amplitude"]*2*math.pi*t/(period*period)*
                          math.cos(2*math.pi*t/period+w["phase"]))**2
    start=int(max(w["times"]))+1
    pool=range(start,w["maximum_followup"]+1)
    optimum=sum(sorted((utility(t) for t in pool),reverse=True)[:w["budget"]])
    return min(1.0,sum(utility(t) for t in selected)/optimum) if optimum else 0.0

def _score(w, s):
    if s["abstain"]: return (1.0 if w["kind"] not in MECHANISMS else 0.0), False
    if w["kind"] not in MECHANISMS: return 0.0, True
    if s["mechanism"] != w["kind"]: return 0.0, True
    target_period = w["period"] * (1.35 if w["kind"] == "activity" else 1.0)
    pscore=math.exp(-abs(s["period"]-target_period)/(target_period*0.25)) if w["kind"] != "clock" else 0.0
    predscore=math.exp(-abs(s["pred"]-_signal(w, w["forecast_transit"]))/(w["noise"]*4))
    designscore=_design_score(w,s)
    if w["kind"] == "clock":
        return 0.50+0.30*predscore+0.20*designscore, False
    return 0.35+0.25*pscore+0.20*predscore+0.20*designscore, False

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
    # A strict discovery score also requires precision: otherwise an aggressive candidate can
    # outscore a better-calibrated method by making more supported and unsupported claims.
    precision = 1.0 - false / claims if claims else 1.0
    score *= precision * precision * precision
    return {
        "combined_score": score,
        "design_score": sum(r.get("design",0.0) for r in rows) / supported if supported else 0.0,
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
    metrics = {"combined_score": 0.0, "development_score": 0.0,
               "robustness_score": 0.0, "valid": 0.0}
    for prefix in ("development", "validation", "heldout"):
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
                supported = w["kind"] in MECHANISMS
                rows.append({"score": score, "fd": fd, "abstain": s["abstain"],
                             "supported": supported,
                             "design": _design_score(w,s),
                             "correct": supported and not s["abstain"] and s["mechanism"] == w["kind"]})
            summary = _aggregate(rows)
            metrics.update({prefix + "_" + key: value for key, value in summary.items()})
            if prefix == "development":
                metrics["development_score"] = summary["combined_score"]
            else:
                metrics["robustness_score"] = summary["combined_score"]
            if prefix == "validation":
                metrics.update({"heldout_" + key: value for key, value in summary.items()})
        # For candidates valid on every world, only development scientific performance
        # selects proposals. All-world validity remains a public feasibility gate above.
        metrics["combined_score"] = metrics["development_score"]
    except Exception:
        return _invalid_metrics()
    return metrics
