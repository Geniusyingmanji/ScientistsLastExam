from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/analyze_gpt56_science_pilot.py"
)
SPEC = importlib.util.spec_from_file_location("gpt56_science_pilot_analysis", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _event(step, score, valid=True, failure=None):
    metrics = {"combined_score": score, "valid": float(valid)}
    if failure:
        metrics["per_world"] = [{"failure_kind": failure}]
    return {
        "step": step,
        "score": score,
        "valid": valid,
        "metrics": metrics,
        "error": None,
    }


class GPT56SciencePilotAnalysisTests(unittest.TestCase):
    def test_selected_event_retains_first_valid_tied_maximum(self):
        events = [_event(0, 0.0), _event(1, 0.8), _event(2, 0.8)]
        self.assertEqual(MODULE._selected_event(events, 0.8)["step"], 1)

    def test_failure_kind_prefers_explicit_then_nested(self):
        explicit = _event(1, 0.0, False)
        explicit["metrics"]["candidate_failure_kind"] = "candidate_runtime_error"
        self.assertEqual(
            MODULE._failure_kind(explicit), "candidate_runtime_error"
        )
        self.assertEqual(
            MODULE._failure_kind(_event(1, 0.0, False, "invalid_submission")),
            "invalid_submission",
        )

    def test_post_first_valid_separates_absence_and_later_gain(self):
        absent = [_event(0, 0.0), _event(1, -1e18, False)]
        self.assertIsNone(MODULE._post_first_valid(absent)["first_valid_score"])
        events = [
            _event(0, 0.0),
            _event(1, 0.2),
            _event(2, 0.5),
            _event(3, 0.4),
        ]
        result = MODULE._post_first_valid(events)
        self.assertEqual(result["first_valid_step"], 1)
        self.assertAlmostEqual(result["later_gain"], 0.3)

    def test_failure_kind_extracts_retained_runtime_error(self):
        event = _event(1, -1e18, False)
        event["error"] = "candidate invalid: candidate_runtime_error"
        self.assertEqual(
            MODULE._failure_kind(event), "candidate_runtime_error"
        )

    def test_markdown_states_claim_limit(self):
        report = {
            "task_assessment": {
                task: {
                    "normal_best_score": 0.0,
                    "selection_blind_best_score": 0.0,
                    "valid_proposals": 0,
                    "proposal_count": 6,
                    "difficulty_evidence": "fixture",
                }
                for task in MODULE.EXPECTED_TASKS
            },
            "aggregate": {
                "valid_proposals": 0,
                "proposal_valid_rate": 0.0,
                "failure_kind_counts": {},
            },
            "inputs": {"pilot_report": {"sha256": "fixture"}},
        }
        rendered = MODULE.render_markdown(report)
        self.assertIn("not a 50-task model ranking", rendered)
        self.assertIn("does not establish", rendered)


if __name__ == "__main__":
    unittest.main()
