"""Recompute FWI method/shot comparisons; not frontier-model calibration.

python .research/pr20_fwi_diagnostics.py --output /tmp/fwi-methods.json
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import time
from pathlib import Path

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'benchmarks/EarthScience/ActiveFullWaveformInversion'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--methods', nargs='+', default=['baseline', 'background', 'constant_lens', 'travel_time', 'spatial_grid', 'spatial_refined', 'greedy_two', 'greedy_three', 'one_shot', 'three_shots'])
    parser.add_argument('--level', type=int, default=1, choices=[1, 2, 3])
    args = parser.parse_args()
    oracle = load(TASK / 'verification/evaluator.py', 'fwi_oracle')
    oracle.DIFFICULTY = args.level
    reference = load(TASK / 'verification/reference_solver.py', 'fwi_reference')
    baseline = load(TASK / 'solution.py', 'fwi_baseline')
    probes = load(ROOT / 'tests/test_pr9_earth_hardening.py', 'fwi_probes')
    spatial = load(ROOT / '.research/pr20_fwi_spatial_probe.py', 'fwi_spatial_probe')
    refined = load(ROOT / '.research/pr20_fwi_spatial_probe.py', 'fwi_refined_probe')
    refined.REFINE = True
    refined.THRESHOLD = .20
    greedy_two = load(ROOT / '.research/pr20_fwi_spatial_probe.py', 'fwi_two_lenses')
    greedy_two.LENSES = 2
    greedy_two.THRESHOLD = .20
    greedy_three = load(ROOT / '.research/pr20_fwi_spatial_probe.py', 'fwi_three_lenses')
    greedy_three.LENSES = 3
    greedy_three.THRESHOLD = .20

    def one_shot(*inputs):
        # Same fitting stages/tolerances and same first shot as the three-shot run.
        return reference.invert_velocity_model(*inputs[:-1], min(inputs[-1], 1))

    candidates = {'baseline': baseline.invert_velocity_model,
                  'background': probes._fwi_zero_inversion,
                  'constant_lens': probes._fwi_constant_lens,
                  'travel_time': probes._fwi_travel_time_only,
                  'spatial_grid': spatial.invert_velocity_model,
                  'spatial_refined': refined.invert_velocity_model,
                  'greedy_two': greedy_two.invert_velocity_model,
                  'greedy_three': greedy_three.invert_velocity_model,
                  'one_shot': one_shot,
                  'three_shots': reference.invert_velocity_model}
    report = {'scope': 'method_diagnostics_not_model_calibration',
              'platform': platform.platform(), 'numpy': np.__version__, 'scipy': scipy.__version__,
              'difficulty': args.level,
              'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in [TASK / 'verification/evaluator.py', TASK / 'verification/reference_solver.py', ROOT / 'tests/test_pr9_earth_hardening.py', ROOT / '.research/pr20_fwi_spatial_probe.py']},
              'results': {}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for name in args.methods:
        start = time.monotonic()
        metrics = oracle.evaluate(candidates[name])
        metrics['wall_seconds'] = time.monotonic() - start
        report['results'][name] = metrics
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(name, metrics['combined_score'], metrics['robustness_score'],
              metrics['development_false_discovery_rate'], metrics['wall_seconds'], flush=True)


if __name__ == '__main__':
    main()
