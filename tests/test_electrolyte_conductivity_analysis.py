from __future__ import annotations

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _module():
    path = ROOT / "scripts/analyze_electrolyte_conductivity_design_calibrations.py"
    spec = importlib.util.spec_from_file_location(
        "electrolyte_conductivity_analysis_test", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load electrolyte-conductivity analysis")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ElectrolyteConductivityAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _module()
        cls.report = cls.module.analyze()

    def test_analysis_binds_inputs_lineage_and_science_axes(self):
        report = self.report
        self.assertTrue(report["execution_passed"])
        self.assertEqual(
            report["trusted_evidence"],
            report["source_provenance"]["source_tree_dirty"] is False,
        )
        self.assertEqual(report["passed"], report["trusted_evidence"])
        self.assertTrue(report["input_task_runtime_source_equivalent"])
        self.assertEqual(report["input_task_runtime_source_changes"], [])
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
                "positive_development_count": 7,
                "all_eight_worlds_valid_count": 7,
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
            len(event["per_world"]) == 8
            for record in report["records"].values()
            for event in record["trajectory"]
        ))
        self.assertTrue(all(
            scan["passed"]
            for record in report["records"].values()
            for scan in record["fixed_instance_shortcut_scans"].values()
        ))

    def test_findings_separate_visible_optimization_from_confirmation(self):
        findings = self.report["descriptive_findings"]
        self.assertTrue(findings["all_seven_model_proposals_are_protocol_valid"])
        self.assertTrue(findings[
            "all_model_proposals_improve_the_zero_development_baseline"
        ])
        self.assertTrue(findings["all_selected_models_use_full_unique_assay_budget"])
        self.assertTrue(findings[
            "all_selected_models_have_zero_nominal_untouched_confirmation"
        ])
        self.assertTrue(findings[
            "normal_second_accept_improves_visible_transfer_and_discovery_repeat_robustness_without_confirmation"
        ])
        self.assertTrue(findings[
            "blind_visible_selection_discards_higher_confirmation_candidate"
        ])
        self.assertTrue(findings[
            "normal_visible_selection_discards_higher_confirmation_robustness_candidate"
        ])
        self.assertTrue(findings["normal_outperforms_blind_selected_development"])
        self.assertTrue(findings["normal_and_blind_are_oracle_call_matched"])
        self.assertFalse(findings["normal_and_blind_are_token_matched"])
        self.assertFalse(findings[
            "independent_confirmation_supports_selected_visible_optimization"
        ])
        self.assertFalse(findings["feedback_effect_identified"])
        self.assertFalse(findings["pretraining_contamination_ruled_out"])
        self.assertFalse(findings[
            "prospective_or_complete_cell_discovery_demonstrated"
        ])
        self.assertIn("NOT_FEEDBACK_CAUSAL", self.report["evidence_scope"])

        normal = self.report["records"]["normal_budget_three"]
        self.assertGreater(normal["best_score"], 0.85)
        self.assertGreater(normal["selected_metrics"]["heldout_policy_score"], 0.90)
        self.assertEqual(normal["selected_metrics"]["confirmation_score"], 0.0)
        self.assertEqual(
            normal["selected_metrics"]["heldout_confirmation_score"], 0.0
        )
        counterexample = self.report["selection_axis_counterexamples"]
        self.assertEqual(counterexample["blind_development_selected_step"], 3)
        self.assertEqual(counterexample["blind_best_confirmation_step"], 1)
        self.assertGreater(
            counterexample["blind_best_confirmation_score"],
            counterexample["blind_development_selected_confirmation_score"],
        )

    def test_shortcut_scan_rejects_formulation_lookup_dataset_and_io(self):
        module = self.module
        with tempfile.TemporaryDirectory() as tmp:
            clean = Path(tmp) / "clean.py"
            clean.write_text(
                "def design_electrolyte_batch(problem, assay):\n"
                "    return {'formulation_ids': []}\n",
                encoding="utf-8",
            )
            bad = Path(tmp) / "bad.py"
            bad.write_text(
                "from pathlib import Path\n"
                "def design_electrolyte_batch(problem, assay):\n"
                "    if problem['candidate_formulations'][0]['id'] == 'F00':\n"
                "        return {'formulation_ids': [Path('verification/evaluator.py').read_text()]}\n"
                "    return {'formulation_ids': []}\n",
                encoding="utf-8",
            )
            self.assertTrue(module._fixed_instance_shortcut_scan(clean)["passed"])
            scanned = module._fixed_instance_shortcut_scan(bad)
            self.assertFalse(scanned["passed"])
            self.assertIn("F00", scanned["fixed_formulation_id_literal_hits"])
            self.assertIn("pathlib", scanned["forbidden_import_hits"])
            self.assertIn("read_text", scanned["forbidden_call_hits"])

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
            task_runtime_source_equivalent=False,
            task_runtime_source_changes=[
                "benchmarks/Electrochemistry/ElectrolyteConductivityDesign/change.py"
            ],
        )
        self.assertFalse(failed["execution_passed"])


if __name__ == "__main__":
    unittest.main()
