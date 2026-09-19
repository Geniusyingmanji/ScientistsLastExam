"""The README's headline counts are a test, not a comment.

`sle/conf/exam_taxonomy.yaml` opens with "Counts are a test, not a comment", and `TASKS.md` is
generated so its table cannot drift. The README paragraph that introduces the two task forms was
the one place the same numbers were maintained by hand, and it drifted: it said 61 task packages,
29 optimization and 32 discovery while the registry held 85, 42 and 43, and it described the
optimization side as three categories after `certificate_bound` had become a fourth.

This reads the numbers back out of the prose and compares them with the registry, so the next
person to add a task finds out here rather than in a stale front page. It deliberately does not
regenerate the README: the prose around each number is written, not templated, and a generator
for it belongs with the one in `scripts/report_task_inventory.py`.
"""
from __future__ import annotations

import collections
import pathlib
import re
import unittest

import yaml

from sle.certification import certification_status
from sle.registry import list_tasks

ROOT = pathlib.Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
TAXONOMY = ROOT / "sle" / "conf" / "exam_taxonomy.yaml"


def _readme() -> str:
    return README.read_text(encoding="utf-8")


# The README writes small category counts as Chinese numerals where they read as words.
CHINESE_DIGITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _only(pattern: str) -> str:
    """The single substring a pattern names, failing loudly when the prose moved."""
    found = re.findall(pattern, _readme())
    if len(found) != 1:
        raise AssertionError(
            "expected exactly one match for %r in README.md, found %d: %r"
            % (pattern, len(found), found))
    return found[0]


def _one(pattern: str) -> int:
    found = _only(pattern)
    return CHINESE_DIGITS[found] if found in CHINESE_DIGITS else int(found)


class ReadmeInventoryCountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task_ids = [spec.task_id for spec in list_tasks(None)]
        cls.taxonomy = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))["tasks"]
        cls.status = collections.Counter(
            certification_status(task_id) for task_id in cls.task_ids)
        cls.form = collections.Counter(
            cls.taxonomy[task_id]["form"] for task_id in cls.task_ids)
        cls.analogue = collections.Counter(
            cls.taxonomy[task_id].get("analogue") for task_id in cls.task_ids
            if cls.taxonomy[task_id]["form"] == "optimization")
        cls.kind = collections.Counter(
            cls.taxonomy[task_id].get("kind") for task_id in cls.task_ids
            if cls.taxonomy[task_id]["form"] == "discovery")

    def test_headline_totals(self):
        self.assertEqual(_one(r"当前 (\d+) 个任务包"), len(self.task_ids))
        self.assertEqual(
            _one(r"当前 \d+ 个任务包,横跨 (\d+) 个学科"),
            len({task_id.split("/")[0] for task_id in
                 (spec.task_dir.relative_to(ROOT / "benchmarks").as_posix()
                  for spec in list_tasks(None))}))
        headline = _only(r"当前 \d+ 个任务包,横跨 \d+ 个学科,([^。]+)。")
        self.assertEqual(
            int(re.search(r"(\d+) 个 certified", headline).group(1)),
            self.status["certified"])
        self.assertEqual(
            int(re.search(r"(\d+) 个 candidate", headline).group(1)),
            self.status["candidate"])

    def test_form_totals(self):
        self.assertEqual(_one(r"optimization\((\d+) 个\)"), self.form["optimization"])
        self.assertEqual(self.form["discovery"], 0)

    def test_optimization_categories(self):
        self.assertEqual(_one(r"工程设计\(.*?等 (\d+) 题\)"), self.analogue["engineering_design"])
        self.assertEqual(_one(r"张量秩、超排列等 (\d+) 题"), self.analogue["combinatorial"])
        self.assertEqual(_one(r"分子与大分子设计\((\d+) 题\)"), self.analogue["molecular_design"])
        self.assertEqual(_one(r"证书上界\((\d+) 题"), self.analogue["certificate_bound"])
        named = {"engineering_design", "combinatorial", "molecular_design", "certificate_bound"}
        self.assertEqual(set(self.analogue) - {None}, named,
                         "a new optimization analogue needs its own sentence in README.md")
        self.assertEqual(_one(r"optimization\(\d+ 个\):在受约束的设计空间里把目标做得更好。分(.)类:"),
                         len(named), "the category count word disagrees with the categories")

    def test_discovery_categories(self):
        self.assertEqual(dict(self.kind), {}, "discovery task kinds belong on main")


if __name__ == "__main__":
    unittest.main()
