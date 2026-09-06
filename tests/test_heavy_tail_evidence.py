"""Discovery-contract pins for HeavyTailEvidence."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Mathematics/HeavyTailEvidence"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HeavyTailEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "tail_oracle")
        cls.baseline = _load(TASK / "solution.py", "tail_baseline")
        cls.reference = _load(
            TASK / "verification/reference_tail.py", "tail_reference"
        )

    def test_small_public_samples_are_unsupported(self):
        small = [spec for spec in self.evaluator.DEVELOPMENT_WORLDS if spec["kind"] == "small"]
        self.assertTrue(small)
        self.assertTrue(all(spec["n_public"] < 25 for spec in small))
        power = [spec for spec in self.evaluator.DEVELOPMENT_WORLDS if spec["kind"] == "powerlaw"]
        self.assertGreater(len({spec["alpha"] for spec in power}), 1)

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _extra: {"abstain": True}
        )
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_the_alpha_two_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.synthesize_tail_evidence)
        reference = self.evaluator.evaluate(self.reference.synthesize_tail_evidence)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["development_false_discovery_rate"], 1.0)
        self.assertEqual(reference["development_false_discovery_rate"], 0.0)
        self.assertGreater(reference["development_signal_recovery_rate"], 0.5)
        self.assertGreater(reference["development_correct_refusal_rate"], 0.99)

    def test_malformed_submissions_score_zero_without_raising(self):
        metrics = self.evaluator.evaluate(lambda *_args: {"abstain": "true", "confidence": 0.0})
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_this_is_not_a_look_elsewhere_bump_or_discrepant_constant(self):
        from sle.registry import find_task
        spec = find_task("Mathematics/HeavyTailEvidence", include_uncertified=True)
        look = find_task("ParticlePhysics/LookElsewhereAnomaly", include_uncertified=True)
        disc = find_task("ParticlePhysics/DiscrepantMeasurements", include_uncertified=True)
        self.assertEqual(spec.entrypoint, "synthesize_tail_evidence")
        self.assertNotEqual(spec.task_dir, look.task_dir)
        self.assertNotEqual(spec.task_dir, disc.task_dir)


if __name__ == "__main__":
    unittest.main()
