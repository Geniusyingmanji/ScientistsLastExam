from __future__ import annotations

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/analyze_prospective_meta_analysis_calibrations.py"


def _analysis():
    spec = importlib.util.spec_from_file_location(
        "prospective_meta_analysis_calibration_test", SCRIPT
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load prospective-meta-analysis analyzer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProspectiveMetaAnalysisCalibrationAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _analysis()
        cls.calibration = cls.module._load_calibration()
        cls.records = {
            label: cls.module._load_model(label, path)
            for label, path in cls.module.REPORTS.items()
        }

    def report(self, records=None, **kwargs):
        return self.module._analyze_records(
            self.calibration,
            records or self.records,
            runtime_source_equivalent=kwargs.get(
                "runtime_source_equivalent", True
            ),
            runtime_source_changes=kwargs.get("runtime_source_changes", []),
        )

    def test_integrity_hurdles_and_single_run_scope(self):
        report = self.report()
        self.assertTrue(report["execution_passed"])
        self.assertTrue(report["input_task_runtime_source_equivalent"])
        self.assertTrue(report["input_source_scope_equivalent"])
        self.assertTrue(report["input_llm_condition_equivalent"])
        self.assertTrue(report["input_task_contract_equivalent"])
        self.assertTrue(report["input_runtime_manifest_equivalent"])
        self.assertTrue(report["input_baseline_candidate_equivalent"])
        self.assertTrue(all(
            record["integrity_passed"]
            for record in report["records"].values()
        ))
        self.assertIn("SINGLE_RUN", report["evidence_scope"])
        self.assertIn("NOT_FEEDBACK_CAUSAL", report["evidence_scope"])
        self.assertEqual(
            report["proposal_hurdle_summary"],
            {
                "proposal_count": 7,
                "valid_proposal_count": 3,
                "invalid_proposal_count": 4,
                "schema_invalid_count": 4,
                "valid_empty_abstention_count": 3,
                "valid_scientific_workflow_count": 0,
                "proposal_with_nonzero_evidence_integrity_count": 0,
                "proposal_with_confirmation_count": 0,
                "proposal_with_supported_claim_coverage_count": 0,
                "retained_terminal_source_count": 3,
                "unretained_intermediate_source_count": 4,
            },
        )

    def test_protocol_repair_is_not_scientific_workflow_progress(self):
        report = self.report()
        findings = report["descriptive_findings"]
        self.assertTrue(findings[
            "normal_feedback_repairs_schema_validity_in_later_proposals"
        ])
        self.assertFalse(findings[
            "normal_feedback_produces_evidence_screening_or_confirmation"
        ])
        self.assertTrue(findings["all_valid_proposals_are_empty_abstentions"])
        self.assertTrue(findings[
            "same_zero_score_conflates_schema_failure_and_empty_abstention"
        ])
        self.assertFalse(findings["feedback_effect_identified"])
        self.assertFalse(findings[
            "real_meta_analysis_or_autonomous_discovery_demonstrated"
        ])
        normal = report["records"]["normal_budget_three"]
        self.assertEqual(
            normal["classification_counts"],
            {"schema_invalid": 1, "valid_empty_abstention": 2},
        )

    def test_budget_three_contrast_is_descriptive_not_causal(self):
        contrast = self.report()[
            "normal_minus_blind_budget_three_descriptive_contrast"
        ]
        self.assertEqual(contrast["best_score"], 0.0)
        self.assertEqual(contrast["valid_proposal_count"], 1)
        self.assertEqual(contrast["oracle_calls"], 0)
        self.assertEqual(contrast["input_tokens"], 0)
        self.assertEqual(contrast["output_tokens"], -570)
        self.assertEqual(contrast["total_tokens"], -570)

    def test_analysis_fails_closed_on_integrity_hurdle_or_source_drift(self):
        records = copy.deepcopy(self.records)
        records["normal_budget_three"]["integrity_passed"] = False
        self.assertFalse(self.report(records)["execution_passed"])

        records = copy.deepcopy(self.records)
        event = records["normal_budget_three"]["trajectory"][2]
        event["classification"] = "valid_scientific_workflow"
        self.assertFalse(self.report(records)["execution_passed"])

        self.assertFalse(self.report(
            runtime_source_equivalent=False,
            runtime_source_changes=["benchmarks/example.py"],
        )["execution_passed"])

    def test_runtime_scope_tracks_trusted_evaluator_not_search_or_narrative(self):
        scope = self.module.TASK_RUNTIME_SCOPE
        for path in (
            "sle/evaluate.py",
            "sle/trusted_driver.py",
            "sle/secure_eval.py",
            "sle/candidate_worker.py",
            "sle/rpc_codec.py",
        ):
            self.assertIn(path, scope)
        for path in (
            "sle/algorithms/evolve.py",
            "sle/protocol.py",
            "sle/certification.yaml",
        ):
            self.assertNotIn(path, scope)

    def test_retained_scan_rejects_hidden_world_and_dynamic_io(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.py"
            path.write_text(
                "import importlib\n"
                "def synthesize_evidence(problem, confirm):\n"
                "    source = open('verification/evaluator.py').read()\n"
                "    return {'kind': 'linear_positive', 'source': source}\n",
                encoding="utf-8",
            )
            scan = self.module._scan_retained_source(path)
        self.assertFalse(scan["passed"])
        self.assertIn("importlib", scan["forbidden_import_hits"])
        self.assertIn("open", scan["forbidden_call_hits"])
        self.assertIn("linear_positive", scan["hidden_world_literal_hits"])
        self.assertIn(
            "verification/evaluator.py", scan["hidden_world_literal_hits"]
        )


if __name__ == "__main__":
    unittest.main()
