from __future__ import annotations

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _module():
    path = ROOT / "scripts/analyze_diffraction_grating_calibrations.py"
    spec = importlib.util.spec_from_file_location(
        "diffraction_grating_analysis_test", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load diffraction-grating analysis")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DiffractionGratingAnalysisTests(unittest.TestCase):
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

    def test_analysis_binds_calibrations_lineage_manifests_and_replays(self):
        report = self.report
        self.assertTrue(report["execution_passed"], report)
        self.assertEqual(
            report["trusted_evidence"],
            report["source_provenance"]["source_tree_dirty"] is False,
        )
        self.assertEqual(report["passed"], report["trusted_evidence"])
        self.assertTrue(
            report["calibration_to_model_task_runtime_source_equivalent"]
        )
        self.assertEqual(
            report["calibration_to_model_task_runtime_source_changes"], []
        )
        self.assertTrue(
            report["model_to_analysis_task_runtime_source_equivalent"]
        )
        self.assertEqual(
            report["model_to_analysis_task_runtime_source_changes"],
            [
                "benchmarks/Physics/DiffractionGratingDesign/verification/evaluator.py",
                "sle/evaluate.py",
                "sle/secure_eval.py",
                "sle/trusted_driver.py",
            ],
        )
        self.assertTrue(
            report["model_to_analysis_task_runtime_source_migration"]["accepted"]
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
        self.assertTrue(all(
            scan["passed"]
            for record in report["records"].values()
            for scan in record["retained_artifact_scans"].values()
        ))
        self.assertTrue(all(
            replay["metrics_numerically_equivalent_to_bound_trajectory"]
            for record in report["records"].values()
            for replay in record["retained_artifact_replays"].values()
        ))

        blind = report["records"]["blind_budget_three"]
        baseline_hash = blind["trajectory"][0]["candidate_sha256"]
        self.assertTrue(all(
            event["parent_sha256"] == baseline_hash
            for event in blind["trajectory"][1:]
        ))
        normal = report["records"]["normal_budget_three"]
        self.assertTrue(all(
            event["parent_sha256"] == baseline_hash
            for event in normal["trajectory"][1:]
        ))

    def test_task_calibration_and_independent_crosscheck_are_bound(self):
        calibration = self.report["task_calibration"]
        self.assertGreater(calibration["minimum_nominal_headroom"], 0.25)
        self.assertGreater(calibration["minimum_robust_headroom"], 0.24)
        self.assertLess(
            calibration["maximum_convergence_utility_delta"], 0.004
        )
        self.assertLess(
            calibration["maximum_convergence_efficiency_delta"], 0.025
        )
        self.assertEqual(
            calibration["visible_metric_keys"],
            ["combined_score", "feasibility_rate", "raw_score", "valid"],
        )

        crosscheck = self.report["independent_grcwa_crosscheck"]
        self.assertEqual(crosscheck["summary"]["condition_count"], 72)
        self.assertLess(
            crosscheck["summary"]["maximum_absolute_efficiency_difference"],
            0.01,
        )
        self.assertLess(
            crosscheck["summary"]["q95_absolute_efficiency_difference"],
            0.007,
        )
        self.assertFalse(crosscheck["external_implementation"][
            "runtime_dependency_of_benchmark"
        ])

    def test_failure_taxonomy_and_robustness_gap_are_explicit(self):
        hurdle = self.report["proposal_hurdle_summary"]
        self.assertEqual(hurdle, {
            "proposal_count": 7,
            "valid_proposal_count": 1,
            "invalid_proposal_count": 6,
            "positive_development_count": 1,
            "all_six_worlds_valid_count": 1,
            "proposal_failure_counts": {
                "invalid_grating_submission_all_worlds": 2,
                "invalid_grating_submission_non_titania_transfer_worlds": 4,
            },
            "invalid_world_failure_counts": {
                "invalid_grating_submission": 24,
            },
        })
        findings = self.report["descriptive_findings"]
        self.assertTrue(findings[
            "one_of_seven_model_proposals_is_nominally_valid"
        ])
        self.assertTrue(findings[
            "six_of_seven_model_proposals_fail_protocol_validity"
        ])
        self.assertTrue(findings[
            "four_invalid_proposals_fail_only_non_titania_transfer_worlds"
        ])
        self.assertTrue(findings[
            "two_invalid_proposals_fail_all_six_worlds"
        ])

        gap = self.report["selected_blind_robustness_gap"]
        self.assertEqual(gap["selected_step"], 2)
        self.assertEqual(gap["nominally_valid_world_count"], 6)
        self.assertEqual(
            gap["nominally_valid_but_shift_infeasible_world_count"], 3
        )
        self.assertEqual(gap["development_shift_infeasible_world_count"], 1)
        self.assertEqual(gap["heldout_shift_infeasible_world_count"], 2)
        self.assertGreater(gap["development_robustness_score"], 0.10)
        self.assertEqual(gap["heldout_robustness_score"], 0.0)

    def test_claim_scope_rejects_causal_device_and_discovery_inference(self):
        findings = self.report["descriptive_findings"]
        self.assertTrue(findings[
            "blind_selected_improves_nominal_development_and_heldout_scores"
        ])
        self.assertTrue(findings[
            "blind_selected_has_zero_heldout_robustness"
        ])
        self.assertTrue(findings[
            "all_blind_selected_heldout_worlds_have_shift_geometry_failure"
        ])
        self.assertTrue(findings["normal_and_blind_are_oracle_call_matched"])
        self.assertTrue(findings["normal_and_blind_are_input_token_matched"])
        self.assertFalse(findings["normal_and_blind_are_total_token_matched"])
        self.assertFalse(findings[
            "independent_solver_is_experimental_validation"
        ])
        self.assertFalse(findings["feedback_effect_identified"])
        self.assertFalse(findings["global_optimum_demonstrated"])
        self.assertFalse(findings[
            "fabricated_or_measured_device_demonstrated"
        ])
        self.assertFalse(findings[
            "prospective_autonomous_scientific_discovery_demonstrated"
        ])
        self.assertIn("NOT_FEEDBACK_CAUSAL", self.report["evidence_scope"])
        self.assertIn("FABRICATED_DEVICE", self.report["evidence_scope"])
        self.assertIn("PROSPECTIVE", self.report["evidence_scope"])

    def test_shortcut_scan_rejects_world_evaluator_io_and_network_access(self):
        module = self.module
        with tempfile.TemporaryDirectory() as tmp:
            clean = Path(tmp) / "clean.py"
            clean.write_text(
                "import numpy as np\n"
                "def design_grating(problem):\n"
                "    return np.zeros((problem['layer_count'], 3))\n",
                encoding="utf-8",
            )
            bad = Path(tmp) / "bad.py"
            bad.write_text(
                "from pathlib import Path\n"
                "import requests\n"
                "def design_grating(problem):\n"
                "    if problem['period_um'] == 1.72:\n"
                "        return Path('verification/evaluator.py').read_text()\n"
                "    return requests.get('https://example.com').text\n",
                encoding="utf-8",
            )
            self.assertTrue(module._source_scan(clean)["passed"])
            scan = module._source_scan(bad)
            self.assertFalse(scan["passed"])
            self.assertEqual(scan["fixed_world_numeric_literal_hits"], [1.72])
            self.assertIn(
                "verification/evaluator", scan["evaluator_or_verification_term_hits"]
            )
            self.assertIn("pathlib", scan["forbidden_import_hits"])
            self.assertIn("requests", scan["forbidden_import_hits"])
            self.assertIn("read_text", scan["forbidden_call_hits"])

    def test_integrity_and_runtime_changes_fail_closed(self):
        records = copy.deepcopy(self.report["records"])
        records["normal_budget_three"]["integrity_passed"] = False
        failed = self.module._analyze_records(
            self.report["task_calibration"],
            self.report["independent_grcwa_crosscheck"],
            records,
        )
        self.assertFalse(failed["execution_passed"])

        records = copy.deepcopy(self.report["records"])
        records["normal_budget_three"]["trusted_evaluator_runtime_sha256"] = "f" * 64
        failed = self.module._analyze_records(
            self.report["task_calibration"],
            self.report["independent_grcwa_crosscheck"],
            records,
        )
        self.assertFalse(failed["execution_passed"])
        self.assertFalse(failed["input_trusted_evaluator_runtime_equivalent"])

        failed = self.module._analyze_records(
            self.report["task_calibration"],
            self.report["independent_grcwa_crosscheck"],
            copy.deepcopy(self.report["records"]),
            model_to_runtime_source_equivalent=False,
            model_to_runtime_source_changes=[
                "benchmarks/Physics/DiffractionGratingDesign/change.py"
            ],
        )
        self.assertFalse(failed["execution_passed"])


if __name__ == "__main__":
    unittest.main()
