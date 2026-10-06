"""Versioned development RMSE, not a model campaign score or discovery metric."""
import math,numbers
from .eligibility import prediction_mask
PROTOCOL='isotope-development-rmse-1'
AXES=('new_recipe','new_history','ambiguity_control')

def _matrix(values,rows):
    if not isinstance(values,list) or len(values)!=rows:raise ValueError('row count mismatch')
    out=[]
    for row in values:
        if not isinstance(row,list) or len(row)!=3:raise ValueError('three channels required')
        if any(isinstance(v,bool) or not isinstance(v,numbers.Real) or not math.isfinite(v) for v in row):raise ValueError('finite numeric predictions required')
        out.append([float(v) for v in row])
    return out

def experiment_error(spec,prediction,target):
    mask=prediction_mask(spec);p=_matrix(prediction,len(mask));y=_matrix(target,len(mask))
    errors=[p[i][j]-y[i][j] for i,row in enumerate(mask) for j,keep in enumerate(row) if keep]
    if not errors:return {'status':'unscorable','reason':'no_unassigned_cells','rmse':None,'cells':0}
    # hypot avoids overflow when squaring large but finite model outputs.
    error=math.hypot(*errors)/math.sqrt(len(errors))
    if not math.isfinite(error):raise ValueError('prediction residual exceeds numeric range')
    return {'status':'scored','rmse':error,'cells':len(errors)}

def summarize(records):
    groups={k:[] for k in AXES}
    for r in records:
        if set(r)!={'axis','spec','prediction','target'} or r['axis'] not in groups:raise ValueError('unknown record schema or axis')
        groups[r['axis']].append(experiment_error(r['spec'],r['prediction'],r['target']))
    result={}
    for axis,items in groups.items():
        vals=[r['rmse'] for r in items if r['status']=='scored']
        result[axis]={'experiments':len(items),'scored':len(vals),'unscorable':len(items)-len(vals),
                      'mean_experiment_rmse':math.fsum(v/len(vals) for v in vals) if vals else None}
    return {'protocol':PROTOCOL,'axes':result,'overall_score':None,
            'scope':'Equal experiment weight within each axis; scales all1. Assigned t=0 excluded. No cross-axis composite or discovery certification. Invalid predictions raise errors, never silently drop.'}
