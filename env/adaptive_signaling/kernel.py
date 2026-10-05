"""Operator-only synthetic dynamics. No claim of biological realism."""
import numpy as np
from scipy.linalg import expm


def matrix(family, p, u):
    a,b,g=p
    if family=='feedforward':
        return np.array([[-a,0,a*g*u],[-b,-b,b*g*u],[0,0,0.]])
    if family=='feedback':
        return np.array([[0,a,0],[-b,-b,b*g*u],[0,0,0.]])
    raise ValueError('unknown operator family')


def predict(family, p, spec):
    state=np.array([0.,0.,1.]);last=0.;u=spec['stimulus'][0]['level'];out=[]
    events={r['at']:r['level'] for r in spec['stimulus']}
    points=sorted(set(spec['times']+list(events)+[spec['reset_at']]))
    rows={}
    for t in points:
        if t>spec['times'][-1]: break
        state=expm(matrix(family,p,u)*(t-last))@state
        if t in events: u=events[t]
        if t==spec['reset_at']: state[0]*=spec['retained_fraction']
        rows[t]=[float(state[1])];last=t
    return np.array([rows[t] for t in spec['times']])
