from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from _sandbox_tools import skip_unless_sandbox  # noqa: E402


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_evaluation_recovery.py"
SPEC = importlib.util.spec_from_file_location("evaluation_recovery_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EvaluationRecoveryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = MODULE.build_report()

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_all_process_fault_scenarios_pass(self):
        self.assertEqual(self.report["scenario_count"], 8)
        self.assertEqual(self.report["issues"], [])
        self.assertTrue(self.report["execution_passed"])
        self.assertTrue(all(self.report["checks"].values()))
        for scenario in self.report["scenarios"]:
            self.assertTrue(all(scenario["checks"].values()), scenario["mode"])

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_search_crashes_resume_without_another_evaluator_call(self):
        rows = {
            row["mode"]: row for row in self.report["scenarios"]
        }
        for mode in MODULE.GREEDY_MODES:
            row = rows[mode]
            self.assertEqual(row["resume_evaluator_call_count"], 0)
            self.assertEqual(row["resume_error"], None)
            self.assertEqual(
                row["evaluation_ledger_snapshot"]["request_count"],
                row["evaluation_ledger_snapshot"]["receipt_count"],
            )

    def test_request_before_receipt_is_not_mislabelled_physical_exactly_once(self):
        row = next(
            item for item in self.report["scenarios"]
            if item["mode"] == "request_before_receipt"
        )
        self.assertEqual(row["recovery_evaluator_call_count"], 1)
        self.assertIn(
            "NOT_PHYSICAL_EXACTLY_ONCE_LIVE_LAB_EXECUTION",
            self.report["evidence_scope"],
        )
        self.assertTrue(any(
            "Physical exactly-once execution" in limitation
            for limitation in self.report["limitations"]
        ))


if __name__ == "__main__":
    unittest.main()
