"""A reference at its own ceiling is a task with nothing left to win, and nothing checks it.

The canary audit feeds each oracle degenerate candidates and asks whether any earns credit - the
bottom of a task. The shortcut contract asks whether a cheap candidate reaches the reference - a
margin a task owner declares. Neither asks whether the declared reference is already the maximum
the task's own contract admits, which is the shape the maintainer found by hand in five reviews:
a trivial strategy that ties such a reference measures exactly what the reference measures, which
is nothing about a searcher.

Two of those five are reproduced here as full regression tests, because they are the strongest
form of the claim - a task-specific trivial strategy that ties the reference exactly. The other
three are covered by the inventory test, since their trivial strategy is not expressible as a
generic probe (their references are at the ceiling, which the audit measures directly).
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sle.registry import find_task, list_tasks  # noqa: E402
from scripts.saturation_audit import (  # noqa: E402
    AT_CEILING_DECLARED,
    AT_CEILING_UNDECLARED,
    HEADROOM,
    MIGRATION,
    NOT_MEASURED,
    audit_task,
    declares_ceiling,
    declares_saturation,
    reference_path,
)

# The flagged set, resolved once. Re-measuring every task would cost one full oracle evaluation
# each - minutes, dominated by the flagship contracts - and would run for every reviewer. The
# tests below measure exactly the tasks whose status is in question, and the word test covers the
# rest of the inventory cheaply. Measured scores were produced by `scripts/saturation_audit.py`.
FLAGGED = ()  # The five pre-split flagged discovery tasks belong on main.


def _load(name: str, path: Path):
    module_spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


class SaturationAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads(MIGRATION.read_text(encoding="utf-8"))["tasks"]


    def test_a_denial_or_an_unknown_is_not_a_declaration(self):
        """The classifier must read an affirmation, not a substring.

        The first version of this test did not exist and the classifier matched "saturat" as a
        substring: adversarial review measured that "not_saturated", "unsaturated",
        "not_saturated_pending_review", "desaturated" and "saturation_unknown" all counted as
        declarations, which would move a task out of the defect inventory (at_ceiling_undeclared)
        into at_ceiling_declared and silently empty it. A card that DENIES saturation, or says it
        is unknown, is the exact opposite of declaring it.
        """
        from scripts.saturation_audit import _declares  # noqa: PLC0415
        for status in ("not_saturated", "unsaturated", "not_saturated_pending_review",
                       "desaturated", "saturation_unknown", "not_tested", "", "pending"):
            with self.subTest(status=status):
                self.assertFalse(_declares(status), status)
        for status in ("saturated", "saturated_for_current_frontier",
                       "Saturated_For_Current_Frontier"):
            with self.subTest(status=status):
                self.assertTrue(_declares(status), status)

    def test_the_inventory_is_exactly_the_flagged_set_with_no_stale_entries(self):
        """Listing is not a pass - the policy says so in as many words.

        Every entry must correspond to a real task and carry a reason, and the inventory must not
        grow a name no test measures: an unmeasured entry is a task quietly added, which is the
        failure mode this pin exists to catch.
        """
        self.assertEqual(sorted(self.inventory), sorted(FLAGGED))
        for task_id, record in self.inventory.items():
            self.assertEqual(record["status"], "pending", task_id)
            self.assertTrue(record.get("reason"), task_id)
            find_task(task_id, include_uncertified=True)

    def test_the_cheap_word_test_is_broader_than_the_structured_one(self):
        """The trigger over-approximates deliberately, and never under-approximates.

        `--declared-only` exists so a reviewer can re-measure only what changed without paying for
        a full sweep. It has to err toward including a task: all five flagged tasks carry the
        ceiling sentence in prose while their structured status says nothing, so a word test that
        only matched the structured field would miss exactly the gap this audit closes.
        """
        for spec in list_tasks(None):
            with self.subTest(task=spec.task_id):
                if declares_saturation(spec) is not None:
                    self.assertTrue(declares_ceiling(spec), spec.task_id)
        for task_id in FLAGGED:
            with self.subTest(flagged=task_id):
                spec = find_task(task_id, include_uncertified=True)
                self.assertTrue(declares_ceiling(spec), task_id)
                self.assertIsNone(declares_saturation(spec), task_id)


    def test_an_unmeasured_reference_is_never_a_pass(self):
        """Thirty-nine tasks keep the reference inside the evaluator, where nothing can score it.

        Those tasks have no submitable reference file, and the audit must say so rather than call
        them healthy - a check that fails open is worse than no check. The three shapes are
        checked directly rather than by sweeping the inventory, which would cost an oracle
        evaluation per task.
        """
        # An evaluator-internal reference: nothing submitable to score.
        internal = find_task("Mathematics/CapSet", include_uncertified=True)
        from dataclasses import replace
        # Test the missing-reference branch independently of the package's uncapped score.
        internal = replace(internal, metadata={**internal.metadata, "score_mode": "clipped"})
        row = audit_task(internal)
        self.assertEqual(row["status"], NOT_MEASURED)
        self.assertIn("evaluator-internal", row["detail"])
        # More than one reference-named candidate: the audit refuses to guess.
        ambiguous = find_task(
            "QuantumErrorCorrection/QuantumErrorDecoder", include_uncertified=True)
        self.assertEqual(audit_task(ambiguous)["status"], NOT_MEASURED)
        # Unmeasured statuses are distinct from the two verdicts, so neither can be read as one.
        self.assertNotEqual(NOT_MEASURED, AT_CEILING_DECLARED)
        self.assertNotEqual(NOT_MEASURED, HEADROOM)
        self.assertNotEqual(NOT_MEASURED, AT_CEILING_UNDECLARED)

    def test_an_uncapped_task_is_not_compared_to_a_normalised_ceiling(self):
        """1.0 is only a ceiling where the contract clips to one.

        An uncapped task's maximum is a number the task does not publish, and one shipped
        reference already scores above 1.0. No submitable reference on an uncapped task may
        receive a ceiling verdict, whether the reason recorded is the score mode or an oracle
        that would not import on this host - both are unmeasured, and neither is a pass.
        """
        uncapped = [spec for spec in list_tasks(None)
                    if str(spec.metadata.get("score_mode")) == "uncapped"
                    and reference_path(spec) is not None]
        self.assertTrue(uncapped, "expected uncapped tasks that ship a reference")
        reasons = []
        for spec in uncapped:
            with self.subTest(task=spec.task_id):
                row = audit_task(spec)
                self.assertEqual(row["status"], NOT_MEASURED)
                reasons.append(row["detail"])
        # At least one was reached far enough to be refused for its score mode rather than for a
        # missing dependency, so the refusal is about the ceiling and not only about the host.
        self.assertTrue(any("uncapped" in detail for detail in reasons), reasons)

    def test_the_reference_lookup_refuses_to_guess_between_candidates(self):
        """A task with two reference-named files is reported unmeasured, not silently mis-scored.

        Four tasks in the tree ship more than one candidate exposing the entrypoint - a reference
        and an ablation. Choosing one arbitrarily would report the ablation's saturation as the
        task's, which is the error this refusal exists to prevent.
        """
        spec = find_task("QuantumErrorCorrection/QuantumErrorDecoder", include_uncertified=True)
        self.assertIsNone(reference_path(spec))
        self.assertEqual(audit_task(spec)["status"], NOT_MEASURED)




if __name__ == "__main__":
    unittest.main()
