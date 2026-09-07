from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Physics" / "MicrolensingEventCharacterization"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load("test_microlensing_evaluator", TASK / "verification" / "evaluator.py")
REFERENCE = _load("test_microlensing_reference", TASK / "verification" / "reference_solver.py")
BASELINE = _load("test_microlensing_baseline", TASK / "solution.py")


class MicrolensingEventCharacterizationTests(unittest.TestCase):
    def test_baseline_is_valid_and_zero(self):
        metrics = EVALUATOR.evaluate(BASELINE.infer_microlensing)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_reference_is_key_deterministic(self):
        first = EVALUATOR.evaluate(REFERENCE.infer_microlensing)
        second = EVALUATOR.evaluate(REFERENCE.infer_microlensing)
        self.assertEqual(first, second)
        self.assertGreater(first["combined_score"], 0.15)

    def test_blanket_abstention_is_zero(self):
        def blanket(problem, observe):
            ids = [observe(float(t), "r")["query_id"] for t in problem["candidate_times"][:6]]
            return {"abstain": True, "confidence": 0.5, "evidence_query_ids": ids}
        self.assertEqual(EVALUATOR.evaluate(blanket)["combined_score"], 0.0)

    def test_duplicate_query_fails_closed(self):
        def duplicate(problem, observe):
            observe(float(problem["candidate_times"][0]), "r")
            observe(float(problem["candidate_times"][0]), "r")
        metrics = EVALUATOR.evaluate(duplicate)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_world_families_are_present(self):
        self.assertEqual({w["kind"] for w in EVALUATOR.DEVELOPMENT_WORLDS},
                         {"point", "binary", "variable", "ambiguous"})


if __name__ == "__main__":
    unittest.main()
