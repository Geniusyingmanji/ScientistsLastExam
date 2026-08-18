from __future__ import annotations

import importlib.util
import tempfile
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_exploratory_2h.py"
SPEC = importlib.util.spec_from_file_location("exploratory_2h_analysis_for_test", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExploratoryTwoHourAnalysisTests(unittest.TestCase):
    def test_materiality_applies_scalar_record_and_bound_criteria(self):
        contract = {
            "scientific_quantity": "test quantity",
            "threshold_basis": "benchmark_preregistered_operational_threshold_not_field_consensus",
            "required_axes": ["development", "heldout", "robustness"],
            "baseline_pointer": "/baseline",
            "material_witness_pointer": "/witness",
            "criteria": [
                {
                    "id": "scalar",
                    "kind": "paired_scalar",
                    "baseline_pointer": "/baseline/loss",
                    "witness_pointer": "/witness/loss",
                    "direction": "decrease",
                    "minimum_relative_change": 0.2,
                    "unit": "loss",
                    "axes": ["development"],
                },
                {
                    "id": "records",
                    "kind": "paired_records",
                    "baseline_pointer": "/baseline/per_instance",
                    "witness_pointer": "/witness/per_instance",
                    "record_key": "name",
                    "value_pointer": "/value",
                    "split_field": "split",
                    "required_splits": ["development", "heldout"],
                    "direction": "increase",
                    "minimum_absolute_change": 0.1,
                    "unit": "utility",
                    "axes": ["development", "heldout"],
                },
                {
                    "id": "bound",
                    "kind": "values_bound",
                    "source_pointer": "/witness/per_instance",
                    "value_pointer": "/feasible",
                    "operator": "eq",
                    "threshold": True,
                    "axes": ["robustness"],
                },
            ],
        }
        baseline = {
            "loss": 1.0,
            "per_instance": [
                {"name": "a", "split": "development", "value": 0.1},
                {"name": "b", "split": "heldout", "value": 0.2},
            ],
        }
        witness = {
            "loss": 0.7,
            "per_instance": [
                {
                    "name": "a", "split": "development", "value": 0.3,
                    "feasible": True,
                },
                {
                    "name": "b", "split": "heldout", "value": 0.4,
                    "feasible": True,
                },
            ],
        }
        result = MODULE.evaluate_materiality(contract, baseline, witness)
        self.assertTrue(result["operational_materiality_contract_passed"])
        self.assertEqual(result["criteria_passed_count"], 3)

        witness["per_instance"][1]["feasible"] = False
        failed = MODULE.evaluate_materiality(contract, baseline, witness)
        self.assertFalse(failed["operational_materiality_contract_passed"])
        self.assertFalse(failed["criteria"][-1]["passed"])

    def test_wall_time_auc_and_cutoff_keep_late_result_separate(self):
        events = [
            {
                "step": 0, "score": 0.0, "best_score": 0.0,
                "valid": True, "accepted": True,
                "cumulative_wall_seconds": 1.0,
                "algorithm_metadata": {},
            },
            {
                "step": 1, "score": 0.5, "best_score": 0.5,
                "valid": True, "accepted": True,
                "cumulative_wall_seconds": 5.0,
                "algorithm_metadata": {"proposal_published_wall_seconds": 3.0},
            },
            {
                "step": 2, "score": 0.9, "best_score": 0.5,
                "valid": True, "accepted": False,
                "cumulative_wall_seconds": 12.0,
                "algorithm_metadata": {"proposal_published_wall_seconds": 9.0},
            },
        ]
        self.assertAlmostEqual(MODULE.wall_time_auc(events, 10.0), 0.25)
        online = MODULE._online_best_completed_by(events, 10.0)
        observer = MODULE._observer_best_published_by(events, 10.0)
        self.assertEqual(online["step"], 1)
        self.assertEqual(observer["step"], 2)

    def test_replaying_the_preregistered_cohort_refuses_once_its_tasks_change(self):
        """A preregistration cannot be rebound, so this has to fail closed rather than replay.

        The seven tasks in this frozen cohort have been edited since - most of them when the upper
        clip came off - so the analysis no longer describes the tasks on disk. Every other frozen
        binding in this repository is repaired by measuring the change inert or re-measuring the
        evidence. Neither is available here: the point of a preregistration is that it was fixed
        *before* the runs, and re-signing it after seeing the results is the one thing it exists to
        prevent. So the correct behaviour is refusal, and refusal is what is pinned.
        """
        with self.assertRaises(ValueError) as raised:
            MODULE.analyze()
        self.assertIn("frozen input contract differs", str(raised.exception))

    def test_the_recorded_replay_is_the_authority_for_its_numbers(self):
        """The analysis ran when the contracts still matched, and its report is committed.

        Those numbers are a historical fact about seven task versions that no longer exist. They
        are checked here rather than dropped, because deleting the assertions along with the
        ability to re-derive them would lose the record entirely.
        """
        recorded = ROOT / "experiments/exploratory_2h_analysis_2026-07-30_v1.json"
        if not recorded.is_file():
            self.skipTest("the recorded two-hour analysis is not in this checkout")
        report = json.loads(recorded.read_text(encoding="utf-8"))
        self.assertTrue(report["execution_passed"])
        self.assertEqual(report["risk_set"]["scheduled_cells"], 7)
        self.assertEqual(report["risk_set"]["successful_cells"], 7)
        self.assertEqual(report["risk_set"]["proposal_count"], 1033)
        self.assertEqual(report["risk_set"]["valid_proposal_count"], 790)
        self.assertEqual(report["risk_set"]["oracle_calls_including_baselines"], 1040)
        self.assertEqual(
            report["risk_set"]["signed_in_horizon_endpoint_actions"],
            {"commit": 6, "abstain": 1},
        )
        self.assertEqual(report["risk_set"]["terminal_workspace_valid_count"], 5)
        self.assertEqual(
            report["risk_set"][
                "online_incumbent_operational_materiality_pass_count"
            ],
            3,
        )
        self.assertEqual(
            report["risk_set"][
                "terminal_workspace_operational_materiality_pass_count"
            ],
            1,
        )
        self.assertTrue(report["interpretive_findings"][
            "terminal_endpoint_policy_label_differs_from_runner_semantics"
        ])
        self.assertTrue(report["interpretive_findings"][
            "every_terminal_workspace_artifact_differs_from_online_incumbent"
        ])
        self.assertFalse(report["claims"]["material_post_2h_headroom_demonstrated"])
        self.assertFalse(report["claims"]["autonomous_scientific_discovery_demonstrated"])

    def test_main_refuses_to_overwrite_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "occupied.json"
            output.write_text("occupied\n", encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "overwrite"):
                MODULE.main(["--output", str(output)])


if __name__ == "__main__":
    unittest.main()
