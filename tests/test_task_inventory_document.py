"""TASKS.md is generated from the registry; a stale copy fails here rather than lying on GitHub."""
from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.registry import list_tasks  # noqa: E402

SPEC = importlib.util.spec_from_file_location("report_task_inventory", ROOT / "scripts/report_task_inventory.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TaskInventoryDocumentTests(unittest.TestCase):
    def test_committed_inventory_matches_the_registry(self):
        rendered = MODULE.render(MODULE.build_rows())
        self.assertEqual(
            (ROOT / "TASKS.md").read_text(), rendered,
            "TASKS.md is stale: run python scripts/report_task_inventory.py",
        )

    def test_every_registered_task_has_exactly_one_row(self):
        text = (ROOT / "TASKS.md").read_text()
        names = re.findall(r"^\| \[`([A-Za-z0-9]+)`\]\(benchmarks/", text, re.M)
        expected = sorted(spec.task_id.split("/")[-1] for spec in list_tasks(None))
        self.assertEqual(sorted(names), expected)

    def test_no_task_is_left_unmapped(self):
        rows = MODULE.build_rows()
        self.assertEqual([r["task_id"] for r in rows if r["form"] == "unmapped"], [])
        self.assertNotIn("未映射", (ROOT / "TASKS.md").read_text())


if __name__ == "__main__":
    unittest.main()
