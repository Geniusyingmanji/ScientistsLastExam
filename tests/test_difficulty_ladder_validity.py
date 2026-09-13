"""A failed experiment must not be reported as evidence of a harder task."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


REPORT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "report_difficulty_ladder.py"
SPEC = importlib.util.spec_from_file_location("difficulty_ladder_validity_report", REPORT_PATH)
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def scored(score, **extra):
    return {"status": "scored", "combined_score": score, "valid": 1.0, **extra}


class DifficultyLadderValidityTests(unittest.TestCase):
    def run_report(self, levels, requested="1,2,3"):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            row = {"task": "T/X", "candidate": "fixed.py", "levels": levels}
            stream = io.StringIO()
            with patch.object(report, "measure", return_value=row), contextlib.redirect_stdout(stream):
                result = report.main([
                    "--task", "T/X", "--candidate", "fixed.py", "--levels", requested,
                    "--output", str(output),
                ])
            self.assertEqual(result, 0)
            return json.loads(output.read_text()), stream.getvalue()

    def assert_unavailable(self, levels, requested="1,2,3"):
        document, console = self.run_report(levels, requested)
        row = document["rows"][0]
        self.assertEqual(row["comparison_status"], "unavailable")
        self.assertIsNone(row["monotone_harder"])
        self.assertIsNone(row["flat"])
        self.assertEqual(document["ladders_that_change_nothing"], [])
        self.assertEqual(document["complete_comparisons"], 0)
        self.assertEqual(document["unavailable_comparisons"], 1)
        self.assertIn("comparison unavailable", console)
        return row

    def test_invalid_zero_is_not_scientific_difficulty(self):
        row = self.assert_unavailable({1: scored(.8), 2: scored(.4), 3: scored(0, valid=0)})
        self.assertEqual(row["levels"]["3"]["combined_score"], 0)
        self.assertIn("invalid", row["unavailable_levels"]["3"])

    def test_infrastructure_and_timeout_override_numeric_scores(self):
        for flag in ("infrastructure_failure", "timeout"):
            with self.subTest(flag=flag):
                self.assert_unavailable({1: scored(.8), 2: scored(.4), 3: scored(0, **{flag: True})})

    def test_missing_or_failed_middle_level_cannot_shrink_the_comparison(self):
        for middle in (None, {"status": "could not score: evaluator unavailable"}):
            with self.subTest(middle=middle):
                levels = {1: scored(.8), 3: scored(.2)}
                if middle is not None:
                    levels[2] = middle
                row = self.assert_unavailable(levels)
                self.assertIn("2", row["unavailable_levels"])

    def test_missing_validity_and_nonfinite_scores_are_unavailable(self):
        values = [
            {"status": "scored", "combined_score": 0},
            *[scored(value) for value in (None, float("nan"), float("inf"), -float("inf"), True, 10**1000)],
        ]
        for value in values:
            with self.subTest(value=value):
                self.assert_unavailable({1: scored(.8), 2: scored(.4), 3: value})

    def test_complete_valid_scores_distinguish_decreasing_flat_and_increasing(self):
        for scores, monotone, flat in [((.8, .4, 0), True, False),
                                      ((.4, .4, .4), True, True),
                                      ((.2, .4, .8), False, False)]:
            with self.subTest(scores=scores):
                document, _ = self.run_report({i: scored(value) for i, value in enumerate(scores, 1)})
                row = document["rows"][0]
                self.assertEqual(row["comparison_status"], "complete")
                self.assertEqual(row["monotone_harder"], monotone)
                self.assertEqual(row["flat"], flat)
                self.assertEqual(document["complete_comparisons"], 1)
                self.assertEqual(document["unavailable_comparisons"], 0)

    def test_single_level_does_not_establish_a_ladder(self):
        self.assert_unavailable({1: scored(.4)}, requested="1")

    def test_duplicate_nonpositive_and_empty_levels_are_rejected_before_evaluation(self):
        for levels in ("1,1", "0,1", "-1,2", ""):
            with self.subTest(levels=levels), patch.object(report, "measure") as measure:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    report.main(["--task", "T/X", "--candidate", "fixed.py", "--levels", levels])
                self.assertEqual(error.exception.code, 2)
                measure.assert_not_called()

    def test_no_recorded_candidate_remains_in_unavailable_count(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            with patch.object(report, "_best_candidate", return_value=None), contextlib.redirect_stdout(io.StringIO()):
                report.main(["--task", "T/X", "--output", str(output)])
            document = json.loads(output.read_text())
            self.assertEqual(document["complete_comparisons"], 0)
            self.assertEqual(document["unavailable_comparisons"], 1)
            self.assertEqual(document["rows"][0]["status"], "no recorded candidate on disk")
