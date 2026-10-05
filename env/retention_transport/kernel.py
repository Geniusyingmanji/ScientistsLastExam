"""Operator-only linear mass-transport toy systems."""
import numpy as np
from scipy.linalg import expm


def matrix(family,p,flow):
    if family=='exchange':
        v,on,off=p
        return np.array([[-v*flow-on,off,0],[on,-off,0],[v*flow,0,0.]])
    if family=='parallel':
        fast,slow,fraction=p
        return np.array([[-fast*flow,0,0],[0,-slow*flow,0],[fast*flow,slow*flow,0.]])
    raise ValueError('unknown operator family')


def initial(family,p):
    return np.array([1.,0.,0.]) if family=='exchange' else np.array([p[2],1-p[2],0.])


def predict(family,p,spec):
    state=initial(family,p);last=0.;flow=spec['flow'][0]['rate'];events={r['at']:r['rate'] for r in spec['flow']};rows={}
    for t in sorted(set(spec['times']+list(events))):
        if t>spec['times'][-1]: break
        state=expm(matrix(family,p,flow)*(t-last))@state
        if t in events: flow=events[t]
        rows[t]=[float(state[2])];last=t
    return np.array([rows[t] for t in spec['times']])
