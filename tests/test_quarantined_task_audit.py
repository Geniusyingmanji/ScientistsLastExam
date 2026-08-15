"""The quarantine reaudit has to survive its own wave ending.

This file used to assert the details of nine quarantined tasks: their parameter counts, their
shared non-physical oracle fingerprint, the axes each failed. All nine have since been retired -
their files are gone from the repository - so those assertions describe deleted code and cannot
pass. Keeping them would have meant keeping a permanently red suite that says nothing.

What survives retirement is the coverage invariant: every task the manifest calls quarantined has
a reproduced check, and every check the audit carries refers to a task that is still quarantined.
That is the claim worth pinning, it is what would catch a task being quarantined and quietly not
re-audited, and it holds whether the quarantine holds nine tasks or none.

When a task is quarantined again, the per-record assertions belong back here, written against that
task.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    path = ROOT / "scripts/audit_quarantined_tasks.py"
    spec = importlib.util.spec_from_file_location("quarantined_task_audit_test", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load quarantined task audit")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QuarantinedTaskAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _module()
        cls.report = cls.module.audit()
        cls.records = {row["task"]: row for row in cls.report["records"]}

    def test_every_manifest_quarantine_has_a_reproduced_check(self):
        self.assertTrue(self.report["execution_passed"], self.report)
        self.assertEqual(self.report["missing_checks"], [])
        self.assertEqual(self.report["stale_checks"], [])
        self.assertEqual(
            set(self.records), set(self.report["manifest_quarantined_tasks"])
        )

    def test_the_summary_counts_agree_with_the_records_it_summarizes(self):
        summary = self.report["summary"]
        self.assertEqual(summary["manifest_quarantined_count"],
                         len(self.report["manifest_quarantined_tasks"]))
        self.assertEqual(summary["audited_count"], len(self.records))
        self.assertEqual(summary["reproduced_defect_count"],
                         sum(row["defect_reproduced"] for row in self.records.values()))
        self.assertEqual(summary["recommended_retain_quarantine_count"],
                         sum(row["recommendation"] == "retain_quarantine_until_substantive_rebuild"
                             for row in self.records.values()))

    def test_a_quarantined_task_is_never_reported_as_meeting_the_standard(self):
        """Quarantine is a claim about a defect, not a score. A reproduced defect keeps the task
        out; it never argues the task in. This holds vacuously today and is the assertion that
        would fire if a future reaudit ever tried to readmit on the strength of a reproduction."""
        self.assertEqual(self.report["summary"]["meets_internal_benchmark_standard_count"], 0)
        for task, row in self.records.items():
            self.assertFalse(row["meets_internal_benchmark_standard"], task)
            self.assertTrue(row["defect_reproduced"], task)
            self.assertTrue(row["failed_standard_axes"], task)
            self.assertEqual(row["recommendation"],
                             "retain_quarantine_until_substantive_rebuild")

    def test_checks_naming_a_retired_task_are_reported_rather_than_owed(self):
        """A retired task is neither quarantined nor admitted - it is gone.

        Reading the retired wave as still-owed checks made this audit raise KeyError on a task the
        registry has never heard of, which looks like a broken tool rather than a finished
        quarantine. Retired checks are named so the history stays legible, and they carry no
        weight in the counts.
        """
        import sys

        sys.path.insert(0, str(ROOT))
        from sle.registry import list_tasks

        present = {spec.task_id for spec in list_tasks(None)}
        declared = set(self.module.REPRODUCED_WAVE4_CHECKS) | set(self.module.GENERIC_CLONE_TASKS)
        self.assertEqual(set(self.report["retired_checks"]), declared - present)
        for task in self.report["retired_checks"]:
            self.assertNotIn(task, self.records)
            self.assertNotIn(task, self.report["stale_checks"])


if __name__ == "__main__":
    unittest.main()
