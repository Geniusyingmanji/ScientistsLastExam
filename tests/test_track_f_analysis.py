from __future__ import annotations

import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_track_f_confirmation.py"
SPEC = importlib.util.spec_from_file_location("track_f_analysis_for_test", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TrackFAnalysisTests(unittest.TestCase):
    def test_independent_welch_contrast_matches_manual_equal_variance_case(self):
        treatment = [0.4, 0.5, 0.6, 0.7]
        control = [0.1, 0.2, 0.3, 0.4]
        result = MODULE.independent_welch_contrast(
            treatment, control, alpha=0.05
        )
        self.assertAlmostEqual(
            result["difference_treatment_minus_control"], 0.3
        )
        expected_sd = math.sqrt(1.0 / 60.0)
        expected_se = math.sqrt(2.0 * expected_sd**2 / 4.0)
        self.assertAlmostEqual(result["treatment"]["sample_sd"], expected_sd)
        self.assertAlmostEqual(result["standard_error"], expected_se)
        self.assertAlmostEqual(result["welch_degrees_of_freedom"], 6.0)
        self.assertLess(result["two_sided_p_value"], 0.02)
        self.assertGreater(result["confidence_interval"][0], 0.0)
        self.assertFalse(result["variance_degenerate"])

    def test_degenerate_contrast_is_explicit_and_never_nan(self):
        equal = MODULE.independent_welch_contrast(
            [0.0, 0.0], [0.0, 0.0], alpha=0.05
        )
        self.assertTrue(equal["variance_degenerate"])
        self.assertIsNone(equal["two_sided_p_value"])
        self.assertEqual(equal["confidence_interval"], [0.0, 0.0])
        separated = MODULE.independent_welch_contrast(
            [1.0, 1.0], [0.0, 0.0], alpha=0.05
        )
        self.assertTrue(separated["variance_degenerate"])
        self.assertIsNone(separated["two_sided_p_value"])
        self.assertIsNone(separated["welch_t_statistic"])

    def _confirmation_fixture(self):
        tasks = [MODULE.PRIMARY_TASK, MODULE.SECONDARY_TASK]
        replicates = [0, 1]
        planned = []
        results = []
        artifact_ids = set()
        for task in tasks:
            axis = (
                MODULE.PRIMARY_AXIS
                if task == MODULE.PRIMARY_TASK
                else MODULE.SECONDARY_AXIS
            )
            for replicate in replicates:
                for condition in MODULE.EXPECTED_MODES:
                    for endpoint in MODULE.EXPECTED_ENDPOINTS:
                        endpoint_id = "%s|%d|%s|%s" % (
                            task, replicate, condition, endpoint
                        )
                        artifact_id = endpoint_id + "|artifact"
                        artifact_ids.add(artifact_id)
                        row = {
                            "endpoint_id": endpoint_id,
                            "task": task,
                            "replicate_id": replicate,
                            "condition": condition,
                            "endpoint": endpoint,
                            "common_total_token_horizon": 100,
                            "completed_through_step": 2,
                            "tokens_spent_by_completed_step": 90,
                            "best_source_step": 1,
                            "search_score": 0.2,
                            "candidate_sha256": "a" * 64,
                            "context_sha256": "b" * 64,
                            "artifact_id": artifact_id,
                        }
                        planned.append(row)
                        value = 0.8 if condition == "normal" else 0.2
                        results.append({
                            **row,
                            "deduplicated_evaluation": False,
                            "deterministic": True,
                            "stochastic_artifact": False,
                            "metrics": {
                                "combined_score": value,
                                "valid": 1.0,
                                axis: value,
                                "trusted_context_sha256": "b" * 64,
                            },
                        })
        confirmation = {
            "planned_endpoints": planned,
            "endpoint_results": results,
            "completion": {
                "incomplete_or_infrastructure_failed_evaluations": 0,
                "stochastic_artifacts": 0,
                "deterministic_artifacts": len(artifact_ids),
                "planned_unique_artifacts": len(artifact_ids),
            },
        }
        design = {
            "tasks": tasks,
            "replicates": replicates,
            "candidate_invalid_score": 0.0,
            "alpha": 0.05,
        }
        return confirmation, design

    def test_endpoint_risk_set_keeps_candidate_invalid_at_zero(self):
        confirmation, design = self._confirmation_fixture()
        invalid = next(
            row for row in confirmation["endpoint_results"]
            if row["task"] == MODULE.PRIMARY_TASK
            and row["replicate_id"] == 0
            and row["condition"] == "normal"
            and row["endpoint"] == MODULE.PRIMARY_ENDPOINT
        )
        invalid["metrics"] = {
            "combined_score": -1.0e18,
            "valid": 0.0,
            "candidate_failure_kind": "candidate_runtime_error",
            "trusted_context_sha256": invalid["context_sha256"],
        }
        records = MODULE._endpoint_records(confirmation, design)
        retained = next(row for row in records if row["endpoint_id"] == invalid["endpoint_id"])
        self.assertFalse(retained["candidate_valid"])
        self.assertTrue(retained["candidate_invalid_floor_applied"])
        self.assertEqual(retained["failure_inclusive_science_score"], 0.0)
        summaries, _ = MODULE._condition_summaries(records, design)
        normal = next(
            row for row in summaries
            if row["task"] == MODULE.PRIMARY_TASK
            and row["endpoint"] == MODULE.PRIMARY_ENDPOINT
            and row["condition"] == "normal"
        )
        self.assertEqual(normal["failure_inclusive_score"]["n"], 2)
        self.assertEqual(normal["candidate_invalid_count"], 1)

    def test_endpoint_risk_set_fails_on_missing_stochastic_or_infrastructure(self):
        confirmation, design = self._confirmation_fixture()
        confirmation["endpoint_results"].pop()
        with self.assertRaisesRegex(ValueError, "risk set"):
            MODULE._endpoint_records(confirmation, design)

        confirmation, design = self._confirmation_fixture()
        confirmation["completion"]["stochastic_artifacts"] = 1
        with self.assertRaisesRegex(ValueError, "replay gate"):
            MODULE._endpoint_records(confirmation, design)

        confirmation, design = self._confirmation_fixture()
        confirmation["endpoint_results"][0]["metrics"][
            "infrastructure_failure"
        ] = 1.0
        with self.assertRaisesRegex(ValueError, "binding"):
            MODULE._endpoint_records(confirmation, design)

    def test_complete_synthetic_cohort_opens_only_specific_primary_gate(self):
        confirmation, design = self._confirmation_fixture()
        records = MODULE._endpoint_records(confirmation, design)
        summaries, contrasts = MODULE._condition_summaries(records, design)
        self.assertEqual(len(records), 32)
        self.assertEqual(len(summaries), 16)
        self.assertEqual(len(contrasts), 12)
        primary = next(
            row for row in contrasts
            if row["task"] == MODULE.PRIMARY_TASK
            and row["endpoint"] == MODULE.PRIMARY_ENDPOINT
            and row["contrast"] == "normal_minus_selection_blind"
        )
        self.assertEqual(primary["inference_scope"], "powered_confirmatory_primary")
        self.assertAlmostEqual(
            primary["difference_treatment_minus_control"], 0.6
        )
        # This two-row fixture is intentionally constant and therefore cannot
        # manufacture a positive inferential claim from a degenerate variance.
        self.assertTrue(primary["variance_degenerate"])
        self.assertIsNone(primary["two_sided_p_value"])
        self.assertTrue(all(
            row is primary
            or row["inference_scope"]
            == "descriptive_secondary_no_multiplicity_claim"
            for row in contrasts
        ))

    def test_main_refuses_to_overwrite_analysis(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "analysis.json"
            output.write_text("occupied\n", encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "overwrite"):
                MODULE.main([
                    "--preregistration", str(root / "prereg.json"),
                    "--search-report", str(root / "search.json"),
                    "--confirmation-report", str(root / "confirmation.json"),
                    "--output", str(output),
                ])


if __name__ == "__main__":
    unittest.main()
