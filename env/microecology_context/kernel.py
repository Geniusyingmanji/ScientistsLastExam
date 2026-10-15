"""Trusted-only invented carbon-balanced ecology; no organism calibration."""
import numpy as np
from scipy.integrate import solve_ivp

POOLS=('S','A','B','C','X','N','Y','Q','W')
FAMILIES=('fixed','signal','context_memory')

class Kernel:
    def __init__(self, seed, family):
        if family not in FAMILIES: raise ValueError('unknown operator family')
        self.family=family
        rng=np.random.default_rng(seed)
        self.p=dict(zip(('ua','ub','uc','ks','kx','kn','ki','kq','tau'),
                       np.array([.8,.9,.7,.3,.15,.15,.12,.08,2.])*rng.uniform(.9,1.1,9)))

    def target(self,q,temp):
        if self.family=='fixed': return .3
        k=self.p['kq']* (np.exp(-.06*(temp-30)) if self.family=='context_memory' else 1.)
        return q*q/(k*k+q*q)

    def derivative(self,t,state,temp):
        s,a,b,c,x,n,y,q,w,h=np.maximum(state,0.)
        p=self.p;theta=2**((temp-30)/10)
        h=float(np.clip(h,0,1)) if self.family=='context_memory' else self.target(q,temp)
        qa=theta*p['ua']*a*s/(p['ks']+s)
        qb=theta*p['ub']*b*x/(p['kx']+x)
        qc=theta*p['uc']*c*n/(p['kn']+n)/(1+y/p['ki'])
        death=theta*.01*np.array([a,b,c]);decay=theta*.02*np.array([x,n,y,q])
        return np.array([-qa,.35*qa-death[0],.4*qb-death[1],.5*qc-death[2],
                         .35*qa-qb-decay[0],.6*(1-h)*qb-qc-decay[1],
                         .6*h*qb-decay[2],.05*qa-decay[3],
                         .25*qa+.5*qc+sum(death)+sum(decay),
                         (self.target(q,temp)-h)/p['tau'] if self.family=='context_memory' else 0.])

    def advance(self,state,hours,temp,method='DOP853'):
        if hours==0:return np.array(state,copy=True)
        r=solve_ivp(lambda t,y:self.derivative(t,y,temp),(0,hours),state,
                    method=method,rtol=1e-9,atol=1e-11,max_step=.25)
        if not r.success or not np.isfinite(r.y).all():raise RuntimeError('integration_failed')
        z=r.y[:,-1]
        if min(z[:9]) < -1e-8 or not -1e-8<=z[9]<=1+1e-8:raise RuntimeError('nonphysical_state')
        if abs(sum(z[:9])-sum(state[:9]))>1e-7:raise RuntimeError('carbon_balance')
        return z
