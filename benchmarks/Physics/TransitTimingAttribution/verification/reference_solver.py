"""Truth-blind model-selection reference for active transit timing attribution."""
from __future__ import annotations
import math
import numpy as np

def _fit(x, y, columns, sigma):
    a=np.asarray([[f(t) for f in columns] for t in x],dtype=float)
    coef,_,_,_=np.linalg.lstsq(a,np.asarray(y,dtype=float),rcond=None)
    residual=np.asarray(y,dtype=float)-a@coef
    chi_squared=float((residual/sigma)@(residual/sigma))
    bic=chi_squared+len(columns)*math.log(len(y))
    return bic,coef,columns

def _predict(model,t):
    _,coef,cols=model
    return float(sum(c*f(t) for c,f in zip(coef,cols)))

def _models(observation, x, y):
    one=lambda t:1.0; lin=lambda t:t; quad=lambda t:t*t
    sigma=float(observation["timing_uncertainties_days"][0])
    models=[("clock",1.0,_fit(x,y,[one,lin,quad],sigma))]
    planet_periods=sorted({float(p)*float(scale) for p in observation["planet_period_grid"]
                           for scale in np.linspace(0.80,1.20,17)})
    for p in planet_periods:
        w=2*math.pi/float(p)
        models.append(("planet",float(p),_fit(
            x,y,[one,lambda t,w=w:math.sin(w*t),lambda t,w=w:math.cos(w*t)],sigma)))
    sec=2*math.pi/float(observation["activity_secondary_period"])
    activity_periods=sorted({float(p)*float(scale) for p in observation["activity_period_grid"]
                             for scale in np.linspace(0.80,1.20,17)})
    for p in activity_periods:
        w=2*math.pi/float(p)
        models.append(("activity",float(p),_fit(
            x,y,[one,lambda t,w=w:math.sin(w*t),lambda t,w=w:math.cos(w*t),
                 lambda t,w=sec:math.sin(w*t),lambda t,w=sec:math.cos(w*t)],sigma)))
    return sorted(models,key=lambda z:z[2][0])

def _misspecification_models(observation,x,y):
    one=lambda t:1.0
    sigma=float(observation["timing_uncertainties_days"][0])
    center=float(sum(x)/len(x)); span=max(1.0,float(max(x)-min(x)))
    u=lambda t:(t-center)/span
    penalty=math.log(len(y))
    periods=sorted({float(p)*float(scale)
                    for key in ("planet_period_grid","activity_period_grid")
                    for p in observation[key] for scale in (0.8,0.9,1.0,1.1,1.2)})
    models=[]
    for period in periods:
        w=2*math.pi/period
        for drift in (-12*math.pi,-8*math.pi,-4*math.pi,-2*math.pi,-math.pi,
                      math.pi,2*math.pi,4*math.pi,8*math.pi,12*math.pi):
            phase=lambda t,w=w,drift=drift:w*t+drift*u(t)*u(t)
            fit=_fit(x,y,[one,lambda t,phase=phase:math.sin(phase(t)),
                          lambda t,phase=phase:math.cos(phase(t))],sigma)
            models.append(("phase_evolution",period,(fit[0]+penalty,fit[1],fit[2])))
    secondary=sorted({float(p) for p in np.linspace(1.3,3.1,10)} |
                     {float(observation["activity_secondary_period"])})
    for p1 in periods:
        w1=2*math.pi/p1
        for p2 in secondary:
            if abs(math.log(p1/p2))<0.08:
                continue
            w2=2*math.pi/p2
            fit=_fit(x,y,[one,lambda t,w=w1:math.sin(w*t),lambda t,w=w1:math.cos(w*t),
                          lambda t,w=w2:math.sin(w*t),lambda t,w=w2:math.cos(w*t)],sigma)
            models.append(("extra_component",p1,(fit[0]+2*penalty,fit[1],fit[2])))
    return sorted(models,key=lambda z:z[2][0])

def _next_transit(models, used, start, limit, model_limit=12, bic_temperature=0.08,
                  family_floor=0.08, family_temperature=0.25, spacing_weight=0.03,
                  forecast_number=None, noise=1.0, forecast_weight=0.0,
                  between_family_weight=1.0):
    # Preserve alternatives from every supported family. A global top-k can contain only
    # near-duplicate periods from one family and therefore is not an active attribution design.
    kinds=tuple(kind for kind in ("planet","activity","clock")
                if any(model[0]==kind for model in models))
    per_family=max(1,model_limit//len(kinds))
    representatives=[]
    weights=[]
    family_best={kind:min(model[2][0] for model in models if model[0]==kind)
                 for kind in kinds}
    global_best=min(family_best.values())
    family_weights={kind:max(family_floor,math.exp(-family_temperature*(score-global_best)))
                    for kind,score in family_best.items()}
    for kind in kinds:
        family=sorted((model for model in models if model[0]==kind),key=lambda m:m[2][0])[:per_family]
        local=[math.exp(-bic_temperature*(model[2][0]-family[0][2][0])) for model in family]
        total=sum(local)
        for model,weight in zip(family,local):
            representatives.append(model)
            weights.append(family_weights[kind]*weight/total)
    pool=[n for n in range(start,limit+1) if n not in used]
    if not pool: return limit
    def utility(n):
        predictions=[_predict(m[2],float(n)) for m in representatives]
        total=sum(weights)
        mean=sum(w*v for w,v in zip(weights,predictions))/total
        disagreement=sum(w*(v-mean)**2 for w,v in zip(weights,predictions))/total
        family_means=[]
        for kind in kinds:
            rows=[(weight,value) for model,weight,value in zip(
                representatives,weights,predictions) if model[0]==kind]
            family_total=sum(weight for weight,_ in rows)
            if family_total:
                family_means.append((family_total,
                                     sum(weight*value for weight,value in rows)/family_total))
        between=sum(weight*(value-mean)**2 for weight,value in family_means)/total
        within=max(0.0,disagreement-between)
        reduction=0.0
        if forecast_number is not None and forecast_weight:
            forecasts=[_predict(m[2],float(forecast_number)) for m in representatives]
            forecast_mean=sum(w*v for w,v in zip(weights,forecasts))/total
            covariance=sum(w*(value-mean)*(future-forecast_mean)
                           for w,value,future in zip(weights,predictions,forecasts))/total
            reduction=covariance*covariance/(disagreement+noise*noise)
        spacing=min(abs(n-u) for u in used) if used else 1
        design_variance=within+between_family_weight*between
        return (design_variance+forecast_weight*reduction)*(1.0+spacing_weight*spacing)
    return max(pool,key=utility)

def _refined_models(observation,x,y):
    coarse=_models(observation,x,y)
    refined=[next(model for model in coarse if model[0]=="clock")]
    one=lambda t:1.0
    sigma=float(observation["timing_uncertainties_days"][0])
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
            return _fit(x,y,columns,sigma)
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

def _attribute_ttv(observation, measure, budget_units, rms_limit, gap_limit, correlation_limit,
                   alternative_gap_limit=0.0, anchors=(20,38,55),
                   model_limit=12, bic_temperature=0.01, family_floor=0.08,
                   family_temperature=0.25, spacing_weight=0.03, forecast_weight=0.0,
                   between_family_weight=1.0):
    initial=list(map(int,observation["transit_numbers"])); limit=int(observation["maximum_followup_transit_number"])
    start=max(initial)+1
    ids=[]; nums=[]; vals=[]; used=set(initial)
    x=list(map(float,observation["transit_numbers"])); y=list(map(float,observation["timing_offsets_days"]))
    for step in range(int(budget_units)):
        p=(anchors[step] if step<len(anchors) and anchors[step]>=start
           else _next_transit(_models(observation,x,y),used,start,limit,
                              model_limit,bic_temperature,family_floor,
                              family_temperature,spacing_weight,
                              observation["forecast_transit_number"],
                              observation["timing_uncertainties_days"][0],forecast_weight,
                              between_family_weight))
        r=measure(int(p)); ids.append(r["query_id"]); nums.append(float(p)); vals.append(float(r["timing_offset_days"]))
        x.append(float(p)); y.append(float(r["timing_offset_days"])); used.add(int(p))
    if len(ids)<2: return {"abstain":True}
    best,gap,relative_rms,correlation=_diagnostics(observation,x,y,refine=True)
    alternatives=_misspecification_models(observation,x,y)
    alternative_gap=(alternatives[0][2][0]-best[2][0]) if alternatives else -math.inf
    primary=(relative_rms<=rms_limit and gap>=gap_limit and
             correlation<=correlation_limit and alternative_gap>=alternative_gap_limit)
    moderate=(relative_rms<=1.1 and gap>=2.0 and correlation<=0.2 and
              alternative_gap>=2.0)
    if not (primary or moderate):
        return {"abstain":True}
    forecast=float(observation["forecast_transit_number"])
    return {"mechanism":best[0],"period":best[1],"next_offset_days":_predict(best[2],forecast),"confidence":min(0.95,0.5+gap/20.0),"evidence_query_ids":ids,"abstain":False}

def attribute_ttv(observation, measure, budget_units):
    return _attribute_ttv(observation,measure,budget_units,1.30,0.0,0.50,
                          alternative_gap_limit=6.0,anchors=(),model_limit=24,
                          bic_temperature=0.08,family_floor=0.0,
                          family_temperature=0.25,between_family_weight=4.0)
