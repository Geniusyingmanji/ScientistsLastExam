"""Bounded exposed-development screen. Zero model calls; privileged known-family fit."""
import argparse,json,time
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from .world import World,baseline
from .kernel import predict

def screen():
    results=[]
    for seed in (100,101,202):
        start=time.monotonic();w=World(seed);train=[]
        for q in ([.25]*4,[.5,0,0,.5],[0,.5,.5,0]):
            s=w.example();s['source'][0]['fractions']=q;train.append(s)
        s=w.example();s['source'].append({'at':3.,'fractions':[1.,0,0,0]});train.append(s)
        records=[{'spec':s,'observation':w.run(s,noise_key='isotope-screen-'+str(i))} for i,s in enumerate(train)]
        calls=[0];best=[float('inf'),None];cap=False
        def residual(p):
            if calls[0]+len(train)>2000:raise RuntimeError('fit cap')
            calls[0]+=len(train)
            e=np.concatenate([(predict(*p,s)-np.asarray(r['observation']['values'])).ravel() for s,r in zip(train,records)])
            loss=float(e@e)
            if loss<best[0]:best[:]=[loss,p.copy()]
            return e
        for p in ([.4,.25],[1.2,.75]):
            try:least_squares(residual,p,bounds=([.1,0],[2,1]),max_nfev=80)
            except RuntimeError:cap=True;break
        panel=w.panel(710,'conditions',3)+w.panel(711,'interventions',3)
        truth=np.concatenate([np.asarray(w.run(s)['values']).ravel() for s in panel])
        outputs={'uninformed':np.concatenate([np.asarray(baseline([],s)).ravel() for s in panel]),'empirical':np.concatenate([np.asarray(baseline(records,s)).ravel() for s in panel]),'author_reference':np.concatenate([predict(*best[1],s).ravel() for s in panel])}
        results.append({'world_run_calls':10,'training_experiments':4,'validation_experiments':6,'experiment_units':sum(w.cost(s) for s in train+panel),'fit_kernel_predictions':calls[0],'validation_kernel_predictions':6,'cap_reached':cap,'rmse':{k:float(np.sqrt(np.mean((v-truth)**2))) for k,v in outputs.items()},'wall_seconds':time.monotonic()-start})
    return {'schema':'sle-isotope-screen-1','status':'prototype','paid_model_requests':0,'scope':'Three exposed development instances; known-family author reference with supplied bounds. No difficulty or universal identifiability claim. Errors are dimensionless RMSE, not model scores.','instances':results}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();d=screen();Path(a.output).write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d))
