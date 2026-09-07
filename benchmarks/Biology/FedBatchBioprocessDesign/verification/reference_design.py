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
def design_process(problem):
 choices=[(r,i) for r in itertools.product((.05,.14,.23),repeat=3) for i in (7.,12.)]
 rates,ind=max(choices,key=lambda z:_value(problem,z[0],z[1]))
 return {"feed_rates":list(rates),"induction_time_h":ind,"harvest_time_h":22.0}
