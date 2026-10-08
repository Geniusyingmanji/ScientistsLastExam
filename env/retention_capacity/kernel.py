"""Operator-only synthetic alternatives with a common infinitesimal-load limit."""
import numpy as np
from scipy.integrate import solve_ivp


def derivative(family, p, flow, x):
    v,on,off,capacity=p
    mobile,bound,recovered=x
    capture=on*mobile
    release=v*flow*mobile
    if family=='storage_capacity':capture*=1-bound/capacity
    elif family=='outlet_capacity':release/=1+mobile/capacity
    else:raise ValueError('unknown operator family')
    exchange=capture-off*bound
    return np.array([-release-exchange,exchange,release])


def predict(family,p,spec):
    x=np.array([spec['load'],0.,0.]);now=0.;rate=spec['flow'][0]['rate'];events={r['at']:r['rate'] for r in spec['flow']};rows={};work=0
    for end in sorted(set(spec['times']+list(events))):
        if end>spec['times'][-1]:break
        if end>now:
            def rhs(t,state):
                nonlocal work
                work+=1
                if work>30000:raise RuntimeError('numeric work limit')
                return derivative(family,p,rate,state)
            sol=solve_ivp(rhs,(now,end),x,rtol=1e-8,atol=1e-10,max_step=.1)
            if not sol.success:raise RuntimeError('integration failed')
            x=sol.y[:,-1];now=end
            if not np.isfinite(x).all() or min(x)<-1e-7 or abs(sum(x)-spec['load'])>1e-7:raise RuntimeError('mass invariant failed')
        rows[end]=[float(x[2]/spec['load'])]
        if end in events:rate=events[end]
    return np.array([rows[t] for t in spec['times']])
