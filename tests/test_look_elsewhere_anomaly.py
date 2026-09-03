"""Discovery-contract pins for LookElsewhereAnomaly.

The public score is mechanism, normalised so that declining every world is exactly zero.
Fluke, sculpted and blank worlds are the unsupported cases. A local-z baseline that
never declines therefore scores zero even when it names the right mass on a true
resonance, because the look-elsewhere worlds are published as discoveries.
"""
from __future__ import annotations

import importlib.util
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Physics/LookElsewhereAnomaly"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LookElsewhereAnomalyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "look_elsewhere_oracle")
        cls.baseline = _load(TASK / "solution.py", "look_elsewhere_baseline")
        cls.reference = _load(
            TASK / "verification/reference_scan.py", "look_elsewhere_reference"
        )

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _toys: {"abstain": True}
        )
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_mechanism_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_the_local_z_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.interpret_spectrum)
        reference = self.evaluator.evaluate(self.reference.interpret_spectrum)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertGreater(reference["combined_score"], 0.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["development_false_discovery_rate"], 1.0)
        self.assertEqual(reference["development_false_discovery_rate"], 0.0)
        self.assertEqual(reference["development_signal_recovery_rate"], 1.0)

    def test_a_fluke_world_is_published_by_the_local_scan_alone(self):
        baseline = self.evaluator.evaluate(self.baseline.interpret_spectrum)
        flukes = [row for row in baseline["per_instance"]
                  if row["kind"] == "fluke" and row["split"] == "development"]
        self.assertTrue(flukes)
        self.assertTrue(all(row["false_discovery"] for row in flukes))

    def test_explicit_non_discovery_is_not_a_correct_refusal(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _toys: {
                "discovery": False,
                "confidence": 0.0,
                "abstain": False,
            }
        )
        unsupported = [
            row for row in metrics["per_instance"]
            if row["kind"] in {"fluke", "sculpted", "blank"}
        ]
        self.assertTrue(unsupported)
        self.assertTrue(all(row["mechanism_score"] == 0.0 for row in unsupported))
        self.assertTrue(all(not row["correct_refusal"] for row in unsupported))

    def test_toy_count_must_be_a_non_boolean_integer(self):
        for invalid_count in (True, 1.5):
            with self.subTest(n=invalid_count):
                def candidate(_problem, toys, n=invalid_count):
                    toys(n)
                    return {"abstain": True, "confidence": 0.0}

                metrics = self.evaluator.evaluate(candidate)
                self.assertEqual(metrics["valid"], 0.0, metrics)
                self.assertTrue(
                    all(not row["valid"] for row in metrics["per_instance"]),
                    metrics,
                )

    def test_frozen_flukes_are_local_five_sigma_but_not_global_five_sigma(self):
        for spec in self.evaluator.DEVELOPMENT_WORLDS + self.evaluator.HELDOUT_WORLDS:
            if spec["kind"] != "fluke":
                continue
            counts = self.evaluator._world(spec)["counts"]
            local_z = max(
                (float(count) - self.evaluator.BKG) / math.sqrt(self.evaluator.BKG)
                for count in counts
            )
            local_p = self.reference._p_one_sided(local_z)
            self.assertGreaterEqual(local_z, 5.0, spec)
            self.assertGreater(
                self.evaluator.N_BINS * local_p,
                self.evaluator.FIVE_SIGMA_P,
                spec,
            )

    def test_frozen_signals_remain_global_five_sigma(self):
        for spec in self.evaluator.DEVELOPMENT_WORLDS + self.evaluator.HELDOUT_WORLDS:
            if spec["kind"] != "signal":
                continue
            counts = self.evaluator._world(spec)["counts"]
            local_z = max(
                (float(count) - self.evaluator.BKG) / math.sqrt(self.evaluator.BKG)
                for count in counts
            )
            self.assertLess(
                self.evaluator.N_BINS * self.reference._p_one_sided(local_z),
                self.evaluator.FIVE_SIGMA_P,
                spec,
            )

    def test_this_is_not_discrepant_measurements(self):
        """The public contract is a histogram plus toys, not a table of group values."""
        from sle.registry import find_task
        spec = find_task("ParticlePhysics/LookElsewhereAnomaly", include_uncertified=True)
        other = find_task("ParticlePhysics/DiscrepantMeasurements", include_uncertified=True)
        self.assertEqual(spec.entrypoint, "interpret_spectrum")
        self.assertNotEqual(spec.entrypoint, other.entrypoint)
        self.assertNotEqual(spec.task_dir, other.task_dir)


if __name__ == "__main__":
    unittest.main()
