"""Discovery-contract pins for SequenceLawRecovery.

A candidate that refuses every world is valid: the submission shape is right. The combined
score must still be zero, because mechanism recovery on determined worlds is empty. Averaging
the three axes would give that candidate a high mark on refusal and false-discovery, which is
why those axes are never averaged.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import sympy  # noqa: F401
except ImportError:  # pragma: no cover - skip rather than fail the rest of the suite
    sympy = None


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TASK = ROOT / "benchmarks/Mathematics/SequenceLawRecovery"


@unittest.skipUnless(sympy is not None, "sympy is not installed")
class SequenceLawRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "sequence_law_oracle")
        cls.baseline = _load(TASK / "solution.py", "sequence_law_baseline")
        cls.reference = _load(
            TASK / "verification/reference_recoverer.py", "sequence_law_reference"
        )

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(lambda _observation: {"abstain": True})
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_mechanism_score"], 0.0)

    def test_the_fibonacci_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.recover_law)
        reference = self.evaluator.evaluate(self.reference.recover_law)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertGreater(reference["combined_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
