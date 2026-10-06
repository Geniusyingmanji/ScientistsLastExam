"""Internal candidate-observation adapter; not a public-report exporter.

Only accepts already acquired observations. Cannot establish their provenance:
trusted orchestration must prevent clean/operator outputs from entering here.
No kernel, World or file access. Unknown fields fail closed, not silently copied.
"""
import math
import numbers
from .eligibility import CHANNELS,validate_spec,prediction_mask


def record(spec,observation):
    s=validate_spec(spec)
    if not isinstance(observation,dict) or set(observation)!={'axis','channels','values'}:
        raise ValueError('observation requires exactly axis, channels, values')
    axis=observation['axis']
    if not isinstance(axis,list) or any(isinstance(v,bool) or not isinstance(v,numbers.Real) or not math.isfinite(v) for v in axis) or axis!=s['times']:
        raise ValueError('observation axis differs from requested times')
    if observation['channels']!=list(CHANNELS):raise ValueError('unexpected channels or order')
    values=observation['values']
    if not isinstance(values,list) or len(values)!=len(axis):raise ValueError('unexpected observation row count')
    rows=[]
    for row in values:
        if not isinstance(row,list) or len(row)!=3:raise ValueError('each row needs three channel values')
        if any(isinstance(v,bool) or not isinstance(v,numbers.Real) or not math.isfinite(v) for v in row):raise ValueError('values must be finite numbers')
        rows.append([float(v) for v in row])
    # Do not clip Gaussian observations or normalize their sums.
    return {'spec':s,'observation':{'axis':s['times'][:],'channels':list(CHANNELS),'values':rows},'prediction_mask':prediction_mask(s)}
