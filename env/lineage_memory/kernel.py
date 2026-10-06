"""Synthetic common-founder dependence, with explicit binomial sampling."""
import numpy as np


def moments(p,a,b,rho,n):
    mean=a+(b-a)*p
    cov=p*(1-p)*rho*rho*(b-a)**2
    variance=mean*(1-mean)/n+(1-1/n)*cov
    return mean,variance,cov


def sample(p,a,b,rho,n,pairs,seed,related=True):
    for x in (p,a,b,rho):
        if not np.isfinite(x) or not 0<=x<=1:raise ValueError('probabilities must be finite in [0,1]')
    if isinstance(n,bool) or not isinstance(n,int) or not 1<=n<=256:raise ValueError('n must be integer 1..256')
    if isinstance(pairs,bool) or not isinstance(pairs,int) or not 1<=pairs<=20000:raise ValueError('pairs must be integer 1..20000')
    rng=np.random.default_rng(seed)
    founders=rng.binomial(1,p,size=(pairs,1 if related else 2))
    q=a+(b-a)*(rho*founders+(1-rho)*p)
    return rng.binomial(n,np.broadcast_to(q,(pairs,2)))/float(n)
