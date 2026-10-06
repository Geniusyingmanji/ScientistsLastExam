"""Prototype public eligibility only: no kernel, World, parameters or observations.

Not connected to shared scoring. Passing these checks does not establish novelty,
mechanism dependence, numerical correctness or calibrated uncertainty.
"""
from env.prototype_history import real,times

CHANNELS=('unlabeled','single_label','double_label')


def validate_spec(spec):
    if not isinstance(spec,dict) or set(spec)!={'times','source'}:
        raise ValueError('expected exactly times and source')
    axis=times(spec['times']);source=spec['source']
    if not isinstance(source,list) or not 1<=len(source)<=4:raise ValueError('source needs 1..4 segments')
    rows=[]
    for row in source:
        if not isinstance(row,dict) or set(row)!={'at','fractions'}:raise ValueError('segment needs at and fractions')
        q=row['fractions']
        if not isinstance(q,list) or len(q)!=4:raise ValueError('fractions need four entries ordered 00,10,01,11')
        q=[real(v,0,1,'fraction') for v in q]
        if abs(sum(q)-1)>1e-10:raise ValueError('fractions must sum to one')
        rows.append({'at':real(row['at'],0,12,'at'),'fractions':q})
    if rows[0]['at']!=0 or any(b['at']<=a['at'] for a,b in zip(rows,rows[1:])):raise ValueError('source starts at zero and strictly increases')
    return {'times':axis,'source':rows}


def prediction_mask(spec):
    """Exclude only assigned t=0 values; remaining cells are not certified novel."""
    s=validate_spec(spec)
    return [[t>0]*3 for t in s['times']]


def contrast_eligibility(control,treatment,row,channel):
    a=validate_spec(control);b=validate_spec(treatment)
    if channel not in CHANNELS:raise ValueError('unknown observable channel')
    if type(row) is not int or row<0 or row>=min(len(a['times']),len(b['times'])):raise ValueError('invalid readout row')
    t=a['times'][row]
    if t!=b['times'][row]:raise ValueError('paired readouts must use the same time')
    if t==0:return {'eligible':False,'reason':'assigned_initial_state'}
    # Controls at the readout itself cannot change continuous product instantly.
    cuts=sorted(set([0.,t]+[x['at'] for s in (a,b) for x in s['source'] if x['at']<t]))
    for lo,hi in zip(cuts,cuts[1:]):
        qa=next(x['fractions'] for x in reversed(a['source']) if x['at']<=lo)
        qb=next(x['fractions'] for x in reversed(b['source']) if x['at']<=lo)
        if hi>lo and qa!=qb:return {'eligible':True,'reason':'different_pre_readout_history_not_mechanism_certificate'}
    return {'eligible':False,'reason':'identical_pre_readout_history'}
