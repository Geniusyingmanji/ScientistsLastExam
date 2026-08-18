from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _module():
    path = ROOT / "scripts/analyze_seismic_wave_v2_calibrations.py"
    spec = importlib.util.spec_from_file_location(
        "seismic_wave_analysis_test", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load seismic-wave analysis")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SeismicWaveAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _module()
        try:
            cls.report = cls.module.analyze()
        except FileNotFoundError as missing:
            # Run directories are not committed, so a checkout that does not hold them is a
            # reader missing data - not a reader looking at broken evidence. Erroring here made
            # fifteen analysis suites fail identically on every machine but the one the runs were
            # produced on, which buries a real regression in noise that never changes.
            raise unittest.SkipTest(
                "the runs this analysis reads are not in this checkout: %s" % missing)

    def test_analysis_binds_formal_inputs_axes_and_lineage(self):
        report = self.report
        self.assertTrue(report["execution_passed"])
        # The source-under-test is intentionally uncommitted here; a clean-source
        # invocation after commit upgrades the derived report to trusted evidence.
        self.assertEqual(
            report["trusted_evidence"],
            report["source_provenance"]["source_tree_dirty"] is False,
        )
        self.assertEqual(report["passed"], report["trusted_evidence"])
        self.assertTrue(report["input_task_runtime_source_equivalent"])
        self.assertTrue(report["input_source_scope_equivalent"])
        self.assertTrue(report["input_llm_condition_equivalent"])
        self.assertEqual(report["input_task_runtime_source_changes"], [])

        total = report["proposal_summary"]["formal_total"]
        self.assertEqual(total["proposal_count"], 7)
        self.assertEqual(total["valid_proposal_count"], 6)
        self.assertEqual(total["invalid_proposal_count"], 1)
        self.assertEqual(total["supported_abstention_count"], 5)
        self.assertEqual(total["supported_claiming_proposal_count"], 1)
        self.assertEqual(total["failure_counts"], {"candidate_timeout": 1})

        records = report["records"]
        self.assertTrue(all(row["selected_step"] == 0 for row in records.values()))
        baseline_hash = records["blind_budget_three"]["trajectory"][0][
            "candidate_sha256"
        ]
        self.assertTrue(all(
            row["parent_sha256"] == baseline_hash
            for row in records["blind_budget_three"]["trajectory"][1:]
        ))
        self.assertEqual(
            report["normal_minus_blind_diagnostic"]["total_tokens"], -258
        )

    def test_findings_separate_information_mechanism_and_refusal(self):
        findings = self.report["descriptive_findings"]
        self.assertTrue(findings[
            "five_valid_proposals_over_refuse_supported_worlds"
        ])
        self.assertTrue(findings[
            "budget_one_claims_only_one_heldout_supported_world"
        ])
        self.assertTrue(findings[
            "high_information_does_not_imply_mechanism_recovery"
        ])
        self.assertTrue(findings[
            "scalar_zero_conflates_distinct_failure_states"
        ])
        vector = self.report["science_vectors"][
            "formal_gpt55_nonbaseline_proposals"
        ]
        self.assertEqual(vector["information_max_I"], 1.0)
        self.assertEqual(vector["optimization_best_O"], 0.0)
        self.assertGreater(vector["heldout_mechanism_best_M"], 0.30)
        self.assertEqual(
            vector["development_supported_discovery_coverage_best"], 0.0
        )
        self.assertEqual(
            vector["heldout_supported_discovery_coverage_best"], 1.0 / 3.0
        )
        self.assertIn("NOT_CAUSAL", self.report["evidence_scope"])

    def test_superseded_contract_runs_are_excluded(self):
        diagnostic = self.report["superseded_contract_diagnostics"]
        self.assertEqual(
            diagnostic["classification"],
            "SUPERSEDED_UNDERSPECIFIED_CONTRACT_DIAGNOSTIC",
        )
        self.assertFalse(diagnostic["included_in_formal_model_performance"])
        self.assertEqual(diagnostic["report_count"], 3)
        self.assertEqual(diagnostic["proposal_count"], 7)
        self.assertEqual(diagnostic["callback_schema_failure_count"], 4)
        self.assertIn("not current-contract model performance", diagnostic["reason"])

    def test_lineage_or_claim_pattern_breaks_gate(self):
        calibration = self.report["task_calibration"]
        records = copy.deepcopy(self.report["records"])
        superseded = self.report["superseded_contract_diagnostics"]
        records["blind_budget_three"]["trajectory"][2][
            "parent_sha256"
        ] = "x" * 64
        failed = self.module._analyze_records(
            calibration, records, superseded, True
        )
        self.assertFalse(failed["execution_passed"])

        records = copy.deepcopy(self.report["records"])
        records["normal_budget_three"]["trajectory"][2][
            "heldout_supported_claim_coverage"
        ] = 1.0 / 3.0
        failed = self.module._analyze_records(
            calibration, records, superseded, True
        )
        self.assertFalse(failed["execution_passed"])


if __name__ == "__main__":
    unittest.main()
