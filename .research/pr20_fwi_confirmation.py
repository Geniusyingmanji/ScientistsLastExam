"""Fixed-oracle comparisons with raw physical errors and independent candidates."""
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path
import numpy as np
import scipy
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'benchmarks/EarthScience/ActiveFullWaveformInversion'
SOURCES = {
    'evaluator_frozen': ROOT / '.research/pr20_fwi_evaluator_before_noise.py',
    'reference_before': ROOT / '.research/pr20_fwi_reference_before.py',
    'reference_after': TASK / 'verification/reference_solver.py',
    'spatial_probe': ROOT / '.research/pr20_fwi_spatial_probe.py',
}

def load(name):
    spec = importlib.util.spec_from_file_location('confirmation_' + name, SOURCES[name])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

FRESH=tuple((seed,'supported',i) for i,seed in enumerate(
    [71011,71017,71023,71039,71047,71051,71059,71063,71069,71081,71089,71099]))+(
    (72011,'null',0),(72017,'misspecified',1),(72023,'structured_attenuation',2),
    (72031,'structured_attenuation',4),(72043,'structured_attenuation',6))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--methods',nargs='+',default=['old','new','grid','refined'])
    parser.add_argument('--split',choices=['development','heldout','fresh'],default='development')
    parser.add_argument('--output',required=True)
    parser.add_argument('--oracle',choices=['frozen','current'],default='frozen',
                        help='Frozen oracle reproduces the solver-only comparison; current includes independent noise streams.')
    args=parser.parse_args()
    if args.oracle == 'current':
        SOURCES['evaluator_frozen'] = TASK / 'verification/evaluator.py'
    e=load('evaluator_frozen')
    output=Path(args.output).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    HERE=output.parent
    if args.oracle == 'frozen':
        assert hashlib.sha256(SOURCES['evaluator_frozen'].read_bytes()).hexdigest() == '9b786e4c449d4937efaeff1102ecc2d7b6396b0b7a2bb7e8b4c89cd3d63d7fb9', 'The archived solver-only comparison requires its original oracle.'
    specs={'development':e.DEVELOPMENT_SPECS,'heldout':e.HELDOUT_SPECS,'fresh':FRESH}[args.split]
    report={'split':args.split,'numpy':np.__version__,'scipy':scipy.__version__,
            'platform':platform.platform(),'source_sha256':{str(SOURCES['evaluator_frozen'].relative_to(ROOT)): hashlib.sha256(SOURCES['evaluator_frozen'].read_bytes()).hexdigest()},'methods':{}}
    for method in args.methods:
        filename={'old':'reference_before','new':'reference_after','one_shot':'reference_after',
                  'grid':'spatial_probe','strict_grid':'spatial_probe','refined':'spatial_probe'}[method]
        c=load(filename)
        if method=='refined':c.REFINE=True;c.THRESHOLD=.20
        if method=='strict_grid':c.THRESHOLD=.12
        report['source_sha256'][filename]=hashlib.sha256(SOURCES[filename].read_bytes()).hexdigest()
        results=[];start_all=time.monotonic()
        for i,spec in enumerate(specs):
            start=time.monotonic();world=e._world(spec);a=e._Acquisition(world)
            candidate=c.invert_velocity_model
            if method=='one_shot':candidate=lambda *a:c.invert_velocity_model(*a[:-1],1)
            submission=candidate(e.GRID_SHAPE,e.SPACING_M,e._background(),e.VELOCITY_BOUNDS,
                e.SOURCE_INDICES.copy(),e.RECEIVER_X_M.copy(),np.arange(e.N_TIME)*e.DT_S,a.acquire,e.BUDGET_UNITS)
            v,confidence,abstain=e._validate(submission)
            row={'spec':spec,'seconds':time.monotonic()-start,'abstained':abstain,'sources':a.calls,
                 'model_score':0.,'waveform_score':0.,'mechanism_score':0.}
            if spec[1]=='supported' and not abstain:
                truth=world['velocity'];model,waveform,mechanism=e._supported_scores(world,v)
                w=np.linspace(.7,1.3,e.GRID_SHAPE[0])[:,None]
                row.update(model_score=model,waveform_score=waveform,mechanism_score=mechanism,
                    velocity_rmse_m_s=float(np.sqrt(np.mean((v-truth)**2))),
                    background_relative_error=float(np.sqrt(np.sum(w*(v-truth)**2)/np.sum(w*(truth-e._background())**2))))
                for name,region in [('upper',slice(0,10)),('lower',slice(10,None))]:
                    row[name+'_rmse_m_s']=float(np.sqrt(np.mean((v[region]-truth[region])**2)))
                np.savez(HERE/(Path(args.output).stem+f'-{method}-{i}.npz'),prediction=v,truth=truth)
            elif spec[1]!='supported':
                row['mechanism_score']=float(abstain)
            results.append(row)
            report['methods'][method]={'per_world':results,'wall_seconds':time.monotonic()-start_all}
            output.write_text(json.dumps(report,indent=2)+'\n')
            print(method,args.split,i,'abstain',abstain,'mechanism',round(row['mechanism_score'],6),
                  'RMSE',row.get('velocity_rmse_m_s'),'seconds',round(row['seconds'],2),flush=True)
        supported=[r for r in results if r['spec'][1]=='supported']
        unsupported=[r for r in results if r['spec'][1]!='supported']
        m=report['methods'][method]
        m['combined_score']=max(0.,(sum(r['mechanism_score'] for r in results)-len(unsupported))/len(supported))
        m['model_score']=float(np.mean([r['model_score'] for r in supported]))
        m['waveform_score']=float(np.mean([r['waveform_score'] for r in supported]))
        m['correct_refusal_rate']=float(np.mean([r['abstained'] for r in unsupported]))
        m['coverage']=float(np.mean([not r['abstained'] for r in supported]))
        m['mean_rmse_m_s']=float(np.mean([r['velocity_rmse_m_s'] for r in supported if not r['abstained']]))
        output.write_text(json.dumps(report,indent=2)+'\n')
        print('SUMMARY',method,{k:v for k,v in m.items() if k!='per_world'},flush=True)
if __name__=='__main__':main()
