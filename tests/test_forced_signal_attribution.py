"""Discovery-contract pins for ForcedSignalAttribution.

The public score is mechanism, normalised so that declining every world is exactly zero. A world
whose model is untrustworthy (too quiet, or pointing the wrong way) is the unsupported case:
declining it is correct, declining everything is not; an unforced world with a trustworthy model
is determinable and "not detected" is its answer. This file pins the normalisation and that the
delivered baseline sits below the sealed reference, which is the headroom the card claims.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/EarthScience/ForcedSignalAttribution"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ForcedSignalAttributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "attribution_oracle")
        cls.baseline = _load(TASK / "solution.py", "attribution_baseline")
        cls.reference = _load(TASK / "verification/reference_fingerprinting.py", "attribution_reference")

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(lambda _problem, _control: {"abstain": True})
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_detecting_everywhere_books_false_discoveries(self):
        always = lambda _p, _c: {"detected": True, "scaling_factor": 1.0, "interval": [0.5, 1.5], "abstain": False}
        metrics = self.evaluator.evaluate(always)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["development_false_discovery_rate"], 1.0)
        self.assertEqual(metrics["development_unforced_false_detection_rate"], 1.0)

    def test_the_trend_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.attribute)
        reference = self.evaluator.evaluate(self.reference.attribute)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertGreater(reference["combined_score"], 0.5)
        self.assertLess(reference["combined_score"], 1.0)
        self.assertEqual(reference["development_unforced_false_detection_rate"], 0.0)
        self.assertEqual(reference["development_correct_refusal_rate"], 1.0)
        self.assertEqual(baseline["development_correct_refusal_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
