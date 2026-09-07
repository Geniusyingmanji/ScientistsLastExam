"""Truth-blind bounded grid-search witness."""
import itertools
import numpy as np
def _value(p,rates,ind):
 def one(ms,os):
  def f(t,y):
   X,S,A,P,V=np.maximum(y,0); j=min(2,int(t//8)); F=rates[j]; mu=p["kinetics"]["mu_max"]*ms*S/(.4+S)/(1+A/3)*(1-p["kinetics"]["induction_burden"]*(t>=ind)); q=mu/.52; oxygen=.52*os*np.clip(p["kinetics"]["kla_per_h"]/180.0,.65,1.25); ov=max(0,q-oxygen)
   return [mu*X-F*X/V,F*p["feed_substrate_gpl"]/V-q*X-F*S/V,.55*ov*X-F*A/V,(.12*max(0,q-ov)*X if t>=ind else 0)-F*P/V,F]
  y=np.asarray(p["initial_state"],float); t=0.; max_a=y[2]
  while t<22-1e-12:
   h=min(.04,22-t); y=y+h*np.asarray(f(t,y)); t+=h; max_a=max(max_a,y[2])
   if not np.all(np.isfinite(y)) or np.any(y<-.1): return 0
  X,S,A,P,V=y
  return P*V/22 if V<=p["maximum_volume_l"] and max_a<=p["maximum_acetate_gpl"] and X*V>=p["minimum_final_biomass_g"] else 0
 return min(one(*s) for s in ((1,1),(.9,.85),(1.08,.8)))
def grid_reference(problem):
 choices=[(r,i) for r in itertools.product((.05,.14,.23),repeat=3) for i in (7.,12.)]
 rates,ind=max(choices,key=lambda z:_value(problem,z[0],z[1]))
 return {"feed_rates":list(rates),"induction_time_h":ind,"harvest_time_h":22.0}


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


def design_process(problem):
    from scipy.optimize import minimize
    ref = grid_reference(problem)
    x = np.r_[ref["feed_rates"], ref["induction_time_h"], ref["harvest_time_h"]]
    def design(x):
        return {"feed_rates": x[:3].tolist(), "induction_time_h": float(x[3]), "harvest_time_h": float(x[4])}
    def objective(x):
        return -_robust(problem, design(x))
    fit = minimize(objective, x, method="Nelder-Mead",
                   bounds=[(0., .32)]*3+[(4., 18.), (16., 24.)],
                   options={"maxiter": 220, "xatol": 1e-5, "fatol": 1e-6})
    return design(fit.x)
