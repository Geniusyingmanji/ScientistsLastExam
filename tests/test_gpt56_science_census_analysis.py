from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/analyze_gpt56_science_census.py"
)
SPEC = importlib.util.spec_from_file_location("gpt56_science_census_analysis", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _event(valid=False, metrics=None, error=None):
    return {"valid": valid, "metrics": metrics or {}, "error": error}


class GPT56ScienceCensusAnalysisTests(unittest.TestCase):
    def test_difficulty_bands_exclude_invalid_proposals(self):
        self.assertEqual(MODULE._difficulty_band(False, 0.8), "protocol_blocked")
        self.assertEqual(MODULE._difficulty_band(True, 0.01), "executable_floor")
        self.assertEqual(MODULE._difficulty_band(True, 0.49), "difficult")
        self.assertEqual(MODULE._difficulty_band(True, 0.50), "discriminating")
        self.assertEqual(MODULE._difficulty_band(True, 0.95), "near_ceiling")

    def test_failure_diagnostic_separates_execution_and_submission(self):
        runtime = _event(
            metrics={"candidate_failure_kind": "candidate_runtime_error"}
        )
        self.assertEqual(
            MODULE._failure_diagnostic(runtime)["failure_class"],
            "candidate_execution_failure",
        )
        submission = _event(
            metrics={"per_world": [{"failure_kind": "invalid_submission"}]}
        )
        self.assertEqual(
            MODULE._failure_diagnostic(submission)["failure_class"],
            "submission_or_protocol_failure",
        )

    def test_nested_reasons_are_canonicalized(self):
        wrong = _event(
            metrics={"per_world": [{"reason": "submission has the wrong fields"}]}
        )
        self.assertEqual(
            MODULE._failure_diagnostic(wrong)["failure_kind"],
            "wrong_submission_fields",
        )
        ocean = _event(
            metrics={"per_world": [{
                "reason": "RuntimeError: initial drifters must lie inside the public interior"
            }]}
        )
        self.assertEqual(
            MODULE._failure_diagnostic(ocean)["failure_kind"],
            "invalid_experiment_request",
        )

    def test_selected_event_uses_first_valid_tied_maximum(self):
        events = [
            {"step": 0, "valid": True, "score": 0.2},
            {"step": 1, "valid": True, "score": 0.2},
        ]
        self.assertEqual(MODULE._selected_event(events, 0.2)["step"], 0)

    def test_frozen_census_counts_and_negative_gate_are_retained(self):
        report = MODULE.analyze()
        self.assertEqual(report["aggregate"]["valid_proposals"], 36)
        self.assertEqual(
            report["aggregate"]["difficulty_band_counts"],
            {
                "difficult": 6,
                "discriminating": 11,
                "executable_floor": 6,
                "near_ceiling": 13,
                "protocol_blocked": 14,
            },
        )
        self.assertFalse(
            report["predeclared_descriptive_gates"]["challenge"]["passed"]
        )
        self.assertEqual(
            report["self_evolving_assessment"]["evolution_candidate_count"], 15
        )
        self.assertFalse(
            report["portfolio_disposition"]["benchmark_requirements_all_passed"]
        )


if __name__ == "__main__":
    unittest.main()
