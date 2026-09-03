"""Discovery-contract pins for SurvivorshipConfoundedDesign.

The public score is mechanism, normalised so that declining every world is exactly zero.
Collider and blank worlds are unsupported. OLS on returned survivors therefore scores
zero even when it names the right sign on a true T→Y edge, because the collider worlds
are published as effects.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/ComputerScience/SurvivorshipConfoundedDesign"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SurvivorshipConfoundedDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "surv_oracle")
        cls.baseline = _load(TASK / "solution.py", "surv_baseline")
        cls.reference = _load(
            TASK / "verification/reference_design.py", "surv_reference"
        )

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _obs, _int: {"abstain": True}
        )
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_the_survivor_ols_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.recover_effect)
        reference = self.evaluator.evaluate(self.reference.recover_effect)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["development_false_discovery_rate"], 1.0)
        self.assertEqual(reference["development_false_discovery_rate"], 0.0)
        self.assertEqual(reference["development_signal_recovery_rate"], 1.0)

    def test_a_collider_world_is_published_by_survivor_ols(self):
        baseline = self.evaluator.evaluate(self.baseline.recover_effect)
        colliders = [row for row in baseline["per_instance"]
                     if row["kind"] == "collider" and row["split"] == "development"]
        self.assertTrue(colliders)
        self.assertTrue(all(row["false_discovery"] for row in colliders))

    def test_explicit_no_effect_is_not_a_correct_refusal(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _observe, _intervene: {
                "has_treatment_effect": False,
                "confidence": 0.0,
                "abstain": False,
            }
        )
        unsupported = [
            row for row in metrics["per_instance"]
            if row["kind"] in {"collider", "blank"}
        ]
        self.assertTrue(unsupported)
        self.assertTrue(all(row["mechanism_score"] == 0.0 for row in unsupported))
        self.assertTrue(all(not row["correct_refusal"] for row in unsupported))

    def test_effect_sign_must_be_finite(self):
        for invalid_sign in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(effect_sign=invalid_sign):
                metrics = self.evaluator.evaluate(
                    lambda _problem, _observe, _intervene, value=invalid_sign: {
                        "has_treatment_effect": True,
                        "effect_sign": value,
                        "confidence": 0.0,
                        "abstain": False,
                    }
                )
                self.assertEqual(metrics["valid"], 0.0, metrics)
                self.assertTrue(
                    all(not row["valid"] for row in metrics["per_instance"]),
                    metrics,
                )

    def test_this_is_not_interventional_scm(self):
        from sle.registry import find_task
        spec = find_task("CausalDiscovery/SurvivorshipConfoundedDesign", include_uncertified=True)
        other = find_task("CausalDiscovery/InterventionalSCM", include_uncertified=True)
        self.assertEqual(spec.entrypoint, "recover_effect")
        self.assertNotEqual(spec.entrypoint, other.entrypoint)
        self.assertNotEqual(spec.task_dir, other.task_dir)


if __name__ == "__main__":
    unittest.main()
