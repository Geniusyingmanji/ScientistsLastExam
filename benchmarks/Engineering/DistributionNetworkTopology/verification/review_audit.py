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


def grid_candidate(n, threshold, consume_initial=True, rounding='floor'):
    def recover(problem, probe, budget):
        routes = problem['routes']
        keys = sorted(routes, key=lambda key:(len(routes[key]),key))
        index = round if rounding == 'nearest' else int
        selected = [keys[index(i*(len(keys)-1)/(n-1))] for i in range(n)]
        reports = list(problem['initial_reports']) if consume_initial else []
        reports += [probe(key) for key in selected[:budget]]
        failures = dict.fromkeys(problem['pipe_ids'],0)
        totals = failures.copy()
        for report in reports:
            for pipe in routes[report['route_id']]:
                totals[pipe] += 1
                failures[pipe] += not report['arrived']
        rates = {p: failures[p]/totals[p] for p in totals if totals[p]}
        chosen = sorted((p for p in rates if rates[p]>=threshold),key=lambda p:-rates[p])[:3]
        return {'broken_pipes':chosen or None,'abstain':not chosen,'confidence':.8}
    return recover


def run(ev,ref,baseline,exports):
    result = {'baseline':compact(ev.evaluate(baseline.recover_network)),
              'reference':compact(ev.evaluate(ref.recover_network)), 'ablations':{}, 'grid':[]}
    again = ev.evaluate(ref.recover_network)
    result['reference_repeat_equal'] = result['reference'] == compact(again)
    for key,value in [('MAX_SIZE',2),('ADAPTIVE',False),('STRUCTURAL_REFUSAL',False),('MODEL_CHECK',False),('COMPLEXITY_PRIOR',False)]:
        old = getattr(ref,key); setattr(ref,key,value)
        result['ablations'][key] = compact(ev.evaluate(ref.recover_network))
        setattr(ref,key,old)
    # Replay both common linspace conversions and both handling choices for the
    # new paid reports; 4 x 420 points, all charged calls fit remaining budget.
    for initial in (False,True):
        for rounding in ('floor','nearest'):
            for n in range(6,27):
                for step in range(1,21):
                    metrics = ev.evaluate(grid_candidate(n,step/20,initial,rounding))
                    result['grid'].append({'n':n,'threshold':step/20,'consume_initial':initial,'rounding':rounding,
                        'combined_score':metrics['combined_score'],'robustness_score':metrics['robustness_score']})
    result['grid_best'] = max(result['grid'], key=lambda r:r['combined_score'])
    result['grid_points_above_reference'] = sum(r['combined_score']>result['reference']['combined_score'] for r in result['grid'])
    if exports:
        import inspect
        exports.mkdir(parents=True,exist_ok=True)
        best=result['grid_best']
        source=inspect.getsource(grid_candidate)+'\nrecover_network = grid_candidate(%r,%r,%r,%r)\n' % (best['n'],best['threshold'],best['consume_initial'],best['rounding'])
        (exports/'grid_best.py').write_text(source)
    return result


if __name__ == '__main__':
    main()
