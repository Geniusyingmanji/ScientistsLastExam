"""Discovery-contract pins for PhaseDiagramDiscovery.

The public score is mechanism, normalised so that declining every world is exactly zero.
A trapped system is the unsupported case: refusing it is correct, refusing everything is not.
The three axes stay separate; this file only pins the combined-score normalisation and that
the delivered baseline sits below the sealed reference, which is the headroom the card claims.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Chemistry/PhaseDiagramDiscovery"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PhaseDiagramDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "phase_diagram_oracle")
        cls.baseline = _load(TASK / "solution.py", "phase_diagram_baseline")
        cls.reference = _load(
            TASK / "verification/reference_mapping.py", "phase_diagram_reference"
        )

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(lambda _problem, _synthesize: {"abstain": True})
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_mechanism_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_the_grid_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.discover_phases)
        reference = self.evaluator.evaluate(self.reference.discover_phases)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertGreater(reference["combined_score"], 0.0)
        self.assertIn("development_false_discovery_rate", baseline)
        self.assertIn("development_correct_refusal_rate", baseline)


if __name__ == "__main__":
    unittest.main()
