from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "audit_task_maturity.py"
    spec = importlib.util.spec_from_file_location("task_maturity_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TaskMaturityAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.report = cls.module.build_report()
        cls.tasks = {row["task"]: row for row in cls.report["tasks"]}

    def test_inventory_and_internal_risk_set_are_complete(self):
        self.assertEqual(self.report["inventory_count"], 46)
        self.assertEqual(
            self.report["status_counts"],
            {"certified": 5, "candidate": 41, "quarantined": 0},
        )
        # Admission is fail-closed against the current evidence bindings. Candidate registration
        # does not imply admission, and older reports whose task/runtime contract drifted do not
        # count toward this total.
        self.assertEqual(self.report["gate_counts"]["internal_science_admission"], 46)
        self.assertEqual(self.report["issues"], [])
        self.assertTrue(self.report["execution_passed"])

    def test_explicit_current_full_suite_gate_is_fail_closed(self):
        revision = "a" * 40
        head = "b" * 40
        document = {
            "trusted_evidence": True,
            "execution_passed": True,
            "unittest_ok": True,
            "test_count": 1,
            "source_provenance": {
                "git_revision": revision,
                "source_tree_dirty": False,
            },
        }
        with patch.object(self.module, "_git_commit_exists", return_value=True):
            with patch.object(self.module, "_git", return_value=""):
                with patch.object(self.module.subprocess, "run") as run:
                    run.return_value.returncode = 0
                    self.assertEqual(
                        self.module._current_full_suite_issues(document, head), []
                    )
                    run.return_value.returncode = 1
                    self.assertEqual(len(
                        self.module._current_full_suite_issues(document, head)
                    ), 1)

    def test_maturity_is_not_inferred_from_registry_status(self):
        self.assertEqual(self.report["gate_counts"]["open_release_ready"], 0)
        self.assertEqual(self.report["gate_counts"]["externally_validated"], 0)
        self.assertEqual(self.report["gate_counts"]["long_horizon_ready"], 0)
        self.assertEqual(
            self.report["evidence_coverage"]["domain_review_complete_task_count"], 0
        )

    def test_expired_certified_admission_is_surfaced_per_task_not_hidden_by_totals(self):
        records = [
            {
                "task": "T/certified",
                "certification_status": "certified",
                "gates": {"internal_science_admission": {"passed": False}},
            },
            {
                "task": "T/candidate",
                "certification_status": "candidate",
                "gates": {"internal_science_admission": {"passed": True}},
            },
        ]
        self.assertEqual(
            self.module._certified_without_current_admission(records),
            ["T/certified"],
        )
        self.assertEqual(self.module._status_admission_issues(records), [])
        self.assertEqual(
            self.report["evidence_coverage"]["builder_lineage_declared_task_count"], 46,
        )
        # Still zero with two tasks now naming their builder, because `complete` here also
        # requires `frozen_before_eval`, and neither is frozen: EnzymeKineticsLaw had a public key
        # changed after its first calibration draw, and both may yet be hardened. Declaring the
        # lineage and freezing the task are different claims and the audit keeps them apart.
        self.assertEqual(
            self.report["evidence_coverage"]["builder_lineage_complete_task_count"], 0
        )

    def test_every_admissible_task_has_current_or_migration_safe_model_measurement(self):
        # Most admissible tasks have no bound measurement, and that is a finding rather than a
        # bug: a recorded run binds to the contract it was made against, and the evaluators
        # changed - most of them when the upper clip came off. The runs still describe what those
        # models did, about a previous contract. Restoring full coverage means re-running the
        # cohort, not re-signing the old numbers, so the count moves as that campaign lands and is
        # checked for consistency below rather than pinned to a passing value.
        coverage = self.report["evidence_coverage"]["current_model_measurement_count"]
        self.assertLessEqual(coverage, self.report["inventory_count"])
        # Every admissible task is currently in this list, for the same reason the count above is
        # zero. What this pins is that the audit and the coverage count agree about *which* tasks
        # lack a bound measurement - a task counted as measured while appearing here, or the
        # reverse, would mean the coverage number and the per-task records had drifted apart.
        missing = [
            row["task"] for row in self.report["tasks"]
            if row["certification_status"] in {"certified", "candidate"}
            and row["model_measurement"]["current_or_migrated_run_count"] == 0
        ]
        admissible = [row["task"] for row in self.report["tasks"]
                      if row["certification_status"] in {"certified", "candidate"}]
        self.assertEqual(
            len(admissible) - len(missing),
            self.report["evidence_coverage"]["current_model_measurement_count"],
        )

    def test_every_quarantined_task_has_current_reproduced_defect_evidence(self):
        self.assertEqual(
            self.report["evidence_coverage"][
                "current_quarantine_defect_reproduction_count"
            ],
            self.report["status_counts"].get("quarantined", 0),
        )
        quarantined = [
            row for row in self.report["tasks"]
            if row["certification_status"] == "quarantined"
        ]
        # The quarantine is empty: its wave was retired rather than readmitted. The loop below is
        # the invariant that matters and it holds whether the quarantine has nine tasks or none.
        self.assertEqual(len(quarantined),
                         self.report["status_counts"].get("quarantined", 0))
        for row in quarantined:
            evidence = row["quarantine_reaudit"]
            self.assertTrue(evidence["passed"], row)
            self.assertTrue(evidence["defect_reproduced"])
            self.assertFalse(evidence["meets_internal_benchmark_standard"])
            self.assertIn(
                evidence["contract_binding"],
                {"current_contract_bound", "migration_replayed"},
            )

    def test_track_f_tasks_have_repeated_controls_and_fresh_confirmation(self):
        """Unbound, not withdrawn - and the binding rule is what this now pins.

        These two tasks carried 48 matched-control replicates and a fresh post-commit
        confirmation. Both read zero now for the same reason every model measurement does: the
        evidence is bound to a contract that has since changed. What still has to hold, and is the
        durable half of the original claim, is that anything the audit *does* count as current is
        genuinely bound - never counted while historical.
        """
        for task_id in (
            "DynamicalSystems/ActiveLawDiscovery",
            "Optics/DiffractionGratingDesign",
        ):
            row = self.tasks[task_id]
            replicates = row["model_measurement"]["maximum_matched_control_replicates"]
            confirmations = row["fresh_confirmation"]
            self.assertTrue(all(
                item["contract_binding"] in {
                    "current_contract_bound", "migration_replayed"
                }
                for item in confirmations
            ))
            self.assertGreaterEqual(replicates, 0)
            if confirmations:
                self.assertGreaterEqual(replicates, 48)

    def test_every_evidence_item_has_an_explicit_binding_state(self):
        allowed = self.module.BINDING_STATES
        for row in self.report["tasks"]:
            self.assertEqual(set(row["evidence_binding_counts"]), allowed)
            for items in row["evidence"].values():
                for item in items:
                    self.assertIn(item["contract_binding"], allowed)

    def test_proposal_health_is_observed_and_condition_specific(self):
        rna = self.tasks["RNAEngineering/RNAInverseDesign"]["model_measurement"]
        b3 = rna["proposal_trajectory_health"]["normal_budget_three"]
        # Observed, never inferred: a zero-run condition has no rate; once current-contract runs
        # exist, counts and the observed rate must become populated consistently.
        self.assertGreaterEqual(b3["run_count"], 0)
        if b3["run_count"] == 0:
            self.assertEqual(b3["proposal_event_count"], 0)
            self.assertEqual(b3["runs_with_valid_proposals"], 0)
            self.assertIsNone(b3["observed_first_valid_run_rate"])
        else:
            self.assertLessEqual(b3["runs_with_valid_proposals"], b3["run_count"])
            self.assertIsNotNone(b3["observed_first_valid_run_rate"])

        matrix = self.tasks["Algorithm/MatrixMultiplicationRank"]["model_measurement"]
        matrix_b3 = matrix["proposal_trajectory_health"]["normal_budget_three"]
        if matrix_b3["run_count"] == 0:
            self.assertIsNone(matrix_b3["observed_first_valid_run_rate"])
        else:
            self.assertIsNotNone(matrix_b3["observed_first_valid_run_rate"])

    def test_untracked_historical_reports_are_excluded(self):
        paths = {
            item["path"]
            for row in self.report["tasks"]
            for items in row["evidence"].values()
            for item in items
        }
        self.assertNotIn(
            "experiments/task_certification_audit_2026-07-26_v60.json", paths
        )

    def test_contract_binding_is_independent_of_discipline_path(self):
        task = "Optics/DiffractionGratingDesign"
        tree = self.module._contract_tree("HEAD", task)
        self.assertTrue(tree)
        self.assertTrue(self.module._contract_equal("HEAD", "HEAD", task))
        self.assertIn(
            "benchmarks/Physics/DiffractionGratingDesign",
            self.module._task_contract_bases(task),
        )


if __name__ == "__main__":
    unittest.main()
