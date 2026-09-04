"""Contract pins for NonlinearCodeRecords.

The score is uncapped and anchored at a construction the evaluator computes rather than stores, so
the two things worth pinning are that the anchor is what it claims to be and that the published
records are still out of reach of the reference. The third test pins the fact that made this task
worth building: at these parameters no linear code reaches the record.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Mathematics/NonlinearCodeRecords"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NonlinearCodeRecordsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "nlcr_oracle")
        cls.baseline = _load(TASK / "solution.py", "nlcr_baseline")
        cls.reference = _load(
            TASK / "verification/reference_parity_check_linear.py", "nlcr_reference")

    def test_every_instance_is_an_open_cell(self):
        """A closed cell would make the record a proven optimum and the task a lookup."""
        for row in self.evaluator.INSTANCES:
            self.assertLess(row["published_lower"], row["published_upper"],
                            "A(%d,%d) is not open" % (row["n"], row["d"]))

    def test_the_linear_reference_reaches_no_record(self):
        """The premise of the task: linearity is what stands between the reference and the
        record. If a linear code ever matches a published lower bound here, that instance has
        stopped measuring anything and should be replaced."""
        metrics = self.evaluator.evaluate(self.reference.build_code)
        self.assertEqual(metrics["instances_beating_the_published_record"], 0)
        for row in metrics["per_instance"]:
            self.assertLess(row["code_size"], row["published_lower"],
                            "A(%d,%d): a linear code now matches the record" % (row["n"], row["distance"]))

    def test_the_baseline_scores_zero_and_the_reference_sits_between(self):
        baseline = self.evaluator.evaluate(self.baseline.build_code)
        reference = self.evaluator.evaluate(self.reference.build_code)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertGreater(reference["combined_score"], 0.4)
        self.assertLess(reference["combined_score"], 0.9)

    def test_the_distance_check_rejects_a_code_that_is_one_short(self):
        """Positive control on the only thing the oracle actually verifies."""
        row = self.evaluator.INSTANCES[0]
        n, d = row["n"], row["d"]
        first = np.zeros(n, dtype=int)
        second = first.copy()
        second[: d - 1] = 1
        size, error = self.evaluator._validate_code([first.tolist(), second.tolist()], n, d)
        self.assertIsNone(size)
        self.assertIn("minimum distance", error)


if __name__ == "__main__":
    unittest.main()
