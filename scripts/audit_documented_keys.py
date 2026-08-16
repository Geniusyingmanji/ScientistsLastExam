#!/usr/bin/env python3
"""Find inputs a task passes to the candidate but never names in its prompt.

A candidate that reaches for a real quantity under a guessed name raises at runtime and scores
nothing, and that zero is indistinguishable from a zero earned on the science. It is not
hypothetical: `CalorimeterDesign` rejected 36 of 36 proposals, and the first rejection retained
for diagnosis had read `problem["light_yield_per_gev"]` when the key is
`light_yield_pe_per_active_gev`. The quantity exists, the name was undocumented, and the task's
prompt named only 15 of the 27 keys it passes in.

This audits the same thing everywhere, from two directions:

    baseline keys   every `problem["..."]` the shipped baseline reads. These are certainly real,
                    since the baseline runs, so any that the prompt does not name is a key a
                    candidate could only get right by copying the baseline.
    prompt coverage whether the name appears anywhere in Task.md or the constraints file.

It reads the task package only and needs no runs, so it applies to a task the day it is written.
It undercounts by construction - a key the baseline happens not to use is invisible here - so a
clean result means "nothing found", not "nothing undocumented".

Usage:
    python scripts/audit_documented_keys.py --output /tmp/keys.json
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.registry import list_tasks  # noqa: E402

# Names a task's input mapping goes by across this inventory.
INPUT_NAMES = {"problem", "instance", "spec", "task", "inputs", "context"}

# Names the evaluator gives the candidate's return value. Keys read off these are the submission
# contract - the other half of the interface, and undocumented just as often. The exact
# calibration key names QuartzCrystalMicrobalanceLab requires appear nowhere in its prompt.
# Deliberately narrow. `result`, `out` and `output` are what evaluators call their own metrics
# dict at least as often as the candidate's return value, and reading those produced a list of
# "undocumented submission fields" containing `error_message`, `valid_rate` and `robustness_score`
# - names the evaluator writes, not names a candidate must supply. A false positive here sends
# someone to document a field that is not part of the contract.
# `fitted` is left out although some evaluators do use it for the validated candidate result:
# others use it for the hidden truth, and CatalystDeactivationLab does exactly that, mapping
# `fitted["log10_a"]` - a world parameter - onto the public name. A name that means opposite
# things in different tasks is not a usable signal, and this audit already declares itself an
# undercount.
SUBMISSION_NAMES = {"submission", "answer", "claim", "returned"}

# Constants that hold the exact submission contract. The suffix alone is too loose for the same
# reason.
SUBMISSION_CONSTANTS = ("SUBMISSION_KEYS", "CALIBRATION_KEYS", "CLAIM_KEYS", "REQUIRED_KEYS",
                        "COMMIT_KEYS", "ANSWER_KEYS")


def _subscript_index(node: ast.Subscript) -> ast.AST:
    """The expression inside `x[...]`, on either side of the 3.9 AST change.

    Before 3.9 the slice is wrapped in an `ast.Index`; from 3.9 it is the expression itself.
    Reading `node.slice` directly finds nothing on the older grammar, and finding nothing is
    indistinguishable here from an evaluator that reads no input keys - so this audit quietly
    reported a clean bill of health on the evaluation host, which runs 3.8, while working
    correctly on a 3.11 laptop.
    """
    index = node.slice
    return getattr(index, "value", index) if index.__class__.__name__ == "Index" else index


def subscript_keys(source: str, names: set[str] | None = None) -> set[str]:
    """String keys read off a named mapping: `problem["x"]` and `problem.get("x")`."""
    names = INPUT_NAMES if names is None else names
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id in names):
            index = _subscript_index(node)
            if isinstance(index, ast.Constant) and isinstance(index.value, str):
                found.add(index.value)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get" and isinstance(node.func.value, ast.Name)
                and node.func.value.id in names and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            found.add(node.args[0].value)
    return found


def submission_keys(source: str) -> set[str]:
    """Keys the evaluator reads off the candidate's return value, plus any declared key set.

    A task states its submission fields in prose and then validates them against an exact set. If
    the set is a module-level constant - `SUBMISSION_KEYS`, `CALIBRATION_KEYS` - the names in it
    are the contract, and a candidate that uses any other name is rejected outright.
    """
    found = subscript_keys(source, SUBMISSION_NAMES)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return found
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or target.id not in SUBMISSION_CONSTANTS:
                continue
            if isinstance(node.value, (ast.Set, ast.List, ast.Tuple)):
                for element in node.value.elts:
                    if isinstance(element, ast.Constant) and isinstance(element.value, str):
                        found.add(element.value)
    return found


def evaluator_problem_keys(source: str) -> set[str]:
    """Keys of dict literals returned by the evaluator's problem constructors.

    The baseline is a lower bound on what a task passes in - a key it happens not to read is
    invisible - and the gap matters, because an undocumented key the baseline ignores is exactly
    the one a candidate has no way to learn. `CalorimeterDesign` passes 27 keys and its baseline
    reads 10 of them.

    Only functions whose name mentions `public` or `problem` are read, and only dict literals they
    return, so a private helper's internal mapping is not mistaken for the candidate's input.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        name = node.name.lower()
        if "public" not in name and "problem" not in name:
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Return) and isinstance(inner.value, ast.Dict):
                for key in inner.value.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        found.add(key.value)
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)

    rows = []
    for spec in list_tasks(None):
        program = spec.initial_program_path
        if not program.is_file():
            continue
        keys = subscript_keys(program.read_text(encoding="utf-8"))
        evaluator = spec.task_dir / "verification" / "evaluator.py"
        declared = (evaluator_problem_keys(evaluator.read_text(encoding="utf-8"))
                    if evaluator.is_file() else set())
        keys |= declared
        if not keys:
            continue
        prose = ""
        for name in ("Task.md",):
            path = spec.task_dir / name
            if path.is_file():
                prose += path.read_text(encoding="utf-8")
        constraints = spec.eval_dir / "constraints.txt"
        if constraints.is_file():
            prose += constraints.read_text(encoding="utf-8")
        submitted = (submission_keys(evaluator.read_text(encoding="utf-8"))
                     if evaluator.is_file() else set())
        undocumented = sorted(k for k in keys if k not in prose)
        undocumented_submission = sorted(k for k in submitted if k not in prose)
        rows.append({
            "task": spec.task_id,
            "keys_read_by_baseline": len(keys),
            "submission_keys": len(submitted),
            "undocumented_submission": undocumented_submission,
            "keys_only_in_evaluator": sorted(declared - subscript_keys(
                program.read_text(encoding="utf-8"))),
            "undocumented": undocumented,
        })

    rows.sort(key=lambda r: (-len(r["undocumented"]), r["task"]))
    affected = [r for r in rows if r["undocumented"]]
    submission_affected = [r for r in rows if r["undocumented_submission"]]

    print("%-34s %8s %s" % ("task", "keys", "undocumented"))
    print("-" * 78)
    for row in rows:
        print("%-34s %8d %s" % (
            row["task"].split("/")[-1][:34], row["keys_read_by_baseline"],
            ", ".join(row["undocumented"][:4]) + (" ..." if len(row["undocumented"]) > 4 else "")
            or "-"))

    print()
    print("tasks whose baseline reads an input the prompt never names: %d of %d"
          % (len(affected), len(rows)))
    print("total undocumented keys: %d" % sum(len(r["undocumented"]) for r in affected))
    print()
    print("Each of these is a name a candidate can only get right by copying the baseline. A")
    print("candidate that reaches for the quantity under any other name raises, and the zero it")
    print("earns cannot be told apart from a zero earned on the science.")
    print()
    print("tasks whose prompt does not name a field their submission is validated against: "
          "%d of %d" % (len(submission_affected), len(rows)))
    for row in submission_affected:
        print("  %-32s %s" % (
            row["task"].split("/")[-1][:32],
            ", ".join(row["undocumented_submission"][:5])
            + (" ..." if len(row["undocumented_submission"]) > 5 else "")))
    print("  A submission using any other name is rejected outright, so this side of the")
    print("  interface costs a candidate everything rather than one field.")
    print()
    print("This undercounts: a key the baseline does not happen to read is invisible here.")

    Path(args.output).write_text(json.dumps({
        "schema_version": 1,
        "note": "undercounts by construction; only keys the shipped baseline reads are checked",
        "tasks_with_undocumented_inputs": [r["task"] for r in affected],
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print()
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
