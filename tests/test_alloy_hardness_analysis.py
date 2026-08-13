from __future__ import annotations

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _module():
    path = ROOT / "scripts/analyze_alloy_hardness_calibrations.py"
    spec = importlib.util.spec_from_file_location(
        "alloy_hardness_analysis_test", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load alloy-hardness analysis")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AlloyHardnessAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _module()
        cls.report = cls.module.analyze()

    def test_analysis_binds_calibration_reports_lineage_and_replay(self):
        report = self.report
        self.assertTrue(report["execution_passed"], report)
        self.assertEqual(
            report["trusted_evidence"],
            report["source_provenance"]["source_tree_dirty"] is False,
        )
        self.assertEqual(report["passed"], report["trusted_evidence"])
        self.assertTrue(report["input_task_runtime_source_equivalent"])
        self.assertFalse(report["input_task_runtime_source_unchanged"])
        self.assertEqual(
            report["input_task_runtime_source_changes"],
            sorted(
                list(self.module.SOURCE_MIGRATION_CHANGES)
                + list(self.module.RUNTIME_PATHS)
            ),
        )
        migration = report["input_task_runtime_source_migration"]
        self.assertTrue(migration["accepted"], migration)
        self.assertTrue(all(migration["checks"].values()))
        self.assertTrue(
            report["input_task_runtime_source_migration_equivalent"]
        )
        self.assertTrue(report["input_source_scope_equivalent"])
        self.assertTrue(report["input_llm_condition_equivalent"])
        self.assertTrue(report["input_task_contract_equivalent"])
        self.assertTrue(report["input_runtime_source_hash_equivalent"])
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
                "valid_proposal_count": 7,
                "invalid_proposal_count": 0,
                "positive_development_count": 5,
                "all_thirteen_worlds_valid_count": 7,
                "failure_counts": {},
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
        self.assertTrue(all(
            replay["metrics_exactly_match_bound_trajectory"]
            for record in report["records"].values()
            for replay in record["retained_artifact_replays"].values()
        ))

    def test_findings_separate_visible_utility_prediction_and_confirmation(self):
        findings = self.report["descriptive_findings"]
        self.assertTrue(findings["all_seven_model_proposals_are_protocol_valid"])
        self.assertTrue(findings[
            "all_seven_model_proposals_run_all_thirteen_worlds"
        ])
        self.assertTrue(findings["three_selected_artifacts_are_source_distinct"])
        self.assertTrue(findings[
            "all_selected_models_use_full_unique_assay_budget"
        ])
        self.assertTrue(findings[
            "all_selected_models_have_full_prediction_interval_coverage"
        ])
        self.assertTrue(findings[
            "all_selected_models_have_sparse_exact_recipe_confirmation"
        ])
        self.assertTrue(findings["all_selected_heldout_visible_scores_are_zero"])
        self.assertTrue(findings[
            "normal_development_selection_discards_heldout_improvement"
        ])
        self.assertTrue(findings[
            "blind_equal_visible_score_discards_better_prediction"
        ])
        self.assertTrue(findings[
            "normal_and_blind_selected_development_scores_equal"
        ])
        self.assertTrue(findings["normal_and_blind_are_oracle_call_matched"])
        self.assertTrue(findings["normal_and_blind_are_input_token_matched"])
        self.assertFalse(findings["normal_and_blind_are_total_token_matched"])
        self.assertFalse(findings[
            "exact_recipe_confirmation_supports_broad_generalization"
        ])
        self.assertFalse(findings["feedback_effect_identified"])
        self.assertFalse(findings["pretraining_contamination_ruled_out"])
        self.assertFalse(findings["prospective_alloy_discovery_demonstrated"])
        self.assertIn("NOT_FEEDBACK_CAUSAL", self.report["evidence_scope"])
        self.assertIn("PROSPECTIVE", self.report["evidence_scope"])

        axes = self.report["selected_science_axes"]
        self.assertEqual(
            axes["budget_one"]["development_prediction_score"],
            0.8182315067572551,
        )
        self.assertEqual(
            axes["normal_budget_three"]["heldout_prediction_score"],
            0.7391749445924091,
        )
        self.assertEqual(
            axes["blind_budget_three"]["development_confirmation_coverage"],
            1.0 / 12.0,
        )
        self.assertEqual(
            axes["blind_budget_three"]["heldout_confirmation_mae_hv"],
            144.60000000000002,
        )

    def test_selection_axis_counterexamples_are_bound(self):
        counterexamples = self.report["selection_axis_counterexamples"]
        normal = counterexamples["normal_rejected_heldout_improvement"]
        self.assertEqual(normal["step"], 1)
        self.assertEqual(normal["development_visible_score"], 0.0)
        self.assertFalse(normal["accepted"])
        self.assertGreater(normal["heldout_policy_score"], 0.15)
        self.assertEqual(normal["selected_heldout_policy_score"], 0.0)
        self.assertTrue(normal[
            "development_only_selection_discards_heldout_improvement"
        ])

        blind = counterexamples["blind_equal_visible_score_better_prediction"]
        self.assertEqual(blind["selected_step"], 1)
        self.assertEqual(blind["discarded_step"], 2)
        self.assertEqual(
            blind["selected_visible_score"], blind["discarded_visible_score"]
        )
        self.assertGreater(
            blind["discarded_development_prediction_score"],
            blind["selected_development_prediction_score"],
        )
        self.assertLess(
            blind["discarded_heldout_interval_width_hv"],
            blind["selected_heldout_interval_width_hv"],
        )
        self.assertTrue(blind[
            "equal_visible_score_discards_better_prediction_with_same_coverage"
        ])

    def test_shortcut_scan_rejects_alloy_doi_dataset_and_io_lookup(self):
        module = self.module
        with tempfile.TemporaryDirectory() as tmp:
            clean = Path(tmp) / "clean.py"
            clean.write_text(
                "def design_alloy_batch(problem, assay):\n"
                "    return {'alloy_ids': [], 'predictions': {}}\n",
                encoding="utf-8",
            )
            bad = Path(tmp) / "bad.py"
            bad.write_text(
                "from pathlib import Path\n"
                "def design_alloy_batch(problem, assay):\n"
                "    if problem['candidates'][0]['id'] == 'A-40dc5783c69b':\n"
                "        return {'alloy_ids': [Path('verification/evaluator.py').read_text()], "
                "'predictions': {'10.1007/s00339-019-2506-z': {}}}\n"
                "    return {'alloy_ids': [], 'predictions': {}}\n",
                encoding="utf-8",
            )
            self.assertTrue(module._source_scan(clean)["passed"])
            scan = module._source_scan(bad)
            self.assertFalse(scan["passed"])
            self.assertEqual(
                scan["fixed_alloy_id_literal_hits"], ["A-40dc5783c69b"]
            )
            self.assertIn("10.1007/s00339-019-2506-z", scan["doi_literal_hits"])
            self.assertIn("pathlib", scan["forbidden_import_hits"])
            self.assertIn("read_text", scan["forbidden_call_hits"])

    def test_integrity_and_runtime_changes_fail_closed(self):
        records = copy.deepcopy(self.report["records"])
        records["normal_budget_three"]["integrity_passed"] = False
        failed = self.module._analyze_records(
            self.report["task_calibration"], records,
        )
        self.assertFalse(failed["execution_passed"])

        failed = self.module._analyze_records(
            self.report["task_calibration"],
            copy.deepcopy(self.report["records"]),
            runtime_source_equivalent=True,
            runtime_source_changes=list(self.module.SOURCE_MIGRATION_CHANGES),
            source_migration={"accepted": False},
        )
        self.assertFalse(failed["execution_passed"])

    def test_source_migration_is_hash_bound_and_scoped(self):
        revision = self.module.source_provenance(ROOT)["git_revision"]
        accepted = self.module._source_migration_status(
            revision, list(self.module.SOURCE_MIGRATION_CHANGES),
        )
        self.assertTrue(accepted["accepted"], accepted)

        extra = self.module._source_migration_status(
            revision,
            list(self.module.SOURCE_MIGRATION_CHANGES) + ["sle/change.py"],
        )
        self.assertFalse(extra["accepted"])
        self.assertFalse(extra["checks"]["runtime_change_scope_matches"])

        failed = self.module._analyze_records(
            self.report["task_calibration"],
            copy.deepcopy(self.report["records"]),
            runtime_source_equivalent=False,
            runtime_source_changes=[
                "benchmarks/Chemistry/AlloyHardnessOptimization/change.py"
            ],
        )
        self.assertFalse(failed["execution_passed"])


if __name__ == "__main__":
    unittest.main()
