"""Replay the review's fixed-shape grids, stronger nuisance fits, and ablations."""
import argparse
import hashlib
import importlib.util
import itertools
import json
import platform
import subprocess
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent

def load(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def compact(r):
    return {k:r[k] for k in ('combined_score','robustness_score','valid',
        'development_false_discovery_rate','development_correct_refusal_rate',
        'development_discovery_coverage','heldout_correct_refusal_rate')}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();ev=load('evaluator');ref=load('reference_solver')
    variants={'reference':{},'no_finite_size_fit':{'correction':False},
              'no_adequacy_test':{'adequacy':False},'no_separation_test':{'separation':False},
              'no_refusal':{'adequacy':False,'separation':False}}
    report={'variants':{name:compact(ev.evaluate(lambda *a,kw=kw:ref.solve(*a,**kw)))
                        for name,kw in variants.items()}}
    ladders=[(8,28,96),(8,16,32,64,128),(8,32,128),(16,64,256)]
    ladders+=list(itertools.product((8,12,16),(24,32,48,64),(96,128,192,256,384)))
    rows=[]
    for ladder,gate,mass,correction in itertools.product(ladders,(.05,.08,.13,.2,.4,.8),(0.8,.95,1.),(False,True)):
        def candidate(problem,lab,budget):
            lo,hi=problem['size_bounds']
            sizes=ladder if lo<=min(ladder) and max(ladder)<=hi else np.rint(np.geomspace(lo,hi,len(ladder))).astype(int)
            transcript=[]
            def record(n):
                r=lab(n);transcript.append(r);return r
            answer=ref.solve(problem,record,budget,sizes=sizes,correction=correction,
                             adequacy=False,separation=False,mass=mass)
            sizes=np.array([r['size'] for r in transcript]);logs=np.log([r['runtime_ms'] for r in transcript])
            best_rms=float('inf')
            for name in problem['classes']:
                y=logs-np.log([ref._shape(name,n) for n in sizes]);x=64./sizes
                a=np.clip(np.dot(x-x.mean(),y-y.mean())/max(np.sum((x-x.mean())**2),1e-15),-2,2) if correction else 0
                residual=y-a*x;best_rms=min(best_rms,float(np.std(residual)))
            if best_rms>gate:answer.update(abstain=True,scale=None)
            return answer
        rows.append({'ladder':list(ladder),'gate':gate,'mass':mass,'correction':correction,
                     **compact(ev.evaluate(candidate))})
    report['grid_count']=len(rows);report['best_by_development']=max(rows,key=lambda r:r['combined_score'])
    report['natural_ladders']=[r for r in rows if tuple(r['ladder']) in ladders[:4] and r['gate']==.13 and r['mass']==1. and not r['correction']]
    report['ambiguity_bounds']=[{'spec':list(s),'kl':ev.ambiguity_information_bound(ev._world(s))[0],
        'binary_accuracy_upper_bound':ev.ambiguity_information_bound(ev._world(s))[1]}
        for s in ev._BASE_DEVELOPMENT_SPECS+ev.HELDOUT_SPECS if s[1]=='ambiguous']
    report['provenance']={'revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
      'dirty':bool(subprocess.check_output(['git','status','--porcelain'],text=True)),
      'platform':platform.platform(),'python':platform.python_version(),'numpy':np.__version__,
      'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')}}
    args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
