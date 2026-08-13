from __future__ import annotations

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _module():
    path = ROOT / "scripts/analyze_demographic_sfs_v2_calibrations.py"
    spec = importlib.util.spec_from_file_location(
        "demographic_sfs_analysis_test", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load demographic-SFS analysis")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DemographicSFSAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _module()
        cls.report = cls.module.analyze()

    def test_analysis_binds_reports_trajectories_and_accounting(self):
        report = self.report
        self.assertTrue(report["execution_passed"])
        self.assertEqual(
            report["trusted_evidence"],
            report["source_provenance"]["source_tree_dirty"] is False,
        )
        self.assertEqual(report["passed"], report["trusted_evidence"])
        self.assertTrue(report["input_task_runtime_source_equivalent"])
        self.assertEqual(
            report["input_task_runtime_source_changes"],
            [
                "sle/evaluate.py",
                "sle/secure_eval.py",
                "sle/trusted_driver.py",
            ],
        )
        self.assertTrue(report["input_task_runtime_source_migration"]["accepted"])
        self.assertTrue(report["input_source_scope_equivalent"])
        self.assertTrue(report["input_llm_condition_equivalent"])
        self.assertTrue(report["input_task_contract_equivalent"])
        self.assertTrue(report["input_runtime_manifest_equivalent"])
        self.assertEqual(
            set(report["records"]),
            {"budget_one", "normal_budget_three", "blind_budget_three"},
        )
        self.assertTrue(all(
            record["integrity_passed"]
            for record in report["records"].values()
        ))
        self.assertEqual(
            report["proposal_hurdle_summary"],
            {
                "proposal_count": 7,
                "valid_proposal_count": 3,
                "invalid_proposal_count": 4,
                "valid_nonzero_proposal_count": 3,
                "all_eleven_worlds_valid_count": 3,
                "failure_counts": {"candidate_runtime_error": 4},
            },
        )

        blind = report["records"]["blind_budget_three"]
        baseline_hash = blind["trajectory"][0]["candidate_sha256"]
        self.assertTrue(all(
            event["parent_sha256"] == baseline_hash
            for event in blind["trajectory"][1:]
        ))
        self.assertTrue(all(
            scan["passed"]
            for record in report["records"].values()
            for scan in record["retained_artifact_scans"].values()
        ))

    def test_findings_keep_prediction_mechanism_and_selection_separate(self):
        report = self.report
        findings = report["descriptive_findings"]
        self.assertTrue(findings["budget_one_model_proposal_is_invalid"])
        self.assertTrue(findings[
            "normal_budget_three_has_three_valid_nonzero_proposals"
        ])
        self.assertTrue(findings["normal_accepts_only_first_proposal"])
        self.assertTrue(findings["normal_selected_uses_full_budget_in_two_calls"])
        self.assertTrue(findings[
            "normal_selected_has_full_coverage_refusal_and_zero_false_discovery"
        ])
        self.assertTrue(findings[
            "normal_selected_prediction_exceeds_mechanism_in_both_splits"
        ])
        self.assertTrue(findings[
            "truth_blind_classical_exceeds_normal_selected_mechanism"
        ])
        self.assertTrue(findings[
            "development_selection_discards_better_heldout_mechanism"
        ])
        self.assertTrue(findings[
            "blind_budget_three_has_no_valid_model_proposal"
        ])
        self.assertTrue(findings["normal_and_blind_are_oracle_call_matched"])
        self.assertFalse(findings["normal_and_blind_are_token_matched"])
        self.assertFalse(findings["feedback_effect_identified"])
        self.assertFalse(findings["arbitrary_demographic_history_identified"])
        self.assertFalse(findings[
            "real_population_or_autonomous_discovery_demonstrated"
        ])

        normal = report["records"]["normal_budget_three"]
        selected = normal["selected_metrics"]
        self.assertAlmostEqual(normal["best_score"], 0.6395338209709723)
        self.assertAlmostEqual(selected["heldout_mechanism_score"], 0.39701014619597036)
        self.assertAlmostEqual(selected["development_prediction_score"], 0.883086673984675)
        self.assertAlmostEqual(selected["heldout_prediction_score"], 0.9391530605691029)
        self.assertEqual(selected["development_false_discovery_rate"], 0.0)
        self.assertEqual(selected["heldout_false_discovery_rate"], 0.0)
        self.assertEqual(normal["oracle_calls"], 4)
        self.assertEqual(normal["total_tokens"], 26450)

        counterexample = report["selection_axis_counterexample"]
        self.assertEqual(counterexample["development_selected_step"], 1)
        self.assertEqual(counterexample["best_heldout_mechanism_step"], 2)
        self.assertGreater(
            counterexample["best_heldout_mechanism_score"],
            counterexample["development_selected_heldout_mechanism_score"],
        )

    def test_analysis_fails_closed_on_integrity_or_hurdle_drift(self):
        records = copy.deepcopy(self.report["records"])
        records["normal_budget_three"]["integrity_passed"] = False
        altered = self.module._analyze_records(
            self.report["task_calibration"], records,
        )
        self.assertFalse(altered["execution_passed"])

        records = copy.deepcopy(self.report["records"])
        event = records["blind_budget_three"]["trajectory"][1]
        event["valid"] = True
        event["failure_kind"] = None
        altered = self.module._analyze_records(
            self.report["task_calibration"], records,
        )
        self.assertFalse(altered["execution_passed"])

    def test_retained_artifact_scan_rejects_lookup_and_file_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.py"
            path.write_text(
                "import os\n"
                "def infer_demography(*args):\n"
                "    open('verification/evaluator.py').read()\n"
                "    return {'world': 'ancestral_misidentification'}\n",
                encoding="utf-8",
            )
            scan = self.module._retained_artifact_scan(path)
        self.assertFalse(scan["passed"])
        self.assertEqual(scan["hidden_world_literal_hits"], [
            "ancestral_misidentification"
        ])
        self.assertIn("os", scan["forbidden_import_hits"])
        self.assertIn("open", scan["forbidden_call_hits"])


if __name__ == "__main__":
    unittest.main()
