"""Discovery-contract pins for PTAHellingsDowns.

The public score is mechanism, normalised so that declining every world is exactly zero.
Monopole, dipole and uncorrelated worlds are unsupported. A mean-correlation baseline that
never declines therefore scores zero even when it names Hellings-Downs on a true array.
"""
from __future__ import annotations

import importlib.util
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Physics/PTAHellingsDowns"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PTAHellingsDownsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "pta_oracle")
        cls.baseline = _load(TASK / "solution.py", "pta_baseline")
        cls.reference = _load(
            TASK / "verification/reference_kernel.py", "pta_reference"
        )

    def test_hellings_downs_orf_matches_the_1983_overlap_reduction(self):
        """Γ = 1/2 - x/4 + (3/2) x ln x, x=(1-cos θ)/2; HD(π)=1/4, HD(π/2)≈-0.145."""
        hd = self.evaluator.hellings_downs_orf
        self.assertAlmostEqual(float(hd(math.pi)), 0.25, places=6)
        x = 0.5
        expected = 0.5 - 0.25 * x + 1.5 * x * math.log(x)
        self.assertAlmostEqual(float(hd(math.pi / 2.0)), expected, places=6)

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _bootstrap: {"abstain": True}
        )
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_the_always_hd_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.interpret_correlations)
        reference = self.evaluator.evaluate(self.reference.interpret_correlations)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["development_false_discovery_rate"], 1.0)
        self.assertEqual(reference["development_false_discovery_rate"], 0.0)
        self.assertEqual(reference["development_signal_recovery_rate"], 1.0)

    def test_a_monopole_world_is_published_by_the_mean_correlation_alone(self):
        baseline = self.evaluator.evaluate(self.baseline.interpret_correlations)
        monopoles = [row for row in baseline["per_instance"]
                     if row["kind"] == "monopole" and row["split"] == "development"]
        self.assertTrue(monopoles)
        self.assertTrue(all(row["false_discovery"] for row in monopoles))

    def test_alternative_kernel_label_is_not_a_correct_refusal(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _bootstrap: {
                "kernel": "uncorrelated",
                "confidence": 0.0,
                "abstain": False,
            }
        )
        unsupported = [
            row for row in metrics["per_instance"]
            if row["kind"] != "hellings_downs"
        ]
        self.assertTrue(unsupported)
        self.assertTrue(all(row["mechanism_score"] == 0.0 for row in unsupported))
        self.assertTrue(all(not row["correct_refusal"] for row in unsupported))

    def test_this_is_not_a_look_elsewhere_bump_hunt(self):
        from sle.registry import find_task
        spec = find_task("Gravitation/PTAHellingsDowns", include_uncertified=True)
        other = find_task("ParticlePhysics/LookElsewhereAnomaly", include_uncertified=True)
        self.assertEqual(spec.entrypoint, "interpret_correlations")
        self.assertNotEqual(spec.entrypoint, other.entrypoint)
        self.assertNotEqual(spec.task_dir, other.task_dir)
        self.assertEqual(spec.domain, "Gravitation")


if __name__ == "__main__":
    unittest.main()
