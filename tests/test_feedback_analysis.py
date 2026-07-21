from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/analyze_feedback_pilot.py"
SPEC = importlib.util.spec_from_file_location("feedback_pilot_analysis", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FeedbackPilotAnalysisTests(unittest.TestCase):
    def test_selected_event_uses_first_valid_tied_maximum(self):
        run = {
            "best": 0.8,
            "trajectory_snapshot": {"events": [
                {"step": 0, "score": 0.0, "valid": True},
                {"step": 1, "score": 0.8, "valid": True},
                {"step": 2, "score": 0.8, "valid": True},
            ]},
        }
        self.assertEqual(MODULE._selected_event(run)["step"], 1)

    def test_blind_lineage_requires_frozen_baseline_and_metadata(self):
        baseline = {"step": 0, "candidate_sha256": "base"}
        proposals = [
            {
                "step": step,
                "parent_sha256": "base",
                "algorithm_metadata": {
                    "selection_policy": "offline_best_of_open_loop_batch"
                },
            }
            for step in (1, 2, 3)
        ]
        run = {"trajectory_snapshot": {"events": [baseline, *proposals]}}
        MODULE._verify_blind_lineage(run)
        proposals[1]["parent_sha256"] = "incumbent"
        with self.assertRaisesRegex(ValueError, "frozen baseline"):
            MODULE._verify_blind_lineage(run)

    def test_paired_summary_retains_small_sample_diagnostic_interval(self):
        result = MODULE._paired_summary([1.0, 2.0, 3.0])
        self.assertEqual(result["n"], 3)
        self.assertEqual(result["mean"], 2.0)
        self.assertLess(result["ci95_low"], 0.0)
        self.assertGreater(result["ci95_high"], 4.0)


if __name__ == "__main__":
    unittest.main()
