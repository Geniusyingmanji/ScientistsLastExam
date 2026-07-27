from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


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
        self.assertEqual(self.report["inventory_count"], 59)
        self.assertEqual(
            self.report["status_counts"],
            {"certified": 7, "candidate": 43, "quarantined": 9},
        )
        self.assertEqual(self.report["gate_counts"]["internal_science_admission"], 50)
        self.assertEqual(self.report["issues"], [])
        self.assertTrue(self.report["execution_passed"])

    def test_maturity_is_not_inferred_from_registry_status(self):
        self.assertEqual(self.report["gate_counts"]["open_release_ready"], 0)
        self.assertEqual(self.report["gate_counts"]["externally_validated"], 0)
        self.assertEqual(self.report["gate_counts"]["long_horizon_ready"], 0)
        self.assertEqual(
            self.report["evidence_coverage"]["domain_review_complete_task_count"], 0
        )
        self.assertEqual(
            self.report["evidence_coverage"]["builder_lineage_declared_task_count"], 50
        )
        self.assertEqual(
            self.report["evidence_coverage"]["builder_lineage_complete_task_count"], 0
        )

    def test_every_admissible_task_has_current_or_migration_safe_model_measurement(self):
        self.assertEqual(
            self.report["evidence_coverage"]["current_model_measurement_count"], 50
        )
        missing = [
            row["task"] for row in self.report["tasks"]
            if row["certification_status"] in {"certified", "candidate"}
            and row["model_measurement"]["current_or_migrated_run_count"] == 0
        ]
        self.assertEqual(missing, [])

    def test_track_f_tasks_have_repeated_controls_and_fresh_confirmation(self):
        for task_id in (
            "DynamicalSystems/ActiveLawDiscovery",
            "Optics/DiffractionGratingDesign",
        ):
            row = self.tasks[task_id]
            self.assertGreaterEqual(
                row["model_measurement"]["maximum_matched_control_replicates"], 48
            )
            self.assertTrue(row["fresh_confirmation"])
            self.assertTrue(all(
                item["contract_binding"] in {
                    "current_contract_bound", "migration_replayed"
                }
                for item in row["fresh_confirmation"]
            ))

    def test_every_evidence_item_has_an_explicit_binding_state(self):
        allowed = self.module.BINDING_STATES
        for row in self.report["tasks"]:
            self.assertEqual(set(row["evidence_binding_counts"]), allowed)
            for items in row["evidence"].values():
                for item in items:
                    self.assertIn(item["contract_binding"], allowed)

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


if __name__ == "__main__":
    unittest.main()
