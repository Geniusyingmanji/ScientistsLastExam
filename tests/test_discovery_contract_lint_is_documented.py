"""Discovery prompts must name the free shape-checker that the sandbox already mounts.

A candidate that does not know `sle.contract_lint` exists will keep failing on submission
shape, and those zeros look like scientific difficulty. Floor-task Task.md files already
named it; the rest of the discovery inventory did not.
"""
from __future__ import annotations

import unittest

from sle.registry import list_tasks


class DiscoveryContractLintDocumentedTests(unittest.TestCase):
    def test_every_discovery_task_md_names_contract_lint(self):
        missing = []
        for spec in list_tasks(None):
            if str(spec.metadata.get("scientific_role", "")) != "discovery":
                continue
            path = spec.task_dir / "Task.md"
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
            if "contract_lint" not in text:
                missing.append(spec.task_id)
        self.assertEqual(missing, [], "discovery Task.md missing sle.contract_lint")


if __name__ == "__main__":
    unittest.main()
