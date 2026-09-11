#!/usr/bin/env python3
"""Scoped Linux evidence: secure witnesses/ablations and bounded shortcut probes.

No model calls. Builder probes access evaluator labels only to score a fixed grid
on development, then evaluate the selected strategy once on heldout. They are not
independent model calibration or a proof that every shortcut has been excluded.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import itertools
import json
import platform
import sys
import tempfile
import time
from pathlib import Path
import numpy as np
import scipy
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sle.evaluate import evaluate_candidate
from sle.metric_visibility import SEARCH_VISIBLE_KEYS
from sle.provenance import source_provenance, finalize_report_trust
from sle.registry import find_task
TASKS = {'Neuroscience/NeuralReportAttribution': ('reference_fit.py', 'infer_circuit',
         ['one_unit', 'six_units', 'ignore_instruments', 'never_abstain', 'no_model_selection'])}


def summary_metrics(metrics):
    """Publish aggregate audit evidence without shipping per-world answer keys."""
    return {key: value for key, value in metrics.items() if key != 'per_instance'}

def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def shortcut_probe(spec):
    module = load(spec.task_dir / 'verification/evaluator.py')
    kinds = ['recurrent', 'report_only'] * 3 + ['none'] * 2 + ['unsupported'] * 2
    bases = (381900, 527300)
    step = 113
    cache = []
    for base in bases:
        rows = []
        for (i, kind) in enumerate(kinds):
            world = module.make_world(base + i * step, kind)
            lab = module.Campaign(world)
            obs = lab({'kind': 'response', 'report': 1, 'frequency': 0, 'units': 1})
            h = np.array(obs['real']) + 1j * np.array(obs['imag'])
            a = -np.linalg.pinv(h).real
            feature = (float(a[1, 2]), float(a[1, 3]))
            rows.append((world, feature))
        cache.append(rows)
    grid = itertools.product(np.linspace(-0.2, 0.3, 9), np.linspace(0.2, 1.8, 12), np.linspace(0.2, 1.8, 9))

    def score(config, rows):
        utilities = []
        for (world, feature) in rows:
            (threshold, scale_f, scale_r) = config
            (f, r) = feature
            answer = {'model': 'recurrent' if f > threshold else 'report_only', 'feedback': float(np.clip(f * scale_f, 0, 1.2)) if f > threshold else 0.0, 'report_feedback': float(np.clip(r * scale_r, 0, 1.2))}
            utilities.append(module.score_world(world, answer)['mechanism'])
        return max(0.0, (sum(utilities) / len(utilities) - 0.2) / 0.8)
    best = (-1, None)
    count = 0
    for config in grid:
        count += 1
        value = score(config, cache[0])
        if value > best[0]:
            best = (value, config)
    return {'strategies': count, 'development_best': best[0], 'selected_parameters': [float(v) for v in best[1]], 'heldout_selected_once': score(best[1], cache[1]), 'observations': 'uncalibrated one-response inverse transfer entries', 'scope': 'finite builder probe, not exhaustive shortcut exclusion'}

def calibrated_shortcut_probe(spec):
    module = load(spec.task_dir / 'verification/evaluator.py')
    probe = load(spec.task_dir / 'verification/algebraic_probe.py')
    kinds = ['recurrent', 'report_only'] * 3 + ['none'] * 2 + ['unsupported'] * 2
    # Cache development only; heldout is first evaluated after selection.
    rows = []
    for i, kind in enumerate(kinds):
        world = module.make_world(381900 + i * 113, kind)
        lab = module.Campaign(world)
        features = probe.acquire_features(world['problem'], lab)
        assert lab.used == 8
        rows.append((world, features))
    grid = itertools.product(np.linspace(.08, .38, 7), np.linspace(.15, .65, 6),
                             (.08, .12, .16, .2), np.linspace(.7, 1.2, 6), (.8, 1., 1.2))
    best, count = (-1., None), 0
    for config in grid:
        count += 1
        raw = np.mean([module.score_world(w, probe.answer_from_features(f, config))['mechanism']
                       for w, f in rows])
        score = max(0., (float(raw) - .2) / .8)
        if score > best[0]:
            best = score, config
    return {'strategies': count, 'development_best': best[0],
            'selected_parameters': [float(v) for v in best[1]], 'units': 8,
            'observations': 'calibration twice and two response frequencies per report condition; '
                            'deconvolution and A = i omega I - inverse(R); no likelihood fit',
            'scope': 'fixed development grid, selected candidate confirmed on heldout once in sandbox'}


def secure_source(spec, source, timeout):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'candidate.py'
        path.write_text(source)
        metrics = evaluate_candidate(spec, path, timeout_s=timeout)
    return {'candidate_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'metrics': summary_metrics(metrics)}


def heldout_validation_probe(spec, timeout):
    module = load(spec.task_dir / 'verification/evaluator.py')
    kinds = ['recurrent', 'report_only'] * 3 + ['none'] * 2 + ['unsupported'] * 2
    request = {'kind': 'response', 'report': 0, 'frequency': 0, 'units': 1}
    fingerprints = {}
    for split, base in (('development', 381900), ('heldout', 527300)):
        fingerprints[split] = []
        for i, kind in enumerate(kinds):
            lab = module.Campaign(module.make_world(base + i*113, kind))
            digest = hashlib.sha256(json.dumps(lab(request), sort_keys=True).encode()).hexdigest()
            fingerprints[split].append(digest)
    assert set(fingerprints['development']).isdisjoint(fingerprints['heldout'])
    # Deliberately adversarial builder fixture, not a truth-blind shortcut or calibration.
    # Keep the temporary membership table out of the published report and repository.
    source = ('import hashlib, json\n'
              'def infer_circuit(problem, experiment):\n'
              f'    data = experiment({request!r})\n'
              '    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()\n'
              f'    return {{"model": "invalid"}} if digest in {fingerprints["heldout"]!r} else {{"abstain": True}}\n')
    result = secure_source(spec, source, timeout)
    metrics = result['metrics']
    result['passed'] = (metrics.get('valid') == metrics.get('feasibility_rate') == 1.
                        and metrics.get('heldout_valid_rate') == 0.
                        and metrics.get('combined_score') == 0.)
    result['scope'] = ('builder-injected heldout-only invalid responses via paid observation fingerprints; '
                       'public validity must stay development-only; temporary fixture not published')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=300)
    args = parser.parse_args()
    if platform.system() != 'Linux':
        raise SystemExit('Run scoped evidence on Linux with Bubblewrap; local unit checks are separate.')
    report = {'schema_version': 2, 'source_provenance': source_provenance(ROOT), 'environment': {'python': sys.version, 'platform': platform.platform(), 'numpy': np.__version__, 'scipy': scipy.__version__}, 'evidence_scope': 'secure baselines, truth-blind witnesses and ablations; builder-only finite probes', 'model_calibration': 'not_run_no_configured_model_endpoint', 'tasks': []}
    passed = True
    for (task_id, (filename, entry, ablations)) in TASKS.items():
        spec = find_task(task_id, include_uncertified=True)
        reference = spec.task_dir / 'verification' / filename
        rows = {'runtime_source_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(spec.task_dir.rglob('*.py'))}}
        for (name, path) in (('baseline', spec.initial_program_path), ('reference', reference)):
            start = time.monotonic()
            first = evaluate_candidate(spec, path, timeout_s=args.timeout)
            first_seconds = time.monotonic() - start
            start = time.monotonic()
            second = evaluate_candidate(spec, path, timeout_s=args.timeout)
            second_seconds = time.monotonic() - start
            ok = first == second and first.get('valid') == 1 and (not first.get('infrastructure_failure'))
            if name == 'baseline':
                ok = ok and first.get('combined_score') == 0
            passed = passed and ok
            rows[name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'deterministic': first == second, 'elapsed_seconds': [first_seconds, second_seconds], 'metrics': summary_metrics(first), 'passed': ok}
            print(task_id, name, first.get('combined_score'), 'passed', ok, flush=True)
        rows['ablations'] = {}
        for ablation in ablations:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'candidate.py'
                source = reference.read_text().replace('ablation=None', f'ablation={ablation!r}', 1)
                path.write_text(source)
                metrics = evaluate_candidate(spec, path, timeout_s=args.timeout)
                valid = metrics.get('valid') == 1 and (not metrics.get('infrastructure_failure'))
                passed = passed and valid
                rows['ablations'][ablation] = {'candidate_sha256': hashlib.sha256(source.encode()).hexdigest(), 'metrics': summary_metrics(metrics), 'delta_from_reference': rows['reference']['metrics']['combined_score'] - metrics['combined_score'], 'heldout_delta_from_reference': rows['reference']['metrics']['heldout_mechanism_score'] - metrics['heldout_mechanism_score']}
                print(task_id, ablation, metrics.get('combined_score'), flush=True)
        rows['shortcut_probe'] = shortcut_probe(spec)
        rows['calibrated_shortcut_probe'] = calibrated_shortcut_probe(spec)
        probe_source = (spec.task_dir / 'verification/algebraic_probe.py').read_text()
        config = tuple(rows['calibrated_shortcut_probe']['selected_parameters'])
        selected_source = probe_source + f"\n_selected = infer_circuit\ndef infer_circuit(problem, experiment):\n    return _selected(problem, experiment, config={config!r})\n"
        selected = secure_source(spec, selected_source, args.timeout)
        selected_metrics = selected['metrics']
        selected_ok = (selected_metrics.get('valid') == 1 and
                       abs(selected_metrics['combined_score'] - rows['calibrated_shortcut_probe']['development_best']) < 1e-9)
        passed = passed and selected_ok
        rows['calibrated_shortcut_probe'].update(secure_confirmation=selected, passed=selected_ok)
        rows['null_or_refuse'] = secure_source(spec, probe_source + '\ninfer_circuit = null_or_refuse\n', args.timeout)
        null_metrics = rows['null_or_refuse']['metrics']
        passed = passed and null_metrics.get('valid') == 1 and null_metrics.get('development_discovery_coverage') == 0
        rows['heldout_invalid_probe'] = heldout_validation_probe(spec, args.timeout)
        passed = passed and rows['heldout_invalid_probe']['passed']
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'metrics.json'
            subprocess.run([sys.executable, str(spec.task_dir / 'frontier_eval/run_eval.py'),
                            '--candidate', str(spec.initial_program_path), '--metrics-out', str(output)], check=True)
            wrapper = json.loads(output.read_text())
        wrapper_ok = set(wrapper) <= set(SEARCH_VISIBLE_KEYS) and wrapper.get('valid') == 1 and wrapper.get('combined_score') == 0
        rows['wrapper'] = {'metrics': wrapper, 'passed': wrapper_ok}
        passed = passed and wrapper_ok
        print(task_id, 'calibrated shortcut', selected_metrics['combined_score'],
              'null/refusal', null_metrics.get('combined_score'),
              'heldout sealing', rows['heldout_invalid_probe']['passed'], flush=True)
        rows['task'] = task_id
        report['tasks'].append(rows)
    finalize_report_trust(report, passed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return 0 if passed else 1
if __name__ == '__main__':
    raise SystemExit(main())
