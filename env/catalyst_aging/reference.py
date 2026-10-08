"""Author-informed bounded reference; receives public records, never a World."""
import time
import numpy as np
from scipy.optimize import least_squares
from .kernel import run_history


def fit(records, max_calls=20000, wall_seconds=180):
    started=time.monotonic(); calls=0; evaluations=[]; attempts=[]
    calibration=[]
    for record in records:
        for index,row in zip(record['spec']['event_indices'],record['observation']['values']):
            kind=record['spec']['events'][index-1]['kind']
            if kind in ('blank','standard'):
                calibration.append((index,1.5 if kind=='standard' else 0.,row[0]))
    if not calibration: raise ValueError('calibration observations required')
    instruments=[]
    for jump in [0]+list(range(5,12)):
        design=[]; target=[]
        for index,product,y in calibration:
            step=float(jump>0 and index>=jump)
            design.append([product,product*(index-1),1,index-1,product*step,step]);target.append(y)
        coef=np.linalg.lstsq(design,target,rcond=None)[0]
        residual=np.asarray(design)@coef-target
        instruments.append({'jump':jump,'coefficients':coef.tolist(),'sse':float(residual@residual)})
    instrument=min(instruments,key=lambda x:x['sse'])
    gain,gs,offset,os,gj,oj=instrument['coefficients']
    target=np.concatenate([np.asarray(r['observation']['values'])[:,0] for r in records])
    def parameters(x,family):
        return dict(rate_ref=x[0],activation_j_mol=x[1],deactivation_ref=x[2],
            deactivation_activation_j_mol=30000.,saturation=.4,gain=gain,gain_slope=gs,
            offset=offset,offset_slope=os,jump_event=instrument['jump'],gain_jump=gj,offset_jump=oj,
            fractions=[1.] if family=='single' else [x[3],1-x[3]],
            decay_multipliers=[1.] if family=='single' else [x[4],x[5]])
    models=[]
    for family in ('single','two'):
        lo=np.array([.02,40000,.003]+([] if family=='single' else [.4,.1,2.]))
        hi=np.array([.15,75000,.04]+([] if family=='single' else [.75,.5,7.]))
        best=None
        def residual(x):
            nonlocal calls,best
            if calls+len(records)>max_calls or time.monotonic()-started>wall_seconds:
                raise RuntimeError('reference budget exhausted')
            p=parameters(x,family)
            predicted=np.concatenate([run_history(r['spec'],p)[:,0] for r in records]);calls+=len(records)
            error=predicted-target;sse=float(error@error)
            evaluations.append({'family':family,'parameters':x.tolist(),'sse':sse,'forward_calls':calls})
            if best is None or sse<best['sse']:best={'family':family,'parameters':p,'sse':sse,'training_predictions':predicted.tolist()}
            return error
        for start in (.3,.7):
            try:
                result=least_squares(residual,lo+start*(hi-lo),bounds=(lo,hi),x_scale='jac',max_nfev=100)
                attempts.append({'family':family,'start':start,'success':bool(result.success),'nfev':result.nfev,'parameters':result.x.tolist()})
            except RuntimeError as exc:
                attempts.append({'family':family,'start':start,'failure':str(exc)})
        if best is not None:models.append(best)
    if not models:raise RuntimeError('no reference model fitted')
    return {'selected':min(models,key=lambda x:x['sse']),'models':models,'instruments':instruments,
            'attempts':attempts,'evaluations':evaluations,'forward_calls':calls,'seconds':time.monotonic()-started,
            'prior':'known kinetic formulas and bounds; no instance parameter/label access'}
