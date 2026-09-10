"""Truth-blind model-selection reference for active transit timing attribution."""
from __future__ import annotations
import math
import numpy as np

def _fit(x, y, columns):
    a=np.asarray([[f(t) for f in columns] for t in x],dtype=float)
    coef,_,_,_=np.linalg.lstsq(a,np.asarray(y,dtype=float),rcond=None)
    residual=np.asarray(y,dtype=float)-a@coef
    rss=float(residual@residual)+1e-15
    bic=len(y)*math.log(rss/len(y))+len(columns)*math.log(len(y))
    return bic,coef,columns

def _predict(model,t):
    _,coef,cols=model
    return float(sum(c*f(t) for c,f in zip(coef,cols)))

def _models(observation, x, y):
    one=lambda t:1.0; lin=lambda t:t; quad=lambda t:t*t
    models=[("clock",1.0,_fit(x,y,[one,lin,quad]))]
    planet_periods=sorted({float(p)*float(scale) for p in observation["planet_period_grid"]
                           for scale in np.linspace(0.90,1.10,11)})
    for p in planet_periods:
        w=2*math.pi/float(p)
        models.append(("planet",float(p),_fit(
            x,y,[one,lambda t,w=w:math.sin(w*t),lambda t,w=w:math.cos(w*t)])))
    sec=2*math.pi/float(observation["activity_secondary_period"])
    activity_periods=sorted({float(p)*float(scale) for p in observation["activity_period_grid"]
                             for scale in np.linspace(0.90,1.10,11)})
    for p in activity_periods:
        w=2*math.pi/float(p)
        models.append(("activity",float(p),_fit(
            x,y,[one,lambda t,w=w:math.sin(w*t),lambda t,w=w:math.cos(w*t),
                 lambda t,w=sec:math.sin(w*t),lambda t,w=sec:math.cos(w*t)])))
    return sorted(models,key=lambda z:z[2][0])

def _next_transit(models, used, start, limit):
    # Active model discrimination: retain period uncertainty within each mechanism instead of
    # collapsing every family to one fit. This makes late follow-up choices informative for both
    # attribution and continuous-period recovery.
    representatives=models[:18]
    pool=[n for n in range(start,limit+1) if n not in used]
    if not pool: return limit
    def utility(n):
        predictions=[_predict(m[2],float(n)) for m in representatives]
        weights=[math.exp(-0.05*(m[2][0]-models[0][2][0])) for m in representatives]
        total=sum(weights)
        mean=sum(w*v for w,v in zip(weights,predictions))/total
        disagreement=sum(w*(v-mean)**2 for w,v in zip(weights,predictions))/total
        spacing=min(abs(n-u) for u in used) if used else 1
        return disagreement*(1.0+0.02*spacing)
    return max(pool,key=utility)

def _refined_models(observation,x,y):
    coarse=_models(observation,x,y)
    refined=[next(model for model in coarse if model[0]=="clock")]
    one=lambda t:1.0
    sec=2*math.pi/float(observation["activity_secondary_period"])
    for kind in ("planet","activity"):
        if not any(model[0]==kind for model in coarse):
            continue
        seed=next(model for model in coarse if model[0]==kind)
        def build(period):
            w=2*math.pi/float(period)
            columns=[one,lambda t,w=w:math.sin(w*t),lambda t,w=w:math.cos(w*t)]
            if kind=="activity":
                columns += [lambda t,w=sec:math.sin(w*t),lambda t,w=sec:math.cos(w*t)]
            return _fit(x,y,columns)
        low,high=seed[1]*0.94,seed[1]*1.06
        best_period=seed[1]
        for _ in range(4):
            grid=np.linspace(low,high,17)
            scored=[(build(float(period))[0],float(period)) for period in grid]
            _,best_period=min(scored)
            step=(high-low)/16.0
            low,high=best_period-step,best_period+step
        refined.append((kind,best_period,build(best_period)))
    return sorted(refined,key=lambda z:z[2][0])

def _diagnostics(observation,x,y,refine=False):
    models=_refined_models(observation,x,y) if refine else _models(observation,x,y)
    best=models[0]
    competitor=next(model for model in models[1:] if model[0] != best[0])
    gap=competitor[2][0]-best[2][0]
    noise=float(sum(observation["timing_uncertainties_days"])/len(observation["timing_uncertainties_days"]))
    pred=[_predict(best[2], t) for t in x]
    rms=math.sqrt(sum((u-v)**2 for u,v in zip(y,pred))/len(y))
    residual=[u-v for u,v in zip(y,pred)]
    lag=sum(a*b for a,b in zip(residual[:-1],residual[1:]))
    energy=sum(a*a for a in residual)+1e-15
    return best,gap,rms/noise,abs(lag/energy)

def _attribute_ttv(observation, measure, budget_units, rms_limit, gap_limit, correlation_limit):
    initial=list(map(int,observation["transit_numbers"])); limit=int(observation["maximum_followup_transit_number"])
    start=max(initial)+1
    ids=[]; nums=[]; vals=[]; used=set(initial)
    x=list(map(float,observation["transit_numbers"])); y=list(map(float,observation["timing_offsets_days"]))
    anchors=(20,38,55)
    for step in range(int(budget_units)):
        p=(anchors[step] if step<len(anchors) and anchors[step]>=start
           else _next_transit(_models(observation,x,y),used,start,limit))
        r=measure(int(p)); ids.append(r["query_id"]); nums.append(float(p)); vals.append(float(r["timing_offset_days"]))
        x.append(float(p)); y.append(float(r["timing_offset_days"])); used.add(int(p))
    if len(ids)<2: return {"abstain":True}
    best,gap,relative_rms,correlation=_diagnostics(observation,x,y,refine=True)
    if relative_rms > rms_limit: return {"abstain":True}
    if gap < gap_limit: return {"abstain":True}
    if correlation > correlation_limit: return {"abstain":True}
    forecast=float(observation["forecast_transit_number"])
    return {"mechanism":best[0],"period":best[1],"next_offset_days":_predict(best[2],forecast),"confidence":min(0.95,0.5+gap/20.0),"evidence_query_ids":ids,"abstain":False}

def attribute_ttv(observation, measure, budget_units):
    return _attribute_ttv(observation,measure,budget_units,1.00,6.0,0.80)
