"""The table that says which recorded task hashes are the same task.

A declarative line added to every task's card moved every hash, and the identity hash used to
include the task's own run output, so twenty tasks looked edited when sixteen were untouched. The
reports compare on the class this returns, so what it does when it knows nothing matters as much
as what it does when it does.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sle.task_versions import version_class


def write_table(root: Path, body: str) -> Path:
    path = root / "task_versions.yaml"
    path.write_text(body, encoding="utf-8")
    return path


class TaskVersionTableTests(unittest.TestCase):
    def test_two_hashes_in_one_class_compare_as_one_version(self):
        with TemporaryDirectory() as tmp:
            table = write_table(Path(tmp), """
tasks:
  Astro/LowThrust:
    classes:
      - id: LowThrust-0
        versions: [aaa, bbb]
""")
            self.assertEqual(version_class("Astro/LowThrust", "aaa", table),
                             version_class("Astro/LowThrust", "bbb", table))

    def test_two_classes_stay_apart(self):
        with TemporaryDirectory() as tmp:
            table = write_table(Path(tmp), """
tasks:
  Chem/Lead:
    classes:
      - id: Lead-0
        versions: [aaa]
      - id: Lead-1
        versions: [bbb]
""")
            self.assertNotEqual(version_class("Chem/Lead", "aaa", table),
                                version_class("Chem/Lead", "bbb", table))

    def test_an_unknown_hash_maps_to_itself_rather_than_to_a_shared_bucket(self):
        """Two hashes nobody has established anything about are not thereby the same task."""
        with TemporaryDirectory() as tmp:
            table = write_table(Path(tmp), "tasks: {}\n")
            self.assertEqual(version_class("T/X", "aaa", table), "aaa")
            self.assertNotEqual(version_class("T/X", "aaa", table),
                                version_class("T/X", "bbb", table))

    def test_a_class_does_not_leak_across_tasks(self):
        with TemporaryDirectory() as tmp:
            table = write_table(Path(tmp), """
tasks:
  A/One:
    classes:
      - id: One-0
        versions: [shared]
""")
            self.assertEqual(version_class("A/One", "shared", table), "One-0")
            self.assertEqual(version_class("B/Two", "shared", table), "shared")

    def test_a_missing_table_changes_nothing(self):
        with TemporaryDirectory() as tmp:
            missing = Path(tmp) / "absent.yaml"
            self.assertEqual(version_class("T/X", "aaa", missing), "aaa")


if __name__ == "__main__":
    unittest.main()
