"""Operator-only isotope bookkeeping; synthetic, no isotope kinetic effects."""
import numpy as np


def target(source, scrambling):
    q=np.asarray(source,dtype=float)
    a=q[1]+q[3];b=q[2]+q[3]
    paired=np.array([q[0],q[1]+q[2],q[3]])
    independent=np.array([(1-a)*(1-b),a*(1-b)+(1-a)*b,a*b])
    return (1-scrambling)*paired+scrambling*independent


def predict(rate,scrambling,spec):
    state=np.array([1.,0.,0.]);last=0.;source=spec['source'][0]['fractions'];rows={}
    events={x['at']:x['fractions'] for x in spec['source']}
    for t in sorted(set(spec['times']+list(events))):
        if t>spec['times'][-1]:break
        goal=target(source,scrambling)
        state=goal+(state-goal)*np.exp(-rate*(t-last))
        if t in events:source=events[t]
        rows[t]=state.copy();last=t
    return np.array([rows[t] for t in spec['times']])
