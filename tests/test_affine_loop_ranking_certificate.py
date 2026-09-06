"""Certificate pins for AffineLoopRankingCertificate."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/ComputerScience/AffineLoopRankingCertificate"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AffineLoopRankingCertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "ranking_oracle")
        cls.baseline = _load(TASK / "solution.py", "ranking_baseline")
        cls.reference = _load(
            TASK / "verification/reference_ranking.py", "ranking_reference"
        )

    def _cut_x(self):
        instance = self.evaluator.INSTANCES[0]
        dimension = instance["dimension"]
        guards = self.evaluator._parse_guards(instance["guards"], dimension)
        update_a = self.evaluator._matrix(instance["A"], "A", dimension, dimension)
        update_b = self.evaluator._vector(instance["b"], "b", dimension)
        return guards, update_a, update_b

    def test_the_fast_coordinate_ranks_harder_than_the_slow_one(self):
        guards, update_a, update_b = self._cut_x()
        fast = [Fraction(1), Fraction(0)]
        slow = [Fraction(0), Fraction(1)]
        lam_fast = [Fraction(1), Fraction(0)]
        lam_slow = [Fraction(0), Fraction(1)]
        zeros = [Fraction(0), Fraction(0)]
        holds, _ = self.evaluator.certificate_holds(
            guards, update_a, update_b, fast, Fraction(0), Fraction(2), lam_fast, zeros
        )
        self.assertTrue(holds)
        fails, _ = self.evaluator.certificate_holds(
            guards, update_a, update_b, slow, Fraction(0), Fraction(2), lam_slow, zeros
        )
        self.assertFalse(fails)
        slow_ok, _ = self.evaluator.certificate_holds(
            guards, update_a, update_b, slow, Fraction(0), Fraction(1), lam_slow, zeros
        )
        self.assertTrue(slow_ok)

    def test_floats_are_rejected_and_score_zero(self):
        def floats(instance):
            dimension = int(instance["dimension"])
            n_guards = len(instance["guards"])
            return {
                "r": [1.0] + [0.0] * (dimension - 1),
                "s": 0.0,
                "delta": 0.0001,
                "nonneg_lambdas": [1.0] + [0.0] * (n_guards - 1),
                "decrease_lambdas": [0.0] * n_guards,
            }

        metrics = self.evaluator.evaluate(floats)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_e1_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.build_ranking)
        reference = self.evaluator.evaluate(self.reference.build_ranking)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertGreater(reference["combined_score"], 0.5)

    def test_malformed_submissions_score_zero_without_raising(self):
        metrics = self.evaluator.evaluate(lambda *_args: "not a mapping")
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_this_is_not_a_lyapunov_ode_or_a_distance_graph(self):
        from sle.registry import find_task
        spec = find_task(
            "ScientificComputing/AffineLoopRankingCertificate", include_uncertified=True
        )
        graph = find_task("Algorithm/GraphFromDistances", include_uncertified=True)
        self.assertEqual(spec.entrypoint, "build_ranking")
        self.assertNotEqual(spec.task_id, "ControlTheory/LyapunovDecayCertificate")
        self.assertNotEqual(spec.task_dir, graph.task_dir)


if __name__ == "__main__":
    unittest.main()
