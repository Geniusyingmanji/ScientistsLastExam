from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/build_continuous_restart_plan.py"
)
SPEC = importlib.util.spec_from_file_location("continuous_restart_plan", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ContinuousRestartPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = MODULE.build_plan(MODULE.DEFAULT_PREREG)

    def test_equal_total_active_time_and_cell_counts(self):
        self.assertEqual(self.report["task_count"], 3)
        self.assertEqual(self.report["arm_count"], 2)
        self.assertEqual(self.report["cell_count"], 21)
        self.assertEqual(self.report["issues"], [])
        for row in self.report["by_task"].values():
            self.assertEqual(row["cell_count"], 7)
            self.assertTrue(row["equal_total_active_wall"])
            self.assertEqual(
                set(row["total_active_wall_seconds"].values()), {43200.0}
            )

    def test_every_restart_is_fresh_and_contract_bound(self):
        for cell in self.report["cells"]:
            self.assertFalse(cell["inherits_prior_cell_state"])
            self.assertEqual(len(cell["task_runtime_contract_sha256"]), 64)
            self.assertEqual(len(cell["task_card_sha256"]), 64)
            self.assertTrue(cell["signed_decisions"])
            self.assertEqual(cell["signed_decision_policy"], "record_only")

    def test_arm_horizons_are_true_independent_policies(self):
        continuous = [
            row for row in self.report["cells"]
            if row["arm"] == "continuous_12h"
        ]
        restarts = [
            row for row in self.report["cells"]
            if row["arm"] == "fresh_restart_6x2h"
        ]
        self.assertEqual(len(continuous), 3)
        self.assertEqual(len(restarts), 18)
        self.assertTrue(all(row["active_wall_horizon_s"] == 43200 for row in continuous))
        self.assertTrue(all(row["active_wall_horizon_s"] == 7200 for row in restarts))
        self.assertEqual(
            {row["restart_index"] for row in restarts}, set(range(6))
        )


if __name__ == "__main__":
    unittest.main()
