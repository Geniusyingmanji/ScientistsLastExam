"""No oracle may draw from a generator it has not pinned.

The whole benchmark rests on an evaluator being a function: the same candidate scores the same
number. A community routine can break that quietly. ViennaRNA's designers, handed `None` as the
start sequence, draw one from a process-global generator inside the C library that Python's
`random.Random` does not reach - so seeding the task's own RNG looks like enough and is not.

On RNAEnsembleDesign that surfaced as a task failing the determinism sweep while reproducing
perfectly when re-run by hand. The wandering anchor defects were the harmless half. The damaging
half was that a target whose anchor sat near the edge of the acceptance band flipped in and out of
the set between runs, so *which instances existed* changed and two scores were not comparable at
all.

This scans the inventory rather than that one task, because the next oracle to reach for a
community routine with private random state will not announce itself.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sle.registry import list_tasks  # noqa: E402

# Routines that draw from a library-internal generator when their start argument is None.
UNSEEDED_WHEN_NONE = {"inverse_fold", "inverse_pf_fold"}

# Calls that pin such a generator. A file that never draws never needs one.
SEEDING_CALLS = {"init_rand", "srandom", "seed", "_seed_rna"}


def _oracle_sources():
    for spec in list_tasks(None):
        verification = spec.task_dir / "verification"
        if not verification.is_dir():
            continue
        for path in sorted(verification.rglob("*.py")):
            yield spec.task_id, path


def _call_name(node: ast.Call) -> str:
    function = node.func
    if isinstance(function, ast.Attribute):
        return function.attr
    if isinstance(function, ast.Name):
        return function.id
    return ""


def _starts_from_none(node: ast.Call) -> bool:
    return bool(node.args) and isinstance(node.args[0], ast.Constant) and node.args[0].value is None


class OracleRandomnessTests(unittest.TestCase):
    def test_no_oracle_draws_from_an_unpinned_library_generator(self):
        offenders = []
        for task_id, path in _oracle_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
            drawing = [node for node in calls
                       if _call_name(node) in UNSEEDED_WHEN_NONE and _starts_from_none(node)]
            if not drawing:
                continue
            seeds = any(_call_name(node) in SEEDING_CALLS for node in calls)
            if not seeds:
                offenders.append("%s: %s draws from an unpinned generator" % (
                    task_id, path.relative_to(ROOT)))
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_the_known_case_seeds_every_drawing_call_site(self):
        """RNAEnsembleDesign is the task this was found on, so it is pinned by name too.

        The inventory scan above only asks whether a file seeds *somewhere*. That is the right
        question to ask of code nobody has read yet, and the wrong question to ask of the case
        already known to be delicate: here every drawing call has to be immediately preceded by a
        seed, or a later call inherits whatever state the previous one left.
        """
        spec = next(s for s in list_tasks(None) if s.task_id.endswith("/RNAEnsembleDesign"))
        source = (spec.task_dir / "verification" / "evaluator.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        for function in [node for node in ast.walk(tree)
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            body = list(ast.walk(function))
            drawing = [node for node in body
                       if isinstance(node, ast.Call)
                       and _call_name(node) in UNSEEDED_WHEN_NONE
                       and _starts_from_none(node)]
            if not drawing:
                continue
            seeded_lines = {node.lineno for node in body
                            if isinstance(node, ast.Call) and _call_name(node) in SEEDING_CALLS}
            for call in drawing:
                self.assertTrue(
                    any(0 < call.lineno - line <= 3 for line in seeded_lines),
                    "%s draws at line %d with no seed in the three lines above it"
                    % (function.name, call.lineno),
                )

    def test_the_seed_is_derived_from_the_call_inputs_not_the_clock(self):
        """A seed taken from the clock or the process id is not a seed, it is a fresh draw."""
        spec = next(s for s in list_tasks(None) if s.task_id.endswith("/RNAEnsembleDesign"))
        source = (spec.task_dir / "verification" / "evaluator.py").read_text(encoding="utf-8")
        for forbidden in ("time.time()", "os.getpid()", "time.time_ns()", "uuid"):
            self.assertNotIn(forbidden, source)
        self.assertIn("hashlib.sha256", source)


if __name__ == "__main__":
    unittest.main()
