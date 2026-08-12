"""The task identity hash must not depend on whether the task has been run.

Several task directories accumulate a `runs/` directory when executed. It was inside the hash,
so a task's recorded identity changed every time somebody ran it: eleven tasks in this repository
carry manifest hashes that no committed revision reproduces, and the comparability guard in the
reports read two runs of an unedited task as two different versions of it.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from frontier_science.algorithms.common import task_package_sha256


class Spec:
    def __init__(self, task_dir: Path):
        self.task_dir = task_dir


def build(root: Path) -> Path:
    task = root / "task"
    (task / "verification").mkdir(parents=True)
    (task / "Task.md").write_text("ask", encoding="utf-8")
    (task / "verification" / "evaluator.py").write_text("score = 1", encoding="utf-8")
    return task


class TaskPackageHashTests(unittest.TestCase):
    def test_running_the_task_does_not_change_its_identity(self):
        with TemporaryDirectory() as tmp:
            task = build(Path(tmp))
            before = task_package_sha256(Spec(task))
            (task / "runs" / "seed_0").mkdir(parents=True)
            (task / "runs" / "seed_0" / "trajectory.jsonl").write_text("{}", encoding="utf-8")
            self.assertEqual(task_package_sha256(Spec(task)), before)

    def test_caches_are_still_excluded(self):
        with TemporaryDirectory() as tmp:
            task = build(Path(tmp))
            before = task_package_sha256(Spec(task))
            (task / "__pycache__").mkdir()
            (task / "__pycache__" / "x.pyc").write_bytes(b"\x00")
            self.assertEqual(task_package_sha256(Spec(task)), before)

    def test_editing_the_evaluator_does_change_it(self):
        """The exclusion must not be so broad that a real edit slips through."""
        with TemporaryDirectory() as tmp:
            task = build(Path(tmp))
            before = task_package_sha256(Spec(task))
            (task / "verification" / "evaluator.py").write_text("score = 2", encoding="utf-8")
            self.assertNotEqual(task_package_sha256(Spec(task)), before)

    def test_a_file_merely_named_runs_is_not_excluded(self):
        """Only directories are generated output; a `runs.py` is source."""
        with TemporaryDirectory() as tmp:
            task = build(Path(tmp))
            before = task_package_sha256(Spec(task))
            (task / "runs.py").write_text("real source", encoding="utf-8")
            self.assertNotEqual(task_package_sha256(Spec(task)), before)


if __name__ == "__main__":
    unittest.main()
