"""Invariants for DiscreteOptimization/MiplibPrimalIncumbent."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Engineering" / "MiplibPrimalIncumbent"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load("mip_evaluator", TASK / "verification" / "evaluator.py")
BASELINE = _load("mip_baseline", TASK / "solution.py")


class MiplibPrimalTests(unittest.TestCase):
    def test_vendored_hashes_and_dimensions_match(self):
        for row in EVALUATOR.INSTANCES:
            model = EVALUATOR._load_model(row)
            self.assertEqual(len(model["columns"]), row["n_variables"], row["name"])
            self.assertEqual(len(model["rhs"]), row["n_constraints"], row["name"])

    def test_baseline_is_feasible_and_scores_exactly_zero(self):
        result = EVALUATOR.evaluate(BASELINE.improve_primal)
        self.assertEqual(result["valid"], 1.0)
        self.assertEqual(result["feasibility_rate"], 1.0)
        self.assertEqual(result["combined_score"], 0.0)

    def test_infeasible_origin_on_gen_ip021_scores_zero_there(self):
        def candidate(problem):
            return [0] * problem["n_variables"]

        result = EVALUATOR.evaluate(candidate)
        by_name = {row["name"]: row for row in result["per_instance"]}
        self.assertTrue(by_name["gen-ip002"]["valid"])
        self.assertFalse(by_name["gen-ip021"]["valid"])
        self.assertFalse(by_name["gen-ip054"]["valid"])

    def test_malformed_submissions_score_zero_without_raising(self):
        cases = {
            "none": lambda problem: None,
            "empty": lambda problem: [],
            "raises": lambda problem: (_ for _ in ()).throw(RuntimeError("boom")),
            "too_short": lambda problem: [0],
            "too_long": lambda problem: [0] * (problem["n_variables"] + 1),
            "floats": lambda problem: [0.0] * problem["n_variables"],
            "booleans": lambda problem: [False] * problem["n_variables"],
            "dict": lambda problem: {0: 1},
            "string": lambda problem: "0" * problem["n_variables"],
            "mixed": lambda problem: [0, 1.2] + [0] * (problem["n_variables"] - 2),
            "none_entry": lambda problem: [None] * problem["n_variables"],
            "nested": lambda problem: [[0]] * problem["n_variables"],
        }
        self.assertGreaterEqual(len(cases), 10)
        for name, candidate in cases.items():
            with self.subTest(candidate=name):
                result = EVALUATOR.evaluate(candidate)
                self.assertEqual(result["combined_score"], 0.0)
                self.assertEqual(result["valid"], 0.0)


if __name__ == "__main__":
    unittest.main()
