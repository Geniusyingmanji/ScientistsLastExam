"""Discovery-contract pins for DiblockMorphologyDiscovery."""
from __future__ import annotations

import importlib.util
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Chemistry/DiblockMorphologyDiscovery"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DiblockMorphologyDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "diblock_oracle")
        cls.baseline = _load(TASK / "solution.py", "diblock_baseline")
        cls.reference = _load(
            TASK / "verification/reference_morphology.py", "diblock_reference"
        )

    def test_hex_and_lamella_have_distinct_second_peaks(self):
        self.assertAlmostEqual(self.evaluator.RATIOS["hex"][1], math.sqrt(3.0))
        self.assertAlmostEqual(self.evaluator.RATIOS["lamella"][1], 2.0)
        self.assertNotAlmostEqual(
            self.evaluator.RATIOS["bcc"][1], self.evaluator.RATIOS["gyroid"][1]
        )

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _measure: {"abstain": True}
        )
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_the_lamella_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.identify_morphology)
        reference = self.evaluator.evaluate(self.reference.identify_morphology)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["development_false_discovery_rate"], 1.0)
        self.assertEqual(reference["development_false_discovery_rate"], 0.0)
        self.assertGreater(reference["development_signal_recovery_rate"], 0.99)
        self.assertGreater(reference["development_correct_refusal_rate"], 0.99)

    def test_malformed_submissions_score_zero_without_raising(self):
        metrics = self.evaluator.evaluate(lambda *_args: "not a mapping")
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_this_is_not_a_binary_phase_diagram_or_crowded_spectrum(self):
        from sle.registry import find_task
        spec = find_task("PolymerScience/DiblockMorphologyDiscovery", include_uncertified=True)
        phase = find_task("MaterialsScience/PhaseDiagramDiscovery", include_uncertified=True)
        spec_id = find_task("Spectroscopy/CrowdedSpectrumAssignment", include_uncertified=True)
        self.assertEqual(spec.entrypoint, "identify_morphology")
        self.assertNotEqual(spec.task_dir, phase.task_dir)
        self.assertNotEqual(spec.task_dir, spec_id.task_dir)


if __name__ == "__main__":
    unittest.main()
