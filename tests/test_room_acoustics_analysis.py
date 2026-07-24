from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _module():
    path = ROOT / "scripts/analyze_room_acoustics_v2_calibrations.py"
    spec = importlib.util.spec_from_file_location(
        "room_acoustics_analysis_test", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load room-acoustics analysis")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RoomAcousticsAnalysisTests(unittest.TestCase):
    def test_analysis_binds_inputs_axes_and_noncausal_scope(self):
        report = _module().analyze()
        self.assertTrue(report["execution_passed"])
        # During development the source-under-test can be uncommitted.  Trust is
        # intentionally upgraded only by a clean-source invocation after commit.
        self.assertEqual(
            report["trusted_evidence"],
            report["source_provenance"]["source_tree_dirty"] is False,
        )
        self.assertEqual(report["passed"], report["trusted_evidence"])
        self.assertTrue(report["input_task_runtime_source_equivalent"])
        self.assertTrue(report["input_source_scope_equivalent"])
        self.assertTrue(report["input_llm_condition_equivalent"])
        self.assertEqual(report["input_task_runtime_source_changes"], [])

        records = report["records"]
        self.assertEqual(records["budget_one"]["selected_step"], 0)
        self.assertEqual(records["normal_budget_three"]["selected_step"], 0)
        self.assertEqual(records["blind_budget_three"]["selected_step"], 3)
        self.assertEqual(records["normal_budget_three"]["proposal_valid_count"], 0)
        self.assertEqual(records["blind_budget_three"]["proposal_valid_count"], 2)
        self.assertEqual(
            records["normal_budget_three"]["proposal_failure_counts"],
            {"candidate_runtime_error": 3},
        )
        baseline_hash = records["blind_budget_three"]["trajectory"][0][
            "candidate_sha256"
        ]
        self.assertTrue(all(
            row["parent_sha256"] == baseline_hash
            for row in records["blind_budget_three"]["trajectory"][1:]
        ))
        self.assertEqual(
            len(records["blind_budget_three"]["selected_instance_axes"]), 6
        )
        self.assertTrue(all(
            row["all_shift_geometry_feasible"]
            for row in records["blind_budget_three"]["selected_instance_axes"]
        ))

        findings = report["descriptive_findings"]
        self.assertTrue(findings["budget_one_preserves_optimization_headroom"])
        self.assertTrue(findings["budget_one_exposes_development_heldout_conflict"])
        self.assertTrue(findings["open_loop_batch_finds_non_saturated_improvement"])
        self.assertTrue(findings["selected_open_loop_artifact_transfers_to_heldout_and_shifts"])
        self.assertTrue(findings["feedback_not_shown_necessary_by_open_loop_calibration"])
        self.assertTrue(findings["normal_and_blind_are_oracle_call_matched"])
        self.assertTrue(findings["normal_and_blind_are_not_token_matched"])
        self.assertIn("NOT_CAUSAL", report["evidence_scope"])
        self.assertTrue(any(
            "not causal" in limitation.lower()
            for limitation in report["limitations"]
        ))


if __name__ == "__main__":
    unittest.main()
