"""Fixed Linux sandbox replay; private originals, public aggregates, no model calls.

The task-local revision_replay.json declares all methods before measurement.
Never imports an oracle or runs a builder's grid driver. Does not select methods,
update the task card, or turn contribution checks into difficulty evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()


def write_new(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
    path.chmod(0o600)


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', required=True)
    parser.add_argument('--private-root', type=Path, required=True)
    parser.add_argument('--phase', choices=('methods', 'contribution'), default='methods')
    args = parser.parse_args()
    import numpy
    import scipy
    from sle.registry import find_task
    from sle.evaluate import evaluate_candidate
    from sle.algorithms.common import task_package_sha256, runtime_source_sha256
    from scripts import check_task_contribution as gate
    threads = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')
    if platform.system() != 'Linux' or any(os.environ.get(k) != '1' for k in threads):
        raise SystemExit('Linux with all four numerical thread limits set to 1 required')
    if git('status', '--porcelain'):
        raise SystemExit('clean committed source required')
    spec = find_task(args.task, include_uncertified=True)
    protocol = json.loads((spec.task_dir/'references/revision_replay.json').read_text())
    private = args.private_root.resolve()
    if private == ROOT or ROOT in private.parents:
        raise SystemExit('private originals must be outside the checkout')
    os.umask(0o077)
    private.mkdir(mode=0o700, parents=False, exist_ok=False)
    bindings = dict(source_revision=git('rev-parse', 'HEAD'), task_package_sha256=task_package_sha256(spec),
                    runtime_source_sha256=runtime_source_sha256(), driver_sha256=sha(Path(__file__).read_bytes()))
    candidates = []
    for method in protocol['methods']:
        source_path = (spec.task_dir/method['candidate']).resolve()
        if spec.task_dir not in source_path.parents:
            raise ValueError('candidate outside task')
        source = source_path.read_bytes()
        if 'ablation' in method:
            signature = ('def %s(problem, experiment, *, ablation=None):' % spec.entrypoint).encode()
            if source.count(signature) != 1:
                raise ValueError('ablation derivation must locate exactly one candidate entrypoint')
            replacement = signature.replace(b'ablation=None', ('ablation=%r' % method['ablation']).encode())
            source = source.replace(signature, replacement, 1)
        target = private/(method['id']+'.py')
        target.write_bytes(source)
        target.chmod(0o600)
        candidates.append((method, target, sha(source)))
    plan = dict(task_id=spec.task_id, phase=args.phase, bindings=bindings, protocol=protocol,
                candidate_hashes={m['id']: h for m, _, h in candidates}, repeats=2,
                environment=dict(python=sys.version, numpy=numpy.__version__, scipy=scipy.__version__,
                                 platform=platform.platform(), threads={k:os.environ[k] for k in threads}))
    write_new(private/'plan.json', plan)
    records = []

    def record(candidate, method_id, repeat, call):
        tick = time.monotonic()
        metrics = call()
        index = len(records)
        full_path = private/('%02d.full.json' % index)
        write_new(full_path, metrics)
        row = dict(method=method_id, repeat=repeat, candidate_sha256=sha(Path(candidate).read_bytes()),
                   seconds=time.monotonic()-tick, full_metrics_sha256=sha(canonical(metrics)),
                   full_file_sha256=sha(full_path.read_bytes()),
                   scalars={k:v for k,v in metrics.items() if type(v) in (int,float,bool)})
        records.append(row)
        write_new(private/('%02d.receipt.json' % index), row)
        print(method_id, repeat, metrics.get('valid'), metrics.get('combined_score'), flush=True)
        return metrics

    if args.phase == 'methods':
        for method, candidate, _ in candidates:
            for repeat in (1, 2):
                record(candidate, method['id'], repeat,
                       lambda: evaluate_candidate(spec, candidate, timeout_s=protocol['timeout_s']))
        complete = all(r['scalars'].get('valid') == 1 and
                       r['scalars'].get('development_valid_rate') == 1 and
                       r['scalars'].get('heldout_valid_rate') == 1 for r in records)
        identical = all(records[i]['full_metrics_sha256'] == records[i+1]['full_metrics_sha256']
                        for i in range(0, len(records), 2))
        report = dict(all_worlds_valid=complete, identical_full_metrics=identical)
        success = complete and identical
    else:
        def recording_evaluate(task_spec, candidate, **kwargs):
            return record(candidate, 'contribution_%02d' % len(records), 1,
                          lambda: evaluate_candidate(task_spec, candidate, **kwargs))
        gate.evaluate_candidate = recording_evaluate
        report = gate.check_task(spec.task_id, timeout_s=protocol['timeout_s'])
        success = report['passed']
    unchanged = (not git('status', '--porcelain') and
                 bindings['task_package_sha256'] == task_package_sha256(spec) and
                 bindings['runtime_source_sha256'] == runtime_source_sha256())
    aggregate = dict(plan, records=records, report=report, source_unchanged=unchanged,
                     model_calls=0, scientific_admission='not_assessed')
    write_new(private/'aggregate.json', aggregate)
    print('complete', success, 'source_unchanged', unchanged, flush=True)
    return 0 if success and unchanged else 2


if __name__ == '__main__':
    raise SystemExit(main())
