"""Matched initial-condition designs for future equation diagnostics.

This creates legal observable experiments, not microscopic interventions. A/B
remain dynamical after initialization; endpoint contrasts are not local fluxes.
"""
from .world import validate


def build_design(base, a_levels, b_levels, temperatures):
    if base.get('events'):
        raise ValueError('initial-state factorial requires no events')
    base = validate(base)
    def levels(values, field):
        if not isinstance(values,(list,tuple)) or len(values)!=2:
            raise ValueError('two distinct ordered levels required')
        checked=[]
        for v in values:
            q=dict(base,initial=dict(base['initial']))
            if field=='temperature':q[field]=v
            else:q['initial'][field]=v
            z=validate(q);checked.append(z[field] if field=='temperature' else z['initial'][field])
        if checked[0]>=checked[1]:raise ValueError('levels must increase')
        return checked
    aa,bb,tt=levels(a_levels,'A'),levels(b_levels,'B'),levels(temperatures,'temperature')
    return [validate(dict(base,initial=dict(base['initial'],A=a,B=b),temperature=t))
            for t in tt for b in bb for a in aa]


def validate_design(specs):
    if len(specs)!=8:raise ValueError('eight factorial arms required')
    specs=[validate(s) for s in specs]
    aa=sorted({s['initial']['A'] for s in specs});bb=sorted({s['initial']['B'] for s in specs});tt=sorted({s['temperature'] for s in specs})
    expected=build_design(specs[0],aa,bb,tt)
    if specs != expected:raise ValueError('confounded, duplicated or misordered design')
    return {'arms':8,'order':'temperature, B, A (A varies fastest)',
            'temperature_blocks':[[0,1,2,3],[4,5,6,7]],
            'scope':'Matched initial conditions; later concentrations are not clamped.'}
