"""Operator-only exact finite-support moment calculation; known parameter priors."""
import itertools
import numpy as np
from scipy.stats import binom


def difference_moments(mu, lineage, batch, p, c, n, shared_founder, shared_batch):
    """Return E[(X-Y)^2], Var((X-Y)^2) for synthetic paired proportions."""
    if type(n) is not int or not 1 <= n <= 64:
        raise ValueError('exact enumeration requires n integer 1..64')
    if type(shared_founder) is not bool or type(shared_batch) is not bool:
        raise ValueError('grouping flags must be boolean')
    params = (mu, lineage, batch, p, c)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not np.isfinite(v) for v in params):
        raise ValueError('finite parameters required')
    if not 0 <= p <= 1 or not 0 <= c <= 1:
        raise ValueError('state probabilities out of range')
    q = {(h,b): mu + lineage*(h-p) + batch*(b-c) for h,b in itertools.product((0,1), repeat=2)}
    if min(q.values()) < 0 or max(q.values()) > 1:
        raise ValueError('survival probabilities out of range')
    def states(prob, shared):
        if shared:
            return [(0,0,1-prob),(1,1,prob)]
        return [(a,b,(prob if a else 1-prob)*(prob if b else 1-prob)) for a,b in itertools.product((0,1), repeat=2)]
    x = np.arange(n+1)/float(n)
    d = (x[:,None]-x[None,:])**2
    first = second = 0.
    pmf = {k: binom.pmf(np.arange(n+1), n, v) for k,v in q.items()}
    for h1,h2,wh in states(p,shared_founder):
        for b1,b2,wb in states(c,shared_batch):
            joint = np.outer(pmf[h1,b1],pmf[h2,b2])
            first += wh*wb*float(np.sum(joint*d))
            second += wh*wb*float(np.sum(joint*d*d))
    return {'mean_squared_difference': first, 'variance_squared_difference': max(0.,second-first*first)}
