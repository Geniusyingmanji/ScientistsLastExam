#!/usr/bin/env python3
"""Local diagnostics for the ten candidate tasks; never certification evidence.

Run: python scripts/diagnose_new_task_hardening.py --output tmp/hardening/diagnostics.json
Add --sweeps for 528 constant wastewater and 48 thermostat parameter probes.
No model calls, promotions, source mutation, or global evidence refresh occur here.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.check_task_contribution import check_task

TASKS={
    'EarthScience':['ActiveFullWaveformInversion','ChronologyAssimilation','DeformationMechanismInference','GroundwaterRemediationDesign','IceObservationNetworkDesign'],
    'Engineering':['CompositeLaminateStacking','ResilientPumpScheduling','BSM1AerationControl','WakeAwareFarmCoDesign','BOPTESTSupervisoryControl'],
}

def load(path):
    spec=importlib.util.spec_from_file_location('diagnostic_'+path.parent.parent.name+'_'+path.stem,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def summary(metrics):
    return {k:v for k,v in metrics.items() if isinstance(v,(int,float,bool))}


def constant_wastewater(m):
    specs=[s for s in m.INSTANCE_SPECS if s[1]=='development'];p=m._problem()
    base=np.array([m._run(m._baseline_factory,p,s)['cost'] for s in specs])
    ref=np.array([m._run(m._reference_factory,p,s)['cost'] for s in specs])
    best=None
    for kla in np.linspace(.25,12.,48):
        for recycle in np.linspace(0.,1.,11):
            factory=lambda p:lambda obs:{'kla_per_hour':float(kla),'internal_recycle':float(recycle)}
            rows=[m._run(factory,p,s) for s in specs]
            if all(r['feasible'] for r in rows):
                score=max(0.,float(np.mean((base-np.array([r['cost'] for r in rows]))/(base-ref))))
                if best is None or score>best['score']:
                    best={'score':score,'parameters':[float(kla),float(recycle)]}
    if best is not None:
        kla,recycle=best['parameters']
        best['metrics']=summary(m.evaluate(lambda p:lambda obs:{'kla_per_hour':kla,'internal_recycle':recycle}))
    return {'trials':528,'best':best,'selection_split':'development_only'}


def thermostat_sweep(m):
    def factory(gain,ventilation):
        def make(p):
            def step(obs):
                t=np.asarray(obs['zone_temperature_c']);occ=np.asarray(obs['occupancy'])
                heat=np.where(occ>0,np.clip(gain*(21.6-t),0,18),np.clip(2*(17-t),0,18))
                cool=np.where(occ>0,np.clip(gain*(t-24.4),0,18),np.clip(2*(t-29),0,18))
                return {'heating_kw':heat.tolist(),'cooling_kw':cool.tolist(),'ventilation_ach':np.clip(.25+ventilation*occ,.15,1.55).tolist()}
            return step
        return make
    best=None
    for gain in (2.,3.,4.2,5.,6.,8.):
        for vent in (.010,.012,.014,.016,.018,.020,.022,.025):
            metrics=m.evaluate(factory(gain,vent))
            if metrics['valid'] and (best is None or metrics['combined_score']>best['score']):
                best={'score':metrics['combined_score'],'parameters':[gain,vent],'metrics':summary(metrics)}
    return {'trials':48,'best':best,'selection_split':'development_only'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--sweeps',action='store_true')
    args=parser.parse_args()
    report={'scope':'local_diagnostic_not_admission_evidence','platform':platform.platform(),
            'revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),
            'tasks':{}}
    for domain,names in TASKS.items():
        for name in names:
            path=ROOT/'benchmarks'/domain/name
            meta=yaml.safe_load((path/'frontier_eval/metadata.yaml').read_text())
            task_id=meta['domain']+'/'+name
            entry=(path/'frontier_eval/entrypoint.txt').read_text().strip()
            evaluator=load(path/'verification/evaluator.py')
            baseline=getattr(load(path/'solution.py'),entry)
            reference_file='reference.py' if domain=='Engineering' else 'reference_solver.py'
            reference=getattr(load(path/'verification'/reference_file),entry)
            started=time.monotonic()
            row={'structural_gate':check_task(task_id,skip_eval=True),
                 'baseline':summary(evaluator.evaluate(baseline)),
                 'reference':summary(evaluator.evaluate(reference))}
            row['elapsed_seconds']=time.monotonic()-started
            # Public-data historical method comparison. This is not an isolated causal ablation.
            oldpath='benchmarks/'+domain+'/'+name+'/verification/'+reference_file
            original=subprocess.run(['git','show','8032e97:'+oldpath],cwd=ROOT,text=True,capture_output=True)
            if original.returncode==0 and 'import evaluator' not in original.stdout:
                namespace={};exec(compile(original.stdout,'historical_reference','exec'),namespace)
                row['historical_method_comparison']=summary(evaluator.evaluate(namespace[entry]))
            if name in ('CompositeLaminateStacking','ResilientPumpScheduling','WakeAwareFarmCoDesign'):
                old_oracle=subprocess.check_output(['git','show','8032e97:benchmarks/'+domain+'/'+name+'/verification/evaluator.py'],cwd=ROOT,text=True)
                namespace={};exec(compile(old_oracle,'historical_public_method','exec'),namespace)
                old_search=namespace['_reference']
                if name=='CompositeLaminateStacking':
                    compare=lambda p:{'ply_angles_deg':old_search(p)}
                elif name=='ResilientPumpScheduling':
                    compare=lambda p:{'pump_speed':old_search(p).tolist()}
                else:
                    def compare(p):
                        layout,yaw=old_search(p)
                        return {'layout_xy_m':layout.tolist(),'yaw_by_direction_deg':yaw.tolist()}
                row['historical_method_comparison']=summary(evaluator.evaluate(compare))
            if name=='ResilientPumpScheduling':
                def always_on(p):
                    speeds=evaluator._continuous_schedule(p,np.ones(24,dtype=bool))
                    return {'pump_speed':speeds}
                row['without_commitment_search']=summary(evaluator.evaluate(always_on))
            if name=='ChronologyAssimilation':
                def curves_collapsed(grid,catalog,lab,budget):
                    answer=dict(reference(grid,catalog,lab,budget))
                    if not answer['abstain']:
                        curves=np.asarray(answer.pop('sample_ages_years'))
                        nominal=np.array([r['nominal_age_years'] for r in catalog])
                        answer['age_offsets_years']=np.clip(np.median(curves-nominal,axis=1),-300,300)
                    return answer
                row['collapse_age_curve_artifact']=summary(evaluator.evaluate(curves_collapsed))
            if name=='GroundwaterRemediationDesign':
                def source(p):
                    x,y=p['source_location_m']
                    return {'plans':[[[x,y,0.,q]] for q in np.linspace(80.,950.,16)]}
                row['single_source_shortcut']=summary(evaluator.evaluate(source))
            if name=='BSM1AerationControl':
                row['constant_control']=summary(evaluator.evaluate(lambda p:lambda obs:{'kla_per_hour':1.,'internal_recycle':1.}))
                if args.sweeps:row['constant_grid']=constant_wastewater(evaluator)
            if name=='BOPTESTSupervisoryControl' and args.sweeps:
                row['thermostat_grid']=thermostat_sweep(evaluator)
            if name=='BOPTESTSupervisoryControl':
                def always_occupied(p):
                    public=dict(p,occupancy_forecast=np.full((p['horizon_steps'],2),38.).tolist())
                    return reference(public)
                row['without_occupancy_forecast']=summary(evaluator.evaluate(always_occupied))
            report['tasks'][task_id]=row
            print(task_id,'baseline',row['baseline']['combined_score'],'reference',row['reference']['combined_score'],flush=True)
            target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(report,indent=2)+'\n')
    return 0

if __name__=='__main__':raise SystemExit(main())
