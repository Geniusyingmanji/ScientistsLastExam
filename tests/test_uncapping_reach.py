"""The carry-forward argument must not clear a key it cannot see the computation of.

Removing an upper clip changes a score only when the score exceeded 1.0, so most recorded evidence
is provably unaffected and can be carried across the edit without a re-run. The temptation is to
push that argument further than it goes.

One version did. It settled each metric key by asking git whether the *line* holding it had been
edited, and reported that every recorded run could be carried forward. That is contradicted by
direct measurement: `check_evaluator_inert.py` found the frozen `DiffractionGratingDesign`
artifact's `robustness_score` moving once the clip came off. The line reads
`"robustness_score": robustness_score` - untouched, and meaningless, because the clip lives in a
helper the line cannot see.

These tests pin the conservative direction. Over-reporting costs a re-measurement; under-reporting
carries a stale number forward as though it had been checked.
"""
from __future__ import annotations

import ast
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "uncapping_reach", ROOT / "scripts" / "report_uncapping_reach.py")
reach = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reach)


def _value(source: str) -> ast.AST:
    """The single dictionary value in a one-entry dict literal."""
    tree = ast.parse(source, mode="eval")
    return tree.body.values[0]


class SelfContainmentTests(unittest.TestCase):
    def test_a_bare_name_is_not_self_contained(self):
        self.assertFalse(reach._self_contained(_value('{"robustness_score": robustness_score}')))

    def test_a_call_to_a_local_helper_is_not_self_contained(self):
        self.assertFalse(reach._self_contained(_value('{"score": _mean(rows, "score")}')))

    def test_a_reduction_over_a_local_list_is_not_self_contained(self):
        """`development` is built elsewhere, so this line's history says nothing about the value."""
        self.assertFalse(reach._self_contained(
            _value('{"feasibility_rate": float(np.mean([r["valid"] for r in development]))}')))

    def test_a_literal_is_self_contained(self):
        self.assertTrue(reach._self_contained(_value('{"robustness_score": 0.0}')))

    def test_a_comprehension_binding_its_own_names_is_self_contained(self):
        self.assertTrue(reach._self_contained(
            _value('{"n": len([x for x in range(3) if x])}')))


class ReachTests(unittest.TestCase):
    def test_the_known_moving_key_is_never_cleared_by_line_history(self):
        """DiffractionGratingDesign's `robustness_score` is the measured counterexample."""
        evaluator = next(
            path for path in (ROOT / "benchmarks").rglob(
                "DiffractionGratingDesign/verification/evaluator.py"))
        self.assertNotIn(
            "robustness_score", reach._key_lines(evaluator),
            "robustness_score was offered up for line-history clearance, but its value is "
            "computed in a helper and it is measured to move when the clip is removed")

    def test_bookkeeping_keys_are_never_treated_as_scores(self):
        for name in ("valid", "infrastructure_failure"):
            self.assertIn(name, reach.BOOKKEEPING)


if __name__ == "__main__":
    unittest.main()
