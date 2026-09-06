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

def attribute_ttv(observation, measure, budget_units):
    initial=list(map(int,observation["transit_numbers"])); limit=int(observation["maximum_followup_transit_number"])
    start=max(initial)+1; span=max(1,limit-start)
    picks=sorted(set(min(limit,start+round(span*q)) for q in (0.05,0.18,0.36,0.58,0.76,0.90,0.97,1.0)))
    ids=[]; nums=[]; vals=[]
    for p in picks[:int(budget_units)]:
        r=measure(int(p)); ids.append(r["query_id"]); nums.append(float(p)); vals.append(float(r["timing_offset_days"]))
    if len(ids)<2: return {"abstain":True}
    x=list(map(float,observation["transit_numbers"]))+nums; y=list(map(float,observation["timing_offsets_days"]))+vals
    one=lambda t:1.0; lin=lambda t:t; quad=lambda t:t*t
    models=[("clock",1.0,_fit(x,y,[one,lin,quad]))]
    for p in observation["planet_period_grid"]:
        w=2*math.pi/float(p); models.append(("planet",float(p),_fit(x,y,[one,lambda t,w=w:math.sin(w*t),lambda t,w=w:math.cos(w*t)])))
    sec=2*math.pi/float(observation["activity_secondary_period"])
    for p in observation["activity_period_grid"]:
        w=2*math.pi/float(p); models.append(("activity",float(p),_fit(x,y,[one,lambda t,w=w:math.sin(w*t),lambda t,w=w:math.cos(w*t),lambda t,w=sec:math.sin(w*t),lambda t,w=sec:math.cos(w*t)])))
    models.sort(key=lambda z:z[2][0]); best,second=models[0],models[1]; gap=second[2][0]-best[2][0]
    noise=float(sum(observation["timing_uncertainties_days"])/len(observation["timing_uncertainties_days"]))
    pred=[_predict(best[2], t) for t in x]
    rms=math.sqrt(sum((u-v)**2 for u,v in zip(y,pred))/len(y))
    if rms > 1.8*noise: return {"abstain":True}
    if gap < 5.0: return {"abstain":True}
    forecast=float(observation["forecast_transit_number"])
    return {"mechanism":best[0],"period":best[1],"next_offset_days":_predict(best[2],forecast),"confidence":min(0.95,0.5+gap/20.0),"evidence_query_ids":ids,"abstain":False}
