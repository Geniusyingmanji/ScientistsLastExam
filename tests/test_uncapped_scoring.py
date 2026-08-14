"""Beating the reference must be visible in the score.

Thirty-six of forty-three tasks are clipped at an anchor the author chose, so the best a searcher
can do is match it. That is the structural reason the optimization half saturates: a design better
than the reference reads as exactly as good as the reference, and the benchmark reports nothing
about the result that would matter most.

The nineteen clipped discovery tasks are clipped correctly - their score is the fraction of a
hidden mechanism recovered and nobody can recover more than all of it. These tests cover the
optimization side, where the anchor is a search witness and beating it is the point.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sle.registry import list_tasks  # noqa: E402


def load_evaluator(task_id: str):
    spec = next(s for s in list_tasks(None) if s.task_id == task_id)
    path = spec.task_dir / "verification" / "evaluator.py"
    module_spec = importlib.util.spec_from_file_location("uncapped_evaluator", path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


class TrussUncappedTests(unittest.TestCase):
    def setUp(self):
        self.evaluator = load_evaluator("StructuralEngineering/TrussWeightMinimization")

    def test_matching_the_reference_scores_one(self):
        score = self.evaluator._normalized_weight_score(100.0, 60.0, 60.0)
        self.assertAlmostEqual(score, 1.0)

    def test_beating_the_reference_scores_above_one(self):
        """The whole point: a lighter design must not read as merely equal to the witness."""
        score = self.evaluator._normalized_weight_score(100.0, 60.0, 50.0)
        self.assertGreater(score, 1.0)
        self.assertAlmostEqual(score, 1.25)

    def test_the_baseline_scores_zero(self):
        self.assertAlmostEqual(self.evaluator._normalized_weight_score(100.0, 60.0, 100.0), 0.0)

    def test_worse_than_the_baseline_is_still_zero(self):
        """Below the baseline is a worse design, not a negative achievement."""
        self.assertAlmostEqual(self.evaluator._normalized_weight_score(100.0, 60.0, 130.0), 0.0)

    def test_the_task_declares_itself_uncapped(self):
        """A scorer that can exceed one and a card that says it cannot is the worse of both."""
        spec = next(s for s in list_tasks(None)
                    if s.task_id == "StructuralEngineering/TrussWeightMinimization")
        self.assertEqual(spec.metadata.get("score_mode"), "uncapped")


if __name__ == "__main__":
    unittest.main()
