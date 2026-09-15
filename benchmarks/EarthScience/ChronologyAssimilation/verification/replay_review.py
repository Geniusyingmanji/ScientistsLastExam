"""Reproduce legal ablations, all difficulty levels and the review's cheap grid."""
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


def cheap(grid,catalog,lab,budget,n=5,std=.15,chi_gate=4.,coherence_gate=.35,edge=1):
    empty={'temperature_mean':[],'temperature_std':[],'age_offsets_years':[],
           'abstain':True,'confidence':.1}
    chi=np.mean([((np.asarray(r['calibration_proxy_values'])-r['sensitivity']*
             np.asarray(r['calibration_temperature_c']))/r['calibration_noise_std'])**2 for r in catalog])
    if chi>chi_gate:return empty
    curves=[];signals=[];used=0
    for row in catalog:
        nominal=np.asarray(row['nominal_age_years']);cost=1+int(np.ceil(n/5))
        if used+cost<=budget:
            indices=np.linspace(edge,len(nominal)-1-edge,n,dtype=int)
            response=lab(int(row['proxy_index']),indices);used+=response['budget_cost']
            curve=np.interp(nominal,nominal[indices],np.maximum.accumulate(response['dated_age_years']))
        else:curve=nominal
        curve=np.maximum.accumulate(np.clip(curve,grid[0],grid[-1]));curves.append(curve)
        signals.append(np.interp(grid,curve,np.asarray(row['values'])/row['sensitivity']))
    matrix=np.asarray(signals);mean=matrix.mean(axis=0)
    if np.mean((matrix-mean)**2)>coherence_gate:return empty
    return {'temperature_mean':mean,'temperature_std':np.full_like(mean,std),
            'sample_ages_years':curves,'abstain':False,'confidence':.8}


def compact(r):
    return {k:r[k] for k in ('combined_score','robustness_score','valid',
         'development_false_discovery_rate','development_correct_refusal_rate',
         'development_age_mae_years','development_age_increment_mae_years','development_mean_crps_c')}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();ev=load('evaluator');ref=load('reference_solver')
    variants={'reference':{},'no_joint_chronology':{'joint':False},'no_GP_field':{'field':False},
        'no_age_error_propagation':{'propagate':False},'no_calibration_test':{'calibration':False},
        'no_coherence_test':{'coherence':False},'no_refusal':{'calibration':False,'coherence':False}}
    report={'variants':{name:compact(ev.evaluate(lambda *a,kw=kw:ref.solve(*a,**kw)))
                        for name,kw in variants.items()}}
    report['difficulty_ladder']={}
    for level in (1,2,3):
        ev.DIFFICULTY=level;report['difficulty_ladder'][level]=compact(ev.evaluate(ref.reconstruct_climate))
    ev.DIFFICULTY=1;rows=[]
    for n,std,chi,coherence,edge in itertools.product((2,3,4,5,6,8,10),(.03,.06,.1,.15,.2,.3,.5,1.),(1.5,4.,100.),(.2,.35,.5),(0,1)):
        rows.append({'n':n,'std':std,'chi_gate':chi,'coherence_gate':coherence,'edge':edge,
            **compact(ev.evaluate(lambda *a:cheap(*a,n=n,std=std,chi_gate=chi,coherence_gate=coherence,edge=edge)))})
    report['grid_count']=len(rows);report['best_by_development']=max(rows,key=lambda r:r['combined_score'])
    report['provenance']={'revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
      'dirty':bool(subprocess.check_output(['git','status','--porcelain'],text=True)),
      'platform':platform.platform(),'python':platform.python_version(),'numpy':np.__version__,
      'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')}}
    args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
