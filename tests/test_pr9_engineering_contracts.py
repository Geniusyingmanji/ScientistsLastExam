"""Determinism and fail-closed contracts for the kept engineering candidate tasks.

The round-four DistributionNetworkTopology package this file originally pinned was
withdrawn on 2026-09-07 after an internal difficulty audit (superseded by the PR #51
level-3 rebuild); its pins were removed with it. The generic contracts below still
apply to every kept candidate.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK_ROOT = ROOT / "benchmarks" / "Engineering"
TASKS = {
    "WindEnergy/WakeAwareFarmCoDesign": "design_wind_farm",
}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _task_dir(task_id):
    return TASK_ROOT / task_id.split("/")[1]


class KeptCandidateContractTests(unittest.TestCase):
    def test_baselines_valid_zero_and_deterministic(self):
        for task_id, entrypoint in TASKS.items():
            with self.subTest(task_id=task_id):
                evaluator = _load(_task_dir(task_id) / "verification" / "evaluator.py",
                                  "kept_evaluator_" + entrypoint)
                baseline = _load(_task_dir(task_id) / "solution.py",
                                 "kept_baseline_" + entrypoint)
                first = evaluator.evaluate(getattr(baseline, entrypoint))
                second = evaluator.evaluate(getattr(baseline, entrypoint))
                self.assertEqual(first["valid"], 1.0, task_id)
                self.assertLessEqual(abs(first["combined_score"]), 0.01, task_id)
                self.assertEqual(json.dumps(first, sort_keys=True, default=str),
                                 json.dumps(second, sort_keys=True, default=str), task_id)

    def test_references_valid_and_above_floor(self):
        for task_id, entrypoint in TASKS.items():
            with self.subTest(task_id=task_id):
                evaluator = _load(_task_dir(task_id) / "verification" / "evaluator.py",
                                  "kept_evaluator_ref_" + entrypoint)
                reference = _load(_task_dir(task_id) / "verification" / "reference.py",
                                  "kept_reference_" + entrypoint)
                result = evaluator.evaluate(getattr(reference, entrypoint))
                self.assertEqual(result["valid"], 1.0, task_id)
                self.assertGreater(result["combined_score"], 0.05, task_id)

    def test_bad_candidates_score_invalid_without_crashing(self):
        def raises(*args, **kwargs):
            raise RuntimeError("candidate failure")

        for task_id, entrypoint in TASKS.items():
            with self.subTest(task_id=task_id):
                evaluator = _load(_task_dir(task_id) / "verification" / "evaluator.py",
                                  "kept_evaluator_bad_" + entrypoint)
                for candidate in (raises, lambda *a, **k: {}, lambda *a, **k: "junk"):
                    result = evaluator.evaluate(candidate)
                    self.assertEqual(result["valid"], 0.0, task_id)
                    self.assertEqual(result["combined_score"], 0.0, task_id)


if __name__ == "__main__":
    unittest.main()
