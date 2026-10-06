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


def crossed_sample(mu,lineage_effect,batch_effect,p,c,n,pairs,seed,
                   shared_founder=True,shared_batch=True):
    """Two independently controlled grouping factors; operator development only."""
    import numbers
    for x in (mu,lineage_effect,batch_effect,p,c):
        if isinstance(x,bool) or not isinstance(x,numbers.Real) or not np.isfinite(x):
            raise ValueError('parameters must be finite real numbers')
    if not 0<=p<=1 or not 0<=c<=1:raise ValueError('state probabilities out of range')
    corners=[mu+lineage_effect*(h-p)+batch_effect*(b-c) for h in (0,1) for b in (0,1)]
    if min(corners)<0 or max(corners)>1:raise ValueError('survival probabilities out of range')
    if type(n) is not int or not 1<=n<=256:raise ValueError('n must be integer 1..256')
    if type(pairs) is not int or not 1<=pairs<=20000:raise ValueError('pairs must be integer 1..20000')
    if type(shared_founder) is not bool or type(shared_batch) is not bool:raise ValueError('grouping flags must be boolean')
    rng=np.random.default_rng(seed)
    h=rng.binomial(1,p,size=(pairs,1 if shared_founder else 2))
    b=rng.binomial(1,c,size=(pairs,1 if shared_batch else 2))
    q=mu+lineage_effect*(h-p)+batch_effect*(b-c)
    return rng.binomial(n,np.broadcast_to(q,(pairs,2)))/float(n)
