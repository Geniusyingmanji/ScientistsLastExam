"""Discovery-contract pins for GlenFlowLawDiscovery."""
from __future__ import annotations

import importlib.util
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/EarthScience/GlenFlowLawDiscovery"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GlenFlowLawDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "glen_oracle")
        cls.baseline = _load(TASK / "solution.py", "glen_baseline")
        cls.reference = _load(
            TASK / "verification/reference_flow.py", "glen_reference"
        )

    def test_glen_is_cubic_and_sliding_curves_the_log_log_slope(self):
        glen = {"kind": "glen", "A": 2.0e-7}
        newtonian = {"kind": "newtonian", "A": 0.012}
        sliding = {"kind": "sliding", "A": 1.0e-5, "C": 0.05}
        taus = (20.0, 80.0, 200.0)
        def slope(spec, left, right):
            y_left = math.log(self.evaluator.true_speed(spec, left))
            y_right = math.log(self.evaluator.true_speed(spec, right))
            return (y_right - y_left) / (math.log(right) - math.log(left))
        self.assertAlmostEqual(slope(glen, *taus[:2]), 3.0, places=6)
        self.assertAlmostEqual(slope(newtonian, *taus[:2]), 1.0, places=6)
        self.assertGreater(
            abs(slope(sliding, taus[1], taus[2]) - slope(sliding, taus[0], taus[1])),
            0.4,
        )

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _measure: {"abstain": True}
        )
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_the_newtonian_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.identify_flow_law)
        reference = self.evaluator.evaluate(self.reference.identify_flow_law)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["development_false_discovery_rate"], 1.0)
        self.assertGreater(reference["combined_score"], 0.3)
        self.assertLess(reference["combined_score"], 0.8)
        self.assertGreater(reference["development_signal_recovery_rate"], 0.5)
        self.assertGreater(reference["development_false_discovery_rate"], 0.0)
        self.assertLess(reference["development_correct_refusal_rate"], 1.0)

    def test_malformed_submissions_score_zero_without_raising(self):
        metrics = self.evaluator.evaluate(lambda *_args: {"abstain": True, "confidence": 1.1})
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_this_is_not_an_amoc_fold_or_a_wall_closure(self):
        from sle.registry import find_task
        spec = find_task("Glaciology/GlenFlowLawDiscovery", include_uncertified=True)
        amoc = find_task("Oceanography/AMOCTippingRefusal", include_uncertified=True)
        wall = find_task("Turbulence/WallClosureDiscovery", include_uncertified=True)
        self.assertEqual(spec.entrypoint, "identify_flow_law")
        self.assertNotEqual(spec.task_dir, amoc.task_dir)
        self.assertNotEqual(spec.task_dir, wall.task_dir)


if __name__ == "__main__":
    unittest.main()
