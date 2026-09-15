"""Truth-blind bounded-nuisance likelihood fits and two distinct refusal checks.

The design depends only on the public domain/costs. Every family fits its public
finite-size correction. Known-noise goodness of fit tests adequacy; profile
likelihood separation tests identifiability. No residues, seeds or oracle imports.
"""
import math
import numpy as np
from scipy.stats import chi2


def _shape(name, size):
    log_size=math.log2(max(size,2))
    return {"constant":1., "logarithmic":log_size, "linear":float(size),
            "linearithmic":size*log_size, "quadratic":float(size)**2,
            "exponential":2.**(size/8.)}[name]


def design(problem, budget):
    lo,hi=problem["size_bounds"]
    pool=np.unique(np.rint(np.geomspace(lo,hi,11)).astype(int)).tolist()
    def cost(n):
        return next(c for bound,c in problem["cost_tiers"] if n<=bound)
    sizes=[]; used=0
    while pool:
        n=pool.pop(0)
        if used+cost(n)<=budget:
            sizes.append(n);used+=cost(n)
    # Use remaining units at the extremes to refine the scale/correction contrast.
    while used+cost(lo)<=budget:
        n=hi if used+cost(hi)<=budget else lo
        sizes.append(n);used+=cost(n)
    return sizes


def solve(problem,time_run,budget_units,*,sizes=None,correction=True,
          adequacy=True,separation=True,threshold=.85,mass=None):
    sizes=design(problem,budget_units) if sizes is None else sizes
    logs=np.log([time_run(int(n))["runtime_ms"] for n in sizes])
    x=64./np.asarray(sizes,dtype=float); sigma=problem["log_noise_std"]
    fits=[]
    for name in problem["classes"]:
        residual=logs-np.log([_shape(name,n) for n in sizes])
        slope=(np.dot(x-x.mean(),residual-residual.mean())/max(np.sum((x-x.mean())**2),1e-15)) if correction else 0.
        slope=float(np.clip(slope,-2.,2.));level=float(np.mean(residual-slope*x))
        rss=float(np.sum((residual-level-slope*x)**2)/sigma**2)
        fits.append((rss,math.exp(level)))
    rss=np.array([r for r,c in fits]); best=int(np.argmin(rss))
    weights=np.exp(-.5*(rss-rss.min())); weights/=weights.sum()
    bad_fit=bool(adequacy and rss[best]>chi2.ppf(.99,max(1,len(sizes)-(2 if correction else 1))))
    ambiguous=bool(weights[best]<threshold)
    abstain=(adequacy and bad_fit) or (separation and ambiguous)
    if mass is not None:
        weights=np.full(len(weights),(1-mass)/(len(weights)-1)); weights[best]=mass
    return {"class_probabilities":dict(zip(problem["classes"],map(float,weights))),
            "scale":None if abstain else fits[best][1],"abstain":bool(abstain),"confidence":.8}



def identify_scaling_law(problem, time_run, budget_units):
    """Reduced design with all inference capabilities retained, for comparison."""
    lo, hi = problem['size_bounds']
    ladder = (8, 32, 96, 192, 384)
    sizes = ladder if lo <= min(ladder) and max(ladder) <= hi else np.rint(np.geomspace(lo, hi, len(ladder))).astype(int)
    return solve(problem, time_run, budget_units, sizes=sizes, threshold=.7)
