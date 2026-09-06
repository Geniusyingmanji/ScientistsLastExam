"""Discovery-contract pins for UltrasonicDefectSpecies."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Engineering/UltrasonicDefectSpecies"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UltrasonicDefectSpeciesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "ultrasonic_oracle")
        cls.baseline = _load(TASK / "solution.py", "ultrasonic_baseline")
        cls.reference = _load(
            TASK / "verification/reference_species.py", "ultrasonic_reference"
        )

    def test_crack_inverts_phase_and_a_pore_does_not(self):
        crack = {"kind": "crack", "depth_mm": 11.0}
        pore = {"kind": "pore", "depth_mm": 18.0}
        t_crack = self.evaluator._arrival(11.0)
        t_pore = self.evaluator._arrival(18.0)
        self.assertLess(self.evaluator.true_trace(crack, t_crack), -0.8)
        self.assertGreater(self.evaluator.true_trace(pore, t_pore), 0.3)
        clean = self.evaluator.true_trace({"kind": "none"}, t_crack)
        self.assertEqual(clean, 0.0)

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _measure: {"abstain": True}
        )
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_the_clean_scan_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.identify_species)
        reference = self.evaluator.evaluate(self.reference.identify_species)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["development_false_discovery_rate"], 1.0)
        self.assertEqual(reference["development_false_discovery_rate"], 0.0)
        self.assertGreater(reference["development_signal_recovery_rate"], 0.99)
        self.assertGreater(reference["development_correct_refusal_rate"], 0.99)

    def test_malformed_submissions_score_zero_without_raising(self):
        metrics = self.evaluator.evaluate(lambda *_args: {"abstain": True, "confidence": 1.1})
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_this_is_not_modal_damage_or_a_quartz_microbalance(self):
        from sle.registry import find_task
        spec = find_task("Sensors/UltrasonicDefectSpecies", include_uncertified=True)
        modal = find_task("StructuralEngineering/ModalDamageAttribution", include_uncertified=True)
        qcm = find_task("Sensors/QuartzCrystalMicrobalanceLab", include_uncertified=True)
        self.assertEqual(spec.entrypoint, "identify_species")
        self.assertNotEqual(spec.task_dir, modal.task_dir)
        self.assertNotEqual(spec.task_dir, qcm.task_dir)


if __name__ == "__main__":
    unittest.main()
