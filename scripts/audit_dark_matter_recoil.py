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
from sle.provenance import source_provenance, finalize_report_trust
from sle.registry import find_task
TASKS = {'ParticlePhysics/DarkMatterRecoilAttribution': ('reference_profile.py', 'infer_recoil', ['one_unit', 'ignore_gain', 'fixed_halo'])}

def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def peak_features(counts, controls):
    """Single-target features, including narrow residuals omitted in the first audit."""
    excess = np.maximum(0, counts - controls / 8)
    smooth = np.convolve(excess, np.ones(3) / 3, mode="valid")
    # Approximate variance of the centre-minus-three-bin-mean contrast.
    variance = counts + controls / 64
    contrast_var = (variance[:-2] + 4 * variance[1:-1] + variance[2:]) / 9
    peak = float(np.max((excess[1:-1] - smooth) / np.sqrt(np.maximum(1, contrast_var))))
    fractional_peak = float(np.max((excess[1:-1] - smooth) / np.maximum(1, smooth)))
    return peak, fractional_peak


def probe_answer(problem, experiment, config):
    """Legal truth-blind four-way candidate; no evaluator state or labels."""
    target, units, threshold, ratio, mass, peak_kind, peak_threshold = config
    obs = experiment({"target": int(target), "units": int(units)})
    counts, controls = np.array(obs["counts"]), np.array(obs["background_counts"])
    excess = np.maximum(0, counts - controls / 8)
    if excess.sum() / units < threshold:
        return {"model": "none"}
    if peak_features(counts, controls)[int(peak_kind)] > peak_threshold:
        return {"abstain": True}
    hardness = excess[9:].sum() / max(1, excess[:9].sum())
    return {"model": "q2" if hardness > ratio else "contact", "mass_gev": float(mass)}


def constant_mass_bound(module, worlds, answers=None):
    """Exact upper bound over every legal constant, not just a sampled mass grid.

    Utility is piecewise linear in log(m). All extrema occur at legal endpoints
    or at a true log mass +/- the scoring radius. Default model/negative decisions
    are perfect: this deliberately grants MORE information than any legal shortcut.
    Optional recorded reference answers reproduce the reviewer's replacement test.
    """
    knots = [10.0, 250.0]
    for w in worlds:
        if w["kind"] in module.LAWS:
            knots.extend(np.clip(w["mass"] * np.exp(np.array([-0.25, 0, 0.25])), 10, 250))
    best = (-1.0, None)
    for mass in knots:
        utilities = []
        for i, w in enumerate(worlds):
            if answers is None:
                answer = {"abstain": True} if w["kind"] == "unsupported" else {"model": w["kind"]}
            else:
                answer = dict(answers[i])
            if answer.get("model") in module.LAWS:
                answer["mass_gev"] = float(mass)
            utilities.append(module.score_world(w, answer)["mechanism"])
        value = module.normalized_score(utilities)
        if value > best[0]:
            best = (value, float(mass))
    return {"score": best[0], "mass_gev": best[1], "knots_checked": len(knots),
            "scope": "exact continuous constant-mass bound with " +
                     ("perfect model/null/refusal decisions" if answers is None else "recorded reference decisions")}


def shortcut_probe(spec):
    module = load(spec.task_dir / 'verification/evaluator.py')
    worlds = {split: list(module.split_worlds(split)) for split in module.SPLIT_SEEDS}
    masses = np.geomspace(10, 250, 48)
    thresholds = [0, 5, 15, 30, 60, 120]
    ratios = [0, .05, .1, .2, .4, .8, 1, 1.5, 2]
    peak_grid = [(0, value) for value in [1.5, 2, 3, 5, float("inf")]] + [
                (1, value) for value in [.1, .25, .5, 1, 2]]
    cache = {}
    for split, rows in worlds.items():
        for target, units in itertools.product(range(3), [1, 3, module.BUDGET]):
            features = []
            for w in rows:
                obs = module.Campaign(w)({"target": target, "units": units})
                counts, controls = np.array(obs['counts']), np.array(obs['background_counts'])
                excess = np.maximum(0, counts - controls / 8)
                features.append([excess.sum() / units, excess[9:].sum() / max(1, excess[:9].sum()),
                                 *peak_features(counts, controls)])
            cache[split, target, units] = np.asarray(features)
    dev = worlds['development']
    signal = np.array([w['kind'] in module.LAWS for w in dev])
    truth_mass = np.array([w['mass'] for w in dev])
    credit = np.maximum(0, 1 - np.abs(np.log(masses[:, None] / truth_mass)) / .25) * signal
    kinds = np.array([w['kind'] for w in dev])
    best, selected, count = -1., None, 0
    family_best = []
    for target, units in itertools.product(range(3), [1, 3, module.BUDGET]):
        features = cache['development', target, units]
        local_best = -1.
        for threshold, ratio, (peak_kind, peak_threshold) in itertools.product(thresholds, ratios, peak_grid):
            null = features[:, 0] < threshold
            abstain = (~null) & (features[:, 2 + peak_kind] > peak_threshold)
            law = np.where(features[:, 1] > ratio, 'q2', 'contact')
            positive = (~null) & (~abstain) & (law == kinds)
            negative = np.sum(null & (kinds == 'none')) + np.sum(abstain & (kinds == 'unsupported'))
            scores = np.maximum(0, ((credit @ positive + negative) / len(dev) - module.ZERO_UTILITY) / (1-module.ZERO_UTILITY))
            j = int(np.argmax(scores)); value = float(scores[j])
            count += len(masses)
            local_best = max(local_best, value)
            if value > best:
                best = value
                selected = [target, units, threshold, ratio, float(masses[j]), peak_kind, peak_threshold]
        family_best.append({'target': target, 'units': units, 'development_best': local_best})
    # Re-run the actual candidate callback, avoiding a second implementation of scoring.
    def score(split):
        return module.normalized_score([module.score_world(w, probe_answer(w['problem'], module.Campaign(w), selected))['mechanism'] for w in worlds[split]])
    assert abs(score('development') - best) < 1e-12
    return {'strategies': count, 'development_best': best,
            'selected_parameters': [v if np.isfinite(v) else 'infinity' for v in selected],
            'heldout_selected_once': score('heldout'), 'per_acquisition_family': family_best,
            'constant_mass_oracle_bounds': {split: constant_mass_bound(module, rows) for split, rows in worlds.items()},
            'observations': 'single-target excess, hardness, three-bin peak residual; all three targets and 1/3/full budget',
            'scope': 'finite builder grid with null/contact/q2/abstain; selected on development only, not exhaustive shortcut exclusion'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=300)
    args = parser.parse_args()
    if platform.system() != 'Linux':
        raise SystemExit('Run scoped evidence on Linux with Bubblewrap; local unit checks are separate.')
    report = {'schema_version': 1, 'source_provenance': source_provenance(ROOT), 'environment': {'python': sys.version, 'platform': platform.platform(), 'numpy': np.__version__, 'scipy': scipy.__version__}, 'evidence_scope': 'secure baselines, truth-blind witnesses and ablations; builder-only finite probes', 'model_calibration': 'not_run_no_configured_model_endpoint', 'tasks': []}
    passed = True
    for (task_id, (filename, entry, ablations)) in TASKS.items():
        spec = find_task(task_id, include_uncertified=True)
        reference = spec.task_dir / 'verification' / filename
        rows = {}
        for (name, path) in (('baseline', spec.initial_program_path), ('reference', reference)):
            started = time.monotonic()
            first = evaluate_candidate(spec, path, timeout_s=args.timeout)
            first_seconds = time.monotonic() - started
            started = time.monotonic()
            second = evaluate_candidate(spec, path, timeout_s=args.timeout)
            second_seconds = time.monotonic() - started
            ok = first == second and first.get('valid') == 1 and (not first.get('infrastructure_failure'))
            if name == 'baseline':
                ok = ok and first.get('combined_score') == 0
            passed = passed and ok
            rows[name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'deterministic': first == second, 'wall_seconds': [first_seconds, second_seconds], 'metrics': first, 'passed': ok}
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
                rows['ablations'][ablation] = {'candidate_sha256': hashlib.sha256(source.encode()).hexdigest(), 'metrics': metrics, 'delta_from_reference': rows['reference']['metrics']['combined_score'] - metrics['combined_score']}
                print(task_id, ablation, metrics.get('combined_score'), flush=True)
        rows['shortcut_probe'] = shortcut_probe(spec)
        rows['task'] = task_id
        reference_scores = rows['reference']['metrics']
        probe = rows['shortcut_probe']
        bounds_passed = all(probe['constant_mass_oracle_bounds'][split]['score'] <= .6 * reference_scores[split + '_mechanism_score'] for split in ('development', 'heldout'))
        shortcut_passed = all(value < .7 * reference_scores[split + '_mechanism_score'] and reference_scores[split + '_mechanism_score'] - value > .15 for split, value in [('development', probe['development_best']), ('heldout', probe['heldout_selected_once'])])
        probe['regression_passed'] = bounds_passed and shortcut_passed
        passed = passed and probe['regression_passed']
        report['tasks'].append(rows)
    finalize_report_trust(report, passed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return 0 if passed else 1
if __name__ == '__main__':
    raise SystemExit(main())
