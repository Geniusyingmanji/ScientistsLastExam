"""Telling an evaluator edit that moved a measurement from one that only widened the range.

A benchmark under development keeps hitting the same wall: an evaluator improves, the package hash
moves, and every piece of frozen evidence bound to that task is refused - including when the
improvement cannot alter any number the evidence records. Removing an upper clip is that case.

The distinction has to be measured rather than argued, and these tests cover the part that decides
what counts as a difference.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "evaluator_inertness", ROOT / "scripts/check_evaluator_inert.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ComparableMetricTests(unittest.TestCase):
    def test_scores_are_compared(self):
        self.assertEqual(MODULE.comparable({"combined_score": 0.5}), {"combined_score": 0.5})

    def test_wall_clock_is_not_a_difference(self):
        """Two runs of the same evaluator differ in timing and in nothing that matters."""
        self.assertEqual(MODULE.comparable({"wall_seconds": 1.2, "evaluation_wall_seconds": 3.4}),
                         {})

    def test_nested_payloads_are_left_out_rather_than_compared_loosely(self):
        """Per-instance records are large and order-sensitive; a scalar diff is the honest test."""
        self.assertEqual(MODULE.comparable({"per_instance": [{"a": 1}], "score": 0.5}),
                         {"score": 0.5})

    def test_booleans_and_strings_count(self):
        metrics = {"valid": True, "diagnosis": "supported"}
        self.assertEqual(MODULE.comparable(metrics), metrics)


class HistoricalLookupTests(unittest.TestCase):
    def test_a_missing_revision_yields_nothing_rather_than_raising(self):
        with self.subTest("unknown revision"):
            self.assertIsNone(MODULE.historical_evaluator(
                "0" * 40, "NoSuchTask", ROOT / "does-not-matter.py"))


if __name__ == "__main__":
    unittest.main()
