"""Operator-only synthetic horizontal-layer reflection travel times."""
import math
from scipy.optimize import brentq


def travel_times(depths, velocities, offsets):
    if not isinstance(depths,list) or not isinstance(velocities,list) or not 1 <= len(depths) == len(velocities) <= 8:
        raise ValueError('require 1..8 paired layers')
    if not isinstance(offsets,list) or not 1 <= len(offsets) <= 64:
        raise ValueError('require 1..64 offsets')
    for v in depths+velocities+offsets:
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):
            raise ValueError('finite real controls required')
    if any(not .01 <= v <= 10 for v in depths+velocities) or any(abs(x)>10 for x in offsets):
        raise ValueError('controls outside bounded development domain')
    values=[];iterations=[]
    def distance(p):
        return 2*sum(h*p*v/math.sqrt(1-(p*v)**2) for h,v in zip(depths,velocities))
    for x in offsets:
        if x==0:
            p=0.;n=0
        else:
            p,result=brentq(lambda p:distance(p)-abs(x),0.,(1-1e-12)/max(velocities),xtol=1e-12,maxiter=100,full_output=True)
            if not result.converged:raise RuntimeError('root solver did not converge')
            n=result.iterations
        values.append(2*sum(h/(v*math.sqrt(1-(p*v)**2)) for h,v in zip(depths,velocities)))
        iterations.append(n)
    return {'times':values,'root_iterations':iterations}
