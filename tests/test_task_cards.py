from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from frontier_science.certification import certification_status
from frontier_science.registry import list_tasks
from scripts.audit_tasks import _task_card_issues, audit


class TaskCardAuditTests(unittest.TestCase):
    def test_every_nonquarantined_task_has_a_valid_card(self):
        checked = 0
        for spec in list_tasks(None):
            if certification_status(spec.task_id) == "quarantined":
                continue
            checked += 1
            self.assertEqual(
                _task_card_issues(spec.task_dir / "TASK_CARD.yaml"),
                [],
                spec.task_id,
            )
        self.assertEqual(checked, 58)

    def test_bad_yaml_is_a_task_issue_not_an_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TASK_CARD.yaml"
            path.write_text("scientific_question: bad: scalar\n", encoding="utf-8")
            issues = _task_card_issues(path)
        self.assertEqual(len(issues), 1)
        self.assertIn("not valid YAML", issues[0])

    def test_schema_requires_scientific_and_evidence_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TASK_CARD.yaml"
            path.write_text("schema_version: 2\nscientific_question: test\n", encoding="utf-8")
            issues = _task_card_issues(path)
        self.assertIn("task card missing artifact", issues)
        self.assertIn("task card missing oracle", issues)
        self.assertIn("task card missing review", issues)
        self.assertIn("task card missing provenance", issues)
        self.assertIn("task card missing novelty_risk", issues)
        self.assertIn("task card missing lineage", issues)
        self.assertIn("task card missing construction_audit", issues)
        self.assertIn("task card missing long_horizon", issues)

    def test_schema_two_maturity_metadata_is_machine_readable(self):
        for spec in list_tasks(None):
            if certification_status(spec.task_id) == "quarantined":
                continue
            card = __import__("yaml").safe_load(
                (spec.task_dir / "TASK_CARD.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(card["schema_version"], 2, spec.task_id)
            self.assertIn(card["provenance"]["class"], {
                "known_answer", "procedural", "public_data_replay", "prospective",
            })
            self.assertEqual(card["lineage"]["status"], "incomplete_legacy")
            self.assertFalse(card["lineage"]["frozen_before_eval"])
            self.assertIsNone(card["lineage"]["freeze_timestamp"])
            self.assertEqual(card["construction_audit"]["status"], "incomplete_legacy")
            self.assertFalse(card["long_horizon"]["measurement_health_passed"])
            self.assertFalse(card["long_horizon"]["material_headroom_after_2h"])

    def test_inventory_audit_counts_all_required_cards(self):
        report = audit()
        self.assertEqual(report["task_card_required_count"], 58)
        self.assertEqual(report["task_card_passed_count"], 58)
        self.assertTrue(report["passed"])


if __name__ == "__main__":
    unittest.main()
