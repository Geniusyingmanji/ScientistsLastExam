"""Discovery-contract pins for UnimolecularFalloffLaw.

The public score is mechanism, normalised so that declining every world is exactly zero.
Two-channel and negative-order worlds are unsupported. A textbook Lindemann claim
therefore scores zero even when the rate is actually Lindemann-like, because those worlds
are published as discoveries on the unsupported set too.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Chemistry/UnimolecularFalloffLaw"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UnimolecularFalloffLawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "falloff_oracle")
        cls.baseline = _load(TASK / "solution.py", "falloff_baseline")
        cls.reference = _load(
            TASK / "verification/reference_falloff.py", "falloff_reference"
        )

    def test_troe_suppresses_the_mid_falloff_relative_to_lindemann(self):
        lindemann = {
            "kind": "lindemann",
            "A_inf": 2.4e7,
            "E_inf": 2100.0,
            "A0": 4.8e9,
            "E0": 900.0,
        }
        troe = dict(lindemann, kind="troe", Fcent=0.42)
        k_l = self.evaluator.true_k(lindemann, 300.0, 0.03)
        k_t = self.evaluator.true_k(troe, 300.0, 0.03)
        self.assertGreater(k_l, k_t)
        self.assertGreater(self.evaluator.true_k(lindemann, 300.0, 100.0), k_l)

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _measure: {"abstain": True}
        )
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_the_arrhenius_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.identify_falloff)
        reference = self.evaluator.evaluate(self.reference.identify_falloff)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["development_false_discovery_rate"], 1.0)
        self.assertEqual(reference["development_false_discovery_rate"], 0.0)
        self.assertGreater(reference["development_signal_recovery_rate"], 0.5)
        self.assertGreater(reference["development_correct_refusal_rate"], 0.99)

    def test_malformed_submissions_score_zero_without_raising(self):
        metrics = self.evaluator.evaluate(lambda *_args: {"abstain": True, "confidence": 1.1})
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_this_is_not_a_reaction_network_or_enzyme_on_ramp(self):
        from sle.registry import find_task
        spec = find_task("ChemicalKinetics/UnimolecularFalloffLaw", include_uncertified=True)
        network = find_task("ChemicalKinetics/ReactionMechanismFitting", include_uncertified=True)
        enzyme = find_task("SystemsBiology/EnzymeKineticsLaw", include_uncertified=True)
        self.assertEqual(spec.entrypoint, "identify_falloff")
        self.assertNotEqual(spec.entrypoint, network.entrypoint)
        self.assertNotEqual(spec.task_dir, enzyme.task_dir)


if __name__ == "__main__":
    unittest.main()
