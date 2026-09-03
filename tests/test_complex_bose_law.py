"""Discovery-contract pins for ComplexBoseLaw.

The public score is mechanism, normalised so that declining every world is exactly zero.
Fermi and T-independent blanks are unsupported. A textbook (α, β)=(1, 1) Bose claim
therefore scores zero even when occupancy is actually Bose-like, because those worlds are
published as discoveries on Fermi and blanks too.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Physics/ComplexBoseLaw"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ComplexBoseLawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "bose_oracle")
        cls.baseline = _load(TASK / "solution.py", "bose_baseline")
        cls.reference = _load(
            TASK / "verification/reference_fit.py", "bose_reference"
        )

    def test_in_family_occupation_keeps_the_bose_minus_sign(self):
        n_bose = self.evaluator.occupation_number("bose", 1.0, 1.2, 1.0, 1.5, 2.0)
        n_fermi = self.evaluator.occupation_number("fermi", 1.0, 1.2, 1.0, 1.5, 2.0)
        self.assertGreater(n_bose, n_fermi)
        self.assertLess(n_fermi, 1.0)
        alphas = {spec["alpha"] for spec in self.evaluator.DEVELOPMENT_WORLDS
                  if spec["kind"] == "bose"}
        self.assertGreater(len(alphas), 1)
        self.assertNotIn(1.0, alphas)

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _measure: {"abstain": True}
        )
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_the_textbook_bose_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.interpret_cavity)
        reference = self.evaluator.evaluate(self.reference.interpret_cavity)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["development_false_discovery_rate"], 1.0)
        self.assertEqual(reference["development_false_discovery_rate"], 0.0)
        self.assertGreater(reference["development_signal_recovery_rate"], 0.8)

    def test_a_fermi_world_is_published_by_the_textbook_bose_claim(self):
        baseline = self.evaluator.evaluate(self.baseline.interpret_cavity)
        fermi = [row for row in baseline["per_instance"]
                 if row["kind"] == "fermi" and row["split"] == "development"]
        self.assertTrue(fermi)
        self.assertTrue(all(row["false_discovery"] for row in fermi))

    def test_fermi_label_is_not_a_correct_refusal(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _measure: {
                "family": "fermi",
                "C": 1.0,
                "alpha": 1.0,
                "beta": 1.0,
                "confidence": 0.0,
                "abstain": False,
            }
        )
        unsupported = [
            row for row in metrics["per_instance"]
            if row["kind"] != "bose"
        ]
        self.assertTrue(unsupported)
        self.assertTrue(all(row["mechanism_score"] == 0.0 for row in unsupported))
        self.assertTrue(all(not row["correct_refusal"] for row in unsupported))

    def test_this_is_not_an_active_law_ode_or_amoc_fold(self):
        from sle.registry import find_task
        spec = find_task("Physics/ComplexBoseLaw", include_uncertified=True)
        ode = find_task("DynamicalSystems/ActiveLawDiscovery", include_uncertified=True)
        amoc = find_task("Oceanography/AMOCTippingRefusal", include_uncertified=True)
        self.assertEqual(spec.entrypoint, "interpret_cavity")
        self.assertNotEqual(spec.entrypoint, ode.entrypoint)
        self.assertNotEqual(spec.entrypoint, amoc.entrypoint)
        self.assertNotEqual(spec.task_dir, ode.task_dir)


if __name__ == "__main__":
    unittest.main()
