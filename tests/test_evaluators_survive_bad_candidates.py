"""A candidate must never be able to crash the trusted evaluator.

A candidate that raises, returns nonsense, or returns nothing scores zero. It is not an
infrastructure failure - and the difference is expensive, because an infrastructure failure aborts
the whole run. One badly-shaped submission then costs a cohort its evidence rather than earning a
zero, and the operator gets a report saying the campaign failed when a proposal did.

A 129-block paired sweep came back with four terminal failures on two tasks, all reading only
`trusted evaluator internal failure`. The cause was a `KeyError` inside the evaluator: the row it
builds when scoring a world raises carried fewer keys than the row it builds when scoring
succeeds, and an aggregation added later read one of the missing ones. A third task raised out of
`float()` when a controller returned a dictionary.

The authority on this property is `scripts/check_evaluator_survives_bad_candidates.py`, which
feeds every evaluator a candidate that fails and asks what happens. That is too slow for a unit
test - it is a sandboxed evaluation per task - and it is also the only thing that can answer the
question, because whether a missing key matters depends on which list the aggregation walks.

A first version of this file asserted the structural invariant across the inventory instead:
failure rows carry every key scored rows do. It flagged five tasks the executable check had just
cleared. Asserting an invariant stricter than the property it stands in for buys nothing and costs
a red suite, so this pins the regressions that were actually diagnosed and fixed, and leaves
coverage to the check that can measure it.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sle.registry import list_tasks  # noqa: E402

# Keys a failure row may legitimately carry alone: they exist to say *why* it failed.
FAILURE_ONLY = {"reason", "failure_kind", "error", "error_message"}


def _instance_rows(tree: ast.AST) -> tuple[list[set[str]], list[set[str]]]:
    """Key sets of the per-instance rows, split by the literal `valid` they carry.

    A per-instance row is identified by carrying a literal `valid` - that is what tells the
    aggregation whether the world was scored - which keeps summary dictionaries and metric
    dictionaries out of the comparison.
    """
    good, bad = [], []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys, literal = set(), None
        for key, value in zip(node.keys, node.values):
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                continue
            keys.add(key.value)
            if key.value == "valid" and isinstance(value, ast.Constant):
                literal = value.value
        if literal is True:
            good.append(keys)
        elif literal is False:
            bad.append(keys)
    return good, bad


class EvaluatorRowShapeTests(unittest.TestCase):
    def test_the_two_tasks_this_was_found_on_carry_the_key_that_broke(self):
        """`abstained` is read by `discovery_coverage`, which was added after the failure rows.

        Four runs died and a 129-block campaign's report was invalidated because these two rows
        lacked it.
        """
        for name in ("ReactionMechanismFitting", "GravityInversion"):
            path = next(p for p in (ROOT / "benchmarks").rglob(
                "%s/verification/evaluator.py" % name))
            _good, bad = _instance_rows(ast.parse(path.read_text(encoding="utf-8")))
            self.assertTrue(bad, name)
            for keys in bad:
                self.assertIn("abstained", keys, name)

    def test_the_pendulum_separates_a_bad_controller_from_a_broken_evaluator(self):
        """It had no failure path at all: a controller returning a dictionary raised out of
        `float()` and was reported as an infrastructure failure, aborting the run."""
        path = next((ROOT / "benchmarks").rglob(
            "InvertedPendulumSwingUp/verification/evaluator.py"))
        source = path.read_text(encoding="utf-8")
        self.assertIn("class CandidateFailure", source)
        tree = ast.parse(source)
        raised = {node.exc.func.id for node in ast.walk(tree)
                  if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)
                  and isinstance(node.exc.func, ast.Name)}
        self.assertNotIn(
            "ValueError", raised,
            "a bare ValueError here reaches the harness as an infrastructure failure, which "
            "aborts the run instead of scoring the candidate zero")


if __name__ == "__main__":
    unittest.main()
