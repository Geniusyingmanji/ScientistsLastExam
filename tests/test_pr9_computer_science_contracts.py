"""Pinned invariants for the 2026-09-05 round-four candidate tasks.

Each class pins the construction errors recorded in the task's known_best.md and
the repo-wide baseline/reference/bad-candidate contract. Tests load evaluators
directly; sandbox-dependent behaviour is out of scope here.
"""
from __future__ import annotations
import importlib.util
import json
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
TASKS = {'Algorithm/ScalingLawIdentification': ('benchmarks/ComputerScience/ScalingLawIdentification', 'identify_scaling_law')}

def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

class RoundFourPackageTests(unittest.TestCase):

    def test_baselines_valid_zero_and_deterministic(self):
        for task_id, (directory, entrypoint) in TASKS.items():
            evaluator = _load(ROOT / directory / 'verification' / 'evaluator.py', 'r4_evaluator_' + entrypoint)
            baseline = _load(ROOT / directory / 'solution.py', 'r4_baseline_' + entrypoint)
            first = evaluator.evaluate(getattr(baseline, entrypoint))
            second = evaluator.evaluate(getattr(baseline, entrypoint))
            self.assertEqual(first['valid'], 1.0, task_id)
            self.assertLessEqual(abs(first['combined_score']), 0.01, task_id)
            self.assertEqual(json.dumps(first, sort_keys=True, default=str), json.dumps(second, sort_keys=True, default=str), task_id)

    def test_references_valid_and_above_floor(self):
        for task_id, (directory, entrypoint) in TASKS.items():
            evaluator = _load(ROOT / directory / 'verification' / 'evaluator.py', 'r4_evaluator_ref_' + entrypoint)
            reference = _load(ROOT / directory / 'verification' / 'reference_solver.py', 'r4_reference_' + entrypoint)
            result = evaluator.evaluate(getattr(reference, entrypoint))
            self.assertEqual(result['valid'], 1.0, task_id)
            self.assertGreater(result['combined_score'], 0.05, task_id)

    def test_bad_candidates_score_invalid_without_crashing(self):

        def raises(*args, **kwargs):
            raise RuntimeError('candidate failure')
        for task_id, (directory, entrypoint) in TASKS.items():
            evaluator = _load(ROOT / directory / 'verification' / 'evaluator.py', 'r4_evaluator_bad_' + entrypoint)
            for candidate in (raises, lambda *a, **k: {}, lambda *a, **k: 'junk'):
                result = evaluator.evaluate(candidate)
                self.assertEqual(result['valid'], 0.0, task_id)
                self.assertEqual(result['combined_score'], 0.0, task_id)

class ScalingLawPins(unittest.TestCase):

    def test_branch_world_is_deterministic_in_size(self):
        ev = _load('benchmarks/ComputerScience/ScalingLawIdentification/verification/evaluator.py', 'r4_scale')
        world = ev._world((30041, 'branch', 'branch'))
        self.assertEqual(ev._true_runtime(world, 334), ev._true_runtime(world, 334))
        ratio = max(ev._true_runtime(world, 331) / ev._true_runtime(world, 332), ev._true_runtime(world, 332) / ev._true_runtime(world, 331))
        self.assertGreater(ratio, 25.0)

    def test_tightened_statistics_beat_lazy_ladders(self):
        ev = _load('benchmarks/ComputerScience/ScalingLawIdentification/verification/evaluator.py', 'r4_scale')
        ref = _load(ROOT / 'benchmarks/ComputerScience/ScalingLawIdentification/verification' / 'reference_solver.py', 'r4_scale_ref')
        reference = ev.evaluate(ref.identify_scaling_law)
        self.assertLess(reference['combined_score'], 0.97)
        self.assertGreater(reference['combined_score'], 0.8)
        self.assertEqual(reference['development_correct_refusal_rate'], 1.0)
        self.assertEqual(reference['development_false_discovery_rate'], 0.0)
        self.assertGreater(reference['robustness_score'], 0.85)

    def test_jitter_worlds_carry_a_lawful_family(self):
        ev = _load('benchmarks/ComputerScience/ScalingLawIdentification/verification/evaluator.py', 'r4_scale')
        for spec in ev._BASE_DEVELOPMENT_SPECS + ev.HELDOUT_SPECS:
            world = ev._world(spec)
            if world['kind'] != 'branch':
                self.assertIn(world['family'], ev.CLASSES)
if __name__ == '__main__':
    unittest.main()
