"""Discovery-contract pins for HiddenCouplingNetwork.

The public score is mechanism, normalised so that declining every network is exactly zero.
A network with unmeasured units is the unsupported case: refusing it is correct, refusing
everything is not; a network with no couplings is determinable and "no edges" is its answer.
This file pins the normalisation, that the empty graph is not a free ride, and that the delivered
baseline sits below the sealed reference, which is the headroom the card claims.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Physics/HiddenCouplingNetwork"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HiddenCouplingNetworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "hidden_coupling_oracle")
        cls.baseline = _load(TASK / "solution.py", "hidden_coupling_baseline")
        cls.reference = _load(
            TASK / "verification/reference_sparse_regression.py", "hidden_coupling_reference"
        )

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(lambda _problem, _lab: {"abstain": True})
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_the_empty_graph_everywhere_scores_zero_and_books_false_discoveries(self):
        metrics = self.evaluator.evaluate(lambda _problem, _lab: {"edges": [], "abstain": False})
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_false_discovery_rate"], 1.0)
        self.assertEqual(metrics["development_null_false_discovery_rate"], 0.0)

    def test_the_budget_is_below_the_unit_count(self):
        self.assertLess(self.evaluator.DEVELOPMENT_BUDGET, self.evaluator.DEVELOPMENT_UNITS)
        self.assertLess(self.evaluator.HELDOUT_BUDGET, self.evaluator.HELDOUT_UNITS)

    def test_the_dense_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.discover_couplings)
        reference = self.evaluator.evaluate(self.reference.discover_couplings)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertGreater(reference["combined_score"], 0.5)
        self.assertLess(reference["combined_score"], 1.0)
        self.assertEqual(reference["development_false_discovery_rate"], 0.0)
        self.assertEqual(baseline["development_false_discovery_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
