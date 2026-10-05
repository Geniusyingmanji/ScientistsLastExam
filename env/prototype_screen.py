"""Bounded local feasibility screen; never makes model/API requests.

Outputs aggregate diagnostics only. Author-informed fit has both kernel families
and parameter bounds; it never receives the sampled parameters or family label.
"""
import argparse
import importlib
import json
import time
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares


def screen(name):
    mod=importlib.import_module('env.'+name+'.world');kernel=importlib.import_module('env.'+name+'.kernel');results=[]
    bounds={'adaptive_signaling':{'feedforward':([.05,.2,.2],[2.,3.,3.]),'feedback':([.05,.2,.2],[2.,3.,3.])},'retention_transport':{'exchange':([.2,.05,.05],[3.,2.,1.5]),'parallel':([.5,.02,.1],[3.,1.,.9])}}[name]
    for seed in [100,101,202]:
        start=time.monotonic();w=mod.World(seed)
        train=w.panel(4100,'conditions',3)+w.panel(4101,'interventions',3)
        test=w.panel(4200,'conditions',3)+w.panel(4201,'interventions',3)
        records=[{'spec':s,'observation':w.run(s,noise_key='screen-train-'+str(i))} for i,s in enumerate(train)]
        ys=[np.asarray(r['observation']['values']) for r in records];calls=[0];best=[float('inf'),None,None];exhausted=False
        def residual(p,family):
            if calls[0]+len(train)>4000: raise RuntimeError('fitting forward-prediction cap reached')
            calls[0]+=len(train)
            result=np.concatenate([(kernel.predict(family,p,s)-y).ravel() for s,y in zip(train,ys)])
            error=float(result@result)
            if error<best[0]:best[:]=[error,family,p.copy()]
            return result
        for family,(low,high) in bounds.items():
            for frac in [.3,.7]:
                try:least_squares(residual,np.array(low)+frac*(np.array(high)-low),bounds=(low,high),args=(family,),max_nfev=80,ftol=1e-7,xtol=1e-7,gtol=1e-7)
                except RuntimeError:exhausted=True;break
            if exhausted:break
        truth=np.concatenate([np.asarray(w.run(s)['values']).ravel() for s in test])
        oracle=np.concatenate([kernel.predict(best[1],best[2],s).ravel() for s in test])
        empirical=np.concatenate([np.asarray(mod.baseline(records,s)).ravel() for s in test])
        scale=w.scales[0]
        rmse=lambda x:float(np.sqrt(np.mean((x-truth)**2))/scale)
        results.append({'development_instance':seed,'training_experiments':6,'heldout_experiments':6,'experiment_cost':sum(w.cost(s) for s in train+test),'fit_forward_predictions':calls[0],'fit_cap_reached':exhausted,'zero_nrmse':rmse(np.zeros_like(truth)),'empirical_nrmse':rmse(empirical),'author_informed_nrmse':rmse(oracle),'wall_seconds':time.monotonic()-start})
    return {'environment':name,'status':'prototype','results':results}


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    result={'schema':'sle-prototype-screen-v1','paid_model_requests':0,'scope':'Exposed development instances; author-informed reference, not model results or certified difficulty. Six training experiments per fit; two family hypotheses, two starts each. Heldout clean targets remain private.', 'worlds':[screen(n) for n in ['adaptive_signaling','retention_transport']]}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__': main()
