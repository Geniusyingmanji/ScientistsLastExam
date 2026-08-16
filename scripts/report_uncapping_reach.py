#!/usr/bin/env python3
"""Which recorded numbers could the uncapping have moved?

Removing an upper clip changes `clip(expr, 0, 1)` into `max(expr, 0)`. The two differ on exactly
one input: `expr > 1`. Every other candidate scores identically before and after, which means most
recorded evidence is unaffected by the edit and can say so with an argument rather than a re-run.

A recorded reading that sits strictly below 1.0 was never clipped, so the edit provably cannot have
moved it. A reading of exactly 1.0 is the ambiguous case: it may be a genuine 1.0, or it may be a
larger number the old clip flattened. Those, and only those, need re-measuring.

Two refinements make the split usable, and neither needs to read the evaluator.

First: a reading below 1.0 is unaffected *either way*. If its key was never clipped, the edit did
not touch it; if its key was clipped, the clip did not bind at that value. So no knowledge of
which key is which is required to clear it, and being wrong about a key can only make this report
more conservative, never less.

Second: a key that any recorded reading *exceeds* 1.0 on was never clipped at 1.0 - a clip would
have made that reading impossible. That single observation clears the counts and call tallies
(`candidate_instance_call_count`, `candidate_parameter_count`) which otherwise dominate the
ambiguous set and have nothing to do with scoring.

What the numbers cannot settle is a key whose readings top out at exactly 1.0 and never pass it. A
rate is bounded by being a fraction and a clipped score is bounded by the clip, and the two look
identical from outside. Reading the evaluator to trace which keys a helper feeds is possible but
fiddly - the clip usually sits several calls below the dictionary - and easy to get quietly wrong.

The history helps, but only where the line tells the whole story. For a key whose dictionary entry
computes its value in place, `git log -L` on that line settles it: a line nobody edited cannot have
been uncapped, whatever it computes. For a key written as `"robustness_score": robustness_score`
the line says nothing - the clip lives in a helper several frames down, and that helper is exactly
what the uncapping edited. An earlier version of this script cleared such keys anyway and reported
zero runs needing re-measurement, which is contradicted by direct measurement: the frozen
`DiffractionGratingDesign` artifact's `robustness_score` did cross 1.0 once the clip came off.

So the history clears a key only when its value expression is self-contained - no name that some
assignment elsewhere could have redefined. Everything else stays ambiguous and is named. This is
deliberately the conservative side of the line: over-reporting costs a re-measurement, while
under-reporting silently carries stale numbers forward.

Evidence is carried forward a run at a time, so runs are what is counted.

Usage:
    python scripts/report_uncapping_reach.py --output .research/uncapping_reach.json
"""
from __future__ import annotations

import argparse
import ast
import builtins
import glob
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from sle.registry import list_tasks  # noqa: E402

# Never treated as a score: present in nearly every metrics dictionary and never clipped.
BOOKKEEPING = {"valid", "infrastructure_failure", "difficulty", "oracle_calls", "budget_units"}


def _uncapped_tasks() -> dict[str, Path]:
    out = {}
    for spec in list_tasks(None):
        metadata = spec.task_dir / "frontier_eval" / "metadata.yaml"
        if not metadata.is_file():
            continue
        document = yaml.safe_load(metadata.read_text(encoding="utf-8")) or {}
        if document.get("score_mode") == "uncapped":
            out[spec.task_id] = spec.task_dir / "verification" / "evaluator.py"
    return out


_SOURCE_CACHE: dict[Path, str] = {}


def _source_text(path: Path) -> str:
    if path not in _SOURCE_CACHE:
        try:
            _SOURCE_CACHE[path] = path.read_text(encoding="utf-8")
        except OSError:
            _SOURCE_CACHE[path] = ""
    return _SOURCE_CACHE[path]


def _self_contained(value: ast.AST) -> bool:
    """Does this expression compute its result here, with nothing an edit elsewhere could change?

    Every name it reads must be a builtin, an imported module alias, or a variable the expression
    itself binds in a comprehension. A reference to anything assigned elsewhere - a helper, an
    intermediate list, a per-instance record - means the value is produced somewhere this line
    cannot see, and the line's history says nothing about it.
    """
    bound = {target.id
             for node in ast.walk(value)
             if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp))
             for generator in node.generators
             for target in ast.walk(generator.target)
             if isinstance(target, ast.Name)}
    for node in ast.walk(value):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in bound or node.id in dir(builtins):
                continue
            return False
    return True


def _key_lines(path: Path) -> dict[str, int]:
    """Line number of each metric key that is self-contained at *every* place it is written.

    Every place matters. An evaluator typically writes each metric twice: once where it is
    computed and once in the branch that fires when the candidate is invalid, where it is a
    literal. `"robustness_score": 0.0` is self-contained and says nothing about
    `"robustness_score": robustness_score` twenty lines up, which is where the clip that moved it
    actually lived. Taking the first self-contained occurrence let the trivial branch vouch for
    the real one, so a key is offered here only when no occurrence of it hides a computation.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return {}
    lines: dict[str, int] = {}
    opaque: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                continue
            if _self_contained(value):
                lines.setdefault(key.value, getattr(value, "lineno", key.lineno))
            else:
                opaque.add(key.value)
    return {name: line for name, line in lines.items() if name not in opaque}


def _line_changed_since(path: Path, line: int, revision: str) -> Optional[bool]:
    """Has this one line been edited since `revision`? None when git cannot say."""
    if not revision:
        return None
    relative = path.relative_to(ROOT).as_posix()
    result = subprocess.run(
        ["git", "log", "--format=%H", "-L", "%d,%d:%s" % (line, line, relative),
         "%s..HEAD" % revision],
        cwd=str(ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return any(row.strip() for row in result.stdout.splitlines() if len(row.strip()) == 40)


def _is_lower_bound_only(node: ast.AST) -> bool:
    """`max(expr, 0.0)` - a floor with no ceiling - anywhere inside this expression."""
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        name = getattr(child.func, "id", None) or getattr(child.func, "attr", None)
        if name == "max" and len(child.args) == 2:
            for argument in child.args:
                if isinstance(argument, ast.Constant) and argument.value in (0, 0.0):
                    return True
        # np.clip(expr, 0.0, 1.0) keeps a ceiling, so a key built with it is still capped.
        if name == "clip":
            return False
    return False


def uncapped_keys(path: Path) -> set[str]:
    """Metric keys whose value is built with a floor and no ceiling."""
    if not path.is_file():
        return set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                if key.value not in BOOKKEEPING and _is_lower_bound_only(value):
                    keys.add(key.value)
    return keys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args(argv)

    tasks = _uncapped_tasks()

    # First pass: which keys does any recorded reading exceed 1.0 on? Those were never clipped
    # there, so every reading on them is unaffected by the edit.
    exceeds_one: set[str] = set()
    documents = []
    for path in sorted(glob.glob(str(ROOT / "experiments" / "*.json"))):
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(document, dict) or not isinstance(document.get("runs"), list):
            continue
        documents.append((Path(path).name, document))
        for run in document["runs"]:
            if not isinstance(run, dict) or run.get("task") not in tasks:
                continue
            for event in (run.get("trajectory_snapshot") or {}).get("events") or []:
                if not isinstance(event, dict):
                    continue
                for key, value in (event.get("metrics") or {}).items():
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        continue
                    if value > 1.0:
                        exceeds_one.add(key)

    ambiguous = Counter()
    provable = Counter()
    clean_runs, ambiguous_runs = Counter(), Counter()
    ambiguous_keys = Counter()
    ambiguous_files = defaultdict(set)

    key_lines = {task: _key_lines(path) for task, path in tasks.items()}
    settled: dict[tuple, Optional[bool]] = {}
    untouched_keys, touched_keys, undecided_keys = set(), set(), set()

    def _still_ambiguous(task: str, key: str, revision: str) -> bool:
        """A key on a line nobody has edited since the evidence was taken is not ambiguous."""
        cache_key = (task, key, revision)
        if cache_key not in settled:
            line = key_lines.get(task, {}).get(key)
            if line:
                changed = _line_changed_since(tasks[task], line, revision)
            elif key not in _source_text(tasks[task]):
                # The evaluator never names this key, so the harness put it there - `timeout` is
                # the case in hand. An edit to an evaluator cannot have moved a number that
                # evaluator does not produce. Checked against the source rather than a list of
                # known harness fields, so a new one needs no maintenance here.
                changed = False
            else:
                changed = None
            settled[cache_key] = changed
        changed = settled[cache_key]
        if changed is False:
            untouched_keys.add((task, key))
            return False
        (touched_keys if changed else undecided_keys).add((task, key))
        return True

    for name, document in documents:
        revision = str((document.get("source_provenance") or {}).get("git_revision") or "")
        for run in document["runs"]:
            if not isinstance(run, dict):
                continue
            task = run.get("task")
            if task not in tasks:
                continue
            hit = False
            for event in (run.get("trajectory_snapshot") or {}).get("events") or []:
                if not isinstance(event, dict):
                    continue
                for key, value in (event.get("metrics") or {}).items():
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        continue
                    if key in BOOKKEEPING or key in exceeds_one:
                        continue
                    if value < 1.0:
                        provable[task] += 1
                    elif _still_ambiguous(task, key, revision):
                        ambiguous[task] += 1
                        ambiguous_keys[key] += 1
                        ambiguous_files[task].add(name)
                        hit = True
                    else:
                        provable[task] += 1
            if hit:
                ambiguous_runs[task] += 1
            else:
                clean_runs[task] += 1

    report = {
        "schema_version": 1,
        "purpose": "how far the uncapping edit can reach into recorded evidence",
        "argument": (
            "clip(expr, 0, 1) and max(expr, 0) differ only when expr > 1, which a recorded "
            "reading shows as exactly 1.0. A reading below 1.0 is provably unaffected either "
            "way. A key that some reading exceeds 1.0 on was never clipped there. What is left - "
            "a key topping out at exactly 1.0 - cannot be told apart from a bounded rate by the "
            "numbers alone, and is reported rather than assumed."
        ),
        "keys_proved_unclipped_by_a_reading_above_one": sorted(exceeds_one),
        "keys_on_lines_untouched_since_their_evidence": sorted(
            "%s|%s" % pair for pair in untouched_keys),
        "keys_on_lines_edited_since_their_evidence": sorted(
            "%s|%s" % pair for pair in touched_keys),
        "keys_whose_history_git_could_not_answer": sorted(
            "%s|%s" % pair for pair in undecided_keys),
        "uncapped_task_count": len(tasks),
        "carryable_run_count": sum(clean_runs.values()),
        "run_needing_remeasurement_count": sum(ambiguous_runs.values()),
        "carryable_runs_by_task": dict(sorted(clean_runs.items())),
        "runs_needing_remeasurement_by_task": dict(sorted(ambiguous_runs.items())),
        "provably_unaffected_readings": sum(provable.values()),
        "ambiguous_readings": sum(ambiguous.values()),
        "ambiguous_readings_by_key": dict(ambiguous_keys.most_common(20)),
        "tasks_needing_remeasurement": sorted(ambiguous_runs),
        "evidence_files_holding_ambiguous_readings": sorted(
            {name for names in ambiguous_files.values() for name in names}),
    }

    print("uncapped tasks: %d" % len(tasks))
    print("recorded runs: %d carryable, %d need re-measurement"
          % (report["carryable_run_count"], report["run_needing_remeasurement_count"]))
    print("readings: %d provably unaffected, %d at the old ceiling"
          % (report["provably_unaffected_readings"], report["ambiguous_readings"]))
    print("keys cleared by having exceeded 1.0 somewhere: %d" % len(exceeds_one))
    print("keys cleared by never having been edited since their evidence: %d" % len(untouched_keys))
    if undecided_keys:
        print("keys git could not answer for: %d" % len(undecided_keys))
    if ambiguous_keys:
        print("keys that top out at exactly 1.0 and cannot be told from a bounded rate:")
        for key, count in ambiguous_keys.most_common(10):
            print("    %-46s %d readings" % (key[:46], count))
    if report["tasks_needing_remeasurement"]:
        print("tasks with at least one run that cannot be carried forward on this argument:")
        for task in report["tasks_needing_remeasurement"]:
            print("    %-46s %d of %d runs"
                  % (task[:46], ambiguous_runs[task], ambiguous_runs[task] + clean_runs[task]))

    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("wrote", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
