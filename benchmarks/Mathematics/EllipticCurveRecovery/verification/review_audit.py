"""Reproduce review shortcuts and capability ablations on a clean Linux tree.

This is an in-process diagnostic, not a sandbox or calibration claim. Candidate
exports let the strongest shortcuts be replayed through frontier_eval/run_eval.py.
"""
import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import time
from pathlib import Path

TASK = Path(__file__).resolve().parents[1]
ROOT = TASK.parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compact(result):
    return {k: v for k, v in result.items() if k != 'per_world'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--export-candidates', type=Path)
    args = parser.parse_args()
    if platform.system() != 'Linux':
        raise SystemExit('Review evidence must be generated on Linux.')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():
        raise SystemExit('Commit source before generating review evidence.')
    ev = load(TASK/'verification/evaluator.py', 'review_ev')
    ref = load(TASK/'verification/reference_solver.py', 'review_ref')
    baseline = load(TASK/'solution.py', 'review_baseline')
    started = time.monotonic()
    result = run(ev,ref,baseline,args.export_candidates)
    result['provenance'] = {
        'revision': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'clean_tree': True,
        'platform': platform.platform(), 'python': platform.python_version(),
        'source_sha256': {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(TASK.rglob('*')) if p.is_file() and '__pycache__' not in p.parts
                          and p.name != 'review_evidence.json'},
        'command': 'python '+str(Path(__file__).relative_to(ROOT))+' --output <outside-checkout>/review_evidence.json',
        'scope': 'Direct trusted-evaluator diagnostic; sandbox replay is separately tested. No model draw.',
        'wall_seconds': time.monotonic()-started}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('grid','provenance','refusal_traces')},sort_keys=True))


def threshold_candidate(n,k):
    def recover(problem,count_points,budget):
        deviations = [count_points(p)['point_count']-p-1 for p in problem['prime_list'][:n]]
        mean = sum(deviations)/len(deviations)
        a = round(k*mean)
        b = round(k*sum(abs(d) for d in deviations)/len(deviations))
        return {'a':a,'b':b,'abstain':False,'confidence':.8}
    return recover


def literal_source(ev,n):
    # Compile a candidate with literal truth and call order. It does not import
    # verification code at runtime; the evaluator receives its real query trace.
    answers=[]
    for spec in ev._BASE_DEVELOPMENT_SPECS+ev.HELDOUT_SPECS:
        w=ev._world(spec);supported=w['kind']=='elliptic'
        answers.append((w['a'],w['b']) if supported else (None,None))
    return 'ANSWERS = '+repr(answers)+'''\nINDEX = 0

def recover_curve(problem,count_points,budget):
    global INDEX
    a,b=ANSWERS[INDEX % len(ANSWERS)]
    INDEX += 1
    for p in (97,89)[:'''+str(n)+''']:
        count_points(p)
    return {'a':a,'b':b,'abstain':a is None,'confidence':1.0}
'''


def run(ev,ref,baseline,exports):
    result={'baseline':compact(ev.evaluate(baseline.recover_curve)),
            'reference':compact(ev.evaluate(ref.recover_curve)), 'ablations':{},'grid':[],'literal_replays':{}}
    result['reference_repeat_equal']=result['reference']==compact(ev.evaluate(ref.recover_curve))
    for key,value in [('ADAPTIVE',False),('DISCRIMINANT_FILTER',False),('MAX_QUERIES',4),('MAX_QUERIES',3)]:
        old=getattr(ref,key);setattr(ref,key,value)
        result['ablations'][key+'='+str(value)] = compact(ev.evaluate(ref.recover_curve))
        setattr(ref,key,old)
    for n in range(1,6):
        for k in (.5,1,1.5,2,2.5):
            r=ev.evaluate(threshold_candidate(n,k))
            result['grid'].append({'n':n,'k':k,'combined_score':r['combined_score'],'robustness_score':r['robustness_score']})
    result['grid_best']=max(result['grid'],key=lambda r:r['combined_score'])
    if exports:exports.mkdir(parents=True,exist_ok=True)
    for n in (0,1,2):
        source=literal_source(ev,n); namespace={};exec(source,namespace)
        result['literal_replays'][str(n)]={'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'metrics':compact(ev.evaluate(namespace['recover_curve']))}
        if exports:(exports/('memo_%d.py'%n)).write_text(source)
    result['refusal_traces']=[]
    for spec in ev._BASE_DEVELOPMENT_SPECS+ev.HELDOUT_SPECS:
        if spec[1]=='elliptic':continue
        w=ev._world(spec);oracle=ev._ArithmeticOracle(w);trace=[]
        for p in (97,89,83,79,73):
            r=oracle.count_points(p)
            pairs=ev._arithmetic.compatible_pairs(oracle.transcript,ev.COEFFICIENT_BOUND)
            trace.append({'prime':p,'count':r['point_count'],'bounded_lifts':None if pairs is None else len(pairs),
                          'nonsingular_lifts':None if pairs is None else len(ev._arithmetic.nonsingular(pairs))})
        result['refusal_traces'].append({'spec':spec,'trace':trace})
    return result


if __name__ == '__main__':
    main()
