"""Tests for the report that measures how much of a task's difficulty is its contract.

Its claim is a rank correlation, and a correlation computed over the wrong rows is worse than no
correlation at all: it looks like evidence. These pin the parts that decide which rows exist.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "contract_burden", ROOT / "scripts/report_contract_burden.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SpearmanTests(unittest.TestCase):
    def test_a_perfect_inverse_relationship_is_minus_one(self):
        self.assertAlmostEqual(MODULE.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)

    def test_a_perfect_relationship_is_one(self):
        self.assertAlmostEqual(MODULE.spearman([1, 2, 3, 4], [1, 2, 3, 4]), 1.0)

    def test_ties_do_not_crash_and_use_average_ranks(self):
        self.assertIsNotNone(MODULE.spearman([1, 1, 2, 3], [1, 2, 2, 3]))

    def test_a_constant_column_has_no_correlation_rather_than_a_wrong_one(self):
        self.assertIsNone(MODULE.spearman([1, 1, 1, 1], [1, 2, 3, 4]))

    def test_too_few_points_is_reported_as_not_computable(self):
        self.assertIsNone(MODULE.spearman([1, 2], [2, 1]))


class RowSelectionTests(unittest.TestCase):
    """A task with a handful of proposals cannot support a validity rate."""

    def run_report(self, runs: Path, tmp: Path):
        output = tmp / "burden.json"
        MODULE.main(["--runs", str(runs), "--output", str(output)])
        return json.loads(output.read_text(encoding="utf-8"))

    def test_the_minimum_proposal_count_is_a_real_threshold(self):
        self.assertGreaterEqual(MODULE.MIN_PROPOSALS, 10)

    def test_an_empty_tree_yields_no_rows_and_no_correlation(self):
        with TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            runs.mkdir()
            report = self.run_report(runs, Path(tmp))
            self.assertEqual(report["rows"], [])
            self.assertIsNone(report["rank_correlation_lines_vs_validity"])


if __name__ == "__main__":
    unittest.main()
