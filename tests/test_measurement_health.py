from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "audit_measurement_health.py"
    spec = importlib.util.spec_from_file_location("measurement_health_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MeasurementHealthAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.report = cls.module.build_report()
        cls.tasks = {row["task"]: row for row in cls.report["tasks"]}

    def test_classification_is_exhaustive_and_claim_bounded(self):
        self.assertEqual(self.report["inventory_count"], 62)
        self.assertEqual(
            sum(self.report["classification_counts"].values()),
            self.report["inventory_count"],
        )
        self.assertEqual(self.report["issues"], [])
        self.assertTrue(self.report["execution_passed"])
        self.assertEqual(self.report["complete_measurement_health_passed_count"], 0)
        self.assertEqual(self.report["confirmatory_cohort_eligible_count"], 0)

    def test_result_selected_exploratory_cohort_is_frozen(self):
        self.assertEqual(set(self.report["exploratory_cohort"]), self.module.EXPLORATORY_TASKS)
        self.assertEqual(
            self.report["classification_counts"][
                self.module.EXPLORATORY_LONG_HORIZON_SCREEN
            ],
            7,
        )
        for task in self.module.EXPLORATORY_TASKS:
            row = self.tasks[task]
            self.assertFalse(row["confirmatory_cohort_eligible"])
            self.assertIn("material_post_2h_headroom_demonstrated", row["missing_complete_gate_checks"])

    def test_known_saturated_gap_tasks_are_onramps(self):
        for task in (
            "DynamicalSystems/LyapunovControl",
            "Geophysics/SeismicInversion",
            "NuclearEngineering/NeutronDiffusionCriticality",
        ):
            self.assertEqual(
                self.tasks[task]["classification"], self.module.SATURATED_ON_RAMP
            )

    def test_active_law_is_a_control_not_a_headline_optimization_task(self):
        row = self.tasks["DynamicalSystems/ActiveLawDiscovery"]
        self.assertEqual(row["classification"], self.module.CONTROL_ONLY)
        self.assertGreaterEqual(
            row["checks"]["at_least_three_matched_controls"]["value"], 48
        )
        self.assertTrue(row["checks"]["fresh_postcommit_confirmation"]["passed"])

    def test_proposal_health_is_observed_not_inferred(self):
        row = self.tasks["RNAEngineering/RNAInverseDesign"]
        first_valid = row["checks"]["observed_first_valid_in_normal_budget_three"]
        self.assertEqual(first_valid["run_count"], 1)
        self.assertEqual(first_valid["value"], 1.0)
        self.assertTrue(first_valid["passed"])
        self.assertTrue(
            row["checks"]["material_short_run_post_first_valid_gain"]["passed"]
        )


if __name__ == "__main__":
    unittest.main()
