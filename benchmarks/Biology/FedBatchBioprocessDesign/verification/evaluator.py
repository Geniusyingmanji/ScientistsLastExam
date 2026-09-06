"""Reduced-order robust fed-batch process-design oracle."""
from __future__ import annotations
import itertools
from numbers import Real
from functools import lru_cache
import numpy as np

SPECS=(
 {"mu_max":.43,"kla":180.,"burden":.18,"feed_concentration":220.,"max_volume":5.5,"initial_s":8.,"initial_x":1.0},
 {"mu_max":.38,"kla":150.,"burden":.22,"feed_concentration":350.,"max_volume":4.3,"initial_s":2.,"initial_x":.5},
 {"mu_max":.47,"kla":205.,"burden":.16,"feed_concentration":220.,"max_volume":4.3,"initial_s":20.,"initial_x":.5},
 {"mu_max":.35,"kla":135.,"burden":.25,"feed_concentration":350.,"max_volume":5.0,"initial_s":8.,"initial_x":1.0},
 {"mu_max":.41,"kla":165.,"burden":.20,"feed_concentration":300.,"max_volume":4.7,"initial_s":4.,"initial_x":.8},
)
DEV=range(4); HELD=range(4,5); BASELINE={"feed_rates":[.10,.10,.10],"induction_time_h":10.0,"harvest_time_h":20.0}

def _problem(spec):
 return {"horizon_h":24.0,"segment_boundaries_h":[0.0,8.0,16.0,24.0],"feed_rate_bounds_lph":[0.0,.32],
         "induction_time_bounds_h":[4.0,18.0],"harvest_time_bounds_h":[16.0,24.0],
         "initial_state":[spec["initial_x"],spec["initial_s"],0.0,0.0,2.0],
         "feed_substrate_gpl":spec["feed_concentration"],"maximum_volume_l":spec["max_volume"],"maximum_acetate_gpl":5.0,
         "minimum_final_biomass_g":4.0,"kinetics":{"mu_max":spec["mu_max"],"kla_per_h":spec["kla"],"induction_burden":spec["burden"]}}

def _parse(p,out):
 if not isinstance(out,dict) or set(out)!={"feed_rates","induction_time_h","harvest_time_h"}: return None
 if not isinstance(out["feed_rates"],list) or len(out["feed_rates"])!=3: return None
 if any(isinstance(x,bool) or not isinstance(x,Real) for x in [*out["feed_rates"],out["induction_time_h"],out["harvest_time_h"]]): return None
 try: rates=np.asarray(out["feed_rates"],float); ind=float(out["induction_time_h"]); harvest=float(out["harvest_time_h"])
 except Exception: return None
 if rates.shape != (3,) or not np.all(np.isfinite(rates)) or not np.isfinite(ind+harvest): return None
 if np.any(rates<p["feed_rate_bounds_lph"][0]) or np.any(rates>p["feed_rate_bounds_lph"][1]): return None
 if not p["induction_time_bounds_h"][0]<=ind<=p["induction_time_bounds_h"][1] or not p["harvest_time_bounds_h"][0]<=harvest<=p["harvest_time_bounds_h"][1]: return None
 return {"feed_rates":rates,"induction_time_h":ind,"harvest_time_h":harvest}

def _simulate(p,d,shift=(1.,1.)):
 mu_max=p["kinetics"]["mu_max"]*shift[0]; oxygen_scale=shift[1]; burden=p["kinetics"]["induction_burden"]
 bounds=p["segment_boundaries_h"]
 def rhs(t,y):
  X,S,A,P,V=np.maximum(y,0); rate=d["feed_rates"][min(2,np.searchsorted(bounds[1:],t,side="right"))]
  induced=t>=d["induction_time_h"]; mu=mu_max*S/(.4+S)/(1+A/3.0)*(1-burden*induced)
  uptake=mu/.52
  oxygen_cap=.52*oxygen_scale*np.clip(p["kinetics"]["kla_per_h"]/180.0,.65,1.25)
  overflow=max(0.0,uptake-oxygen_cap); productive=max(0.0,uptake-overflow)
  return [mu*X-rate*X/V, rate*p["feed_substrate_gpl"]/V-uptake*X-rate*S/V,
          .55*overflow*X-rate*A/V, (.12*productive*X if induced else 0)-rate*P/V, rate]
 dt=.04; y=np.asarray(p["initial_state"],float); max_a=y[2]; t=0.0
 while t<d["harvest_time_h"]-1e-12:
  h=min(dt,d["harvest_time_h"]-t); y=y+h*np.asarray(rhs(t,y)); t+=h; max_a=max(max_a,y[2])
  if not np.all(np.isfinite(y)) or np.any(y<-.1): return 0.0,False
 X,S,A,P,V=y; feasible=V<=p["maximum_volume_l"]+1e-6 and max_a<=p["maximum_acetate_gpl"]+1e-6 and X*V>=p["minimum_final_biomass_g"]
 utility=(P*V)/max(1e-9,d["harvest_time_h"])
 return float(utility),bool(feasible)

def _robust(p,d):
 vals=[]
 for shift in ((1,1),(.9,.85),(1.08,.8)):
  u,ok=_simulate(p,d,shift); vals.append(u if ok else 0.0)
 return min(vals)

def _reference(p):
 best=None; value=-1
 for rates in itertools.product((.05,.14,.23),repeat=3):
  for ind in (7.,12.):
   d={"feed_rates":np.asarray(rates),"induction_time_h":ind,"harvest_time_h":22.0}; u=_robust(p,d)
   if u>value: best,value=d,u
 return best,value

@lru_cache(maxsize=None)
def _reference_value(index):
 return _reference(_problem(SPECS[index]))[1]

def evaluate(design_process):
 rows=[]
 for index,spec in enumerate(SPECS):
  p=_problem(spec); base=_robust(p,{**BASELINE,"feed_rates":np.asarray(BASELINE["feed_rates"]) }); ref=_reference_value(index)
  try:
   d=_parse(p,design_process(p))
   valid=d is not None
   utility=_robust(p,d) if valid else 0.0
  except Exception:
   valid=False; utility=0.0
  score=np.clip((utility-base)/max(1e-12,ref-base),0,1)
  rows.append({"valid":valid,"utility":utility,"baseline":base,"reference":ref,"score":float(score)})
 dev=[rows[i] for i in DEV]; held=[rows[i] for i in HELD]
 return {"combined_score":float(np.mean([r["score"] for r in dev])),"valid":1.0 if all(r["valid"] for r in dev) else 0.0,
         "feasibility_rate":float(np.mean([r["valid"] for r in dev])),"heldout_robust_score":float(np.mean([r["score"] for r in held])),"per_instance":rows}
