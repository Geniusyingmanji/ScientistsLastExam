from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _module():
    path = ROOT / "scripts/analyze_antenna_v2_calibrations.py"
    spec = importlib.util.spec_from_file_location("antenna_analysis_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record(label, budget, scores, robustness, shifted):
    events = [{
        "step": 0, "accepted": True, "candidate_sha256": "a" * 64,
        "parent_sha256": None, "combined_score": 0.0, "robustness_score": 0.0,
        "heldout_policy_score": 0.0, "heldout_robustness_score": 0.0,
        "mean_worst_shifted_quality_db": 7.0,
        "mean_shifted_target_gain_feasibility_rate": 1.0,
    }]
    for index, score in enumerate(scores, 1):
        events.append({
            "step": index, "accepted": True,
            "candidate_sha256": chr(ord("a") + index) * 64,
            "parent_sha256": chr(ord("a") + index - 1) * 64,
            "combined_score": score, "robustness_score": robustness[index - 1],
            "heldout_policy_score": score * 0.9,
            "heldout_robustness_score": robustness[index - 1] * 0.8,
            "mean_worst_shifted_quality_db": shifted[index - 1],
            "mean_shifted_target_gain_feasibility_rate": 1.0,
        })
    return {
        "label": label, "report": label + ".json", "report_sha256": "1" * 64,
        "trajectory_sha256": "2" * 64, "source_revision": "3" * 40,
        "seed": budget, "proposal_budget": budget,
        "server_side_seed_control": False, "oracle_calls": budget + 1,
        "total_tokens": budget * 100, "best_score": scores[-1],
        "feedback_scope": "synthetic sealed metrics", "trajectory": events,
    }


class AntennaCalibrationAnalysisTests(unittest.TestCase):
    def test_analysis_requires_visible_up_and_robustness_down(self):
        module = _module()
        records = {
            "budget_one": _record("budget_one", 1, [0.999], [0.6], [10.0]),
            "budget_three": _record(
                "budget_three", 3, [0.84, 0.99, 1.0],
                [0.70, 0.63, 0.57], [10.9, 10.6, 10.3],
            ),
        }
        report = module._analyze_records(records)
        self.assertTrue(report["execution_passed"])
        self.assertEqual(
            report["evidence_scope"],
            "ANTENNA_CALIBRATION_NOT_CAUSAL_OR_POPULATION_EVIDENCE",
        )
        self.assertTrue(all(
            row["development_score"] > 0.0
            and row["robustness_score"] < 0.0
            and row["mean_worst_shifted_quality_db"] < 0.0
            for row in report["budget_three_accepted_step_changes"]
        ))

    def test_nonmonotone_visible_curve_fails_gate(self):
        module = _module()
        records = {
            "budget_one": _record("budget_one", 1, [0.999], [0.6], [10.0]),
            "budget_three": _record(
                "budget_three", 3, [0.84, 0.80, 1.0],
                [0.70, 0.63, 0.57], [10.9, 10.6, 10.3],
            ),
        }
        self.assertFalse(module._analyze_records(records)["execution_passed"])


if __name__ == "__main__":
    unittest.main()
