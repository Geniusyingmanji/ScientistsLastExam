#!/usr/bin/env python3
"""Find keys in a task's public problem whose name reads numeric but whose value is prose.

A candidate reads the problem dictionary before it reads the prose, and it types what the key
name says. `noise_sigma_hint` holding "additive Gaussian, sigma between 0.008 and 0.012 in
velocity units" is a `float()` that raises in a setup block, before the first oracle call, on
every world. A live Opus 5 draw did exactly that on EnzymeKineticsLaw: nine of nine proposals
across three seeds scored zero, and the same program scored 0.823 once the key held a pair of
numbers. Nothing in the run said why - the failures read as `candidate_runtime_error`.

This is not a style check. Difficulty a task did not intend is difficulty it does not measure,
and a naming trap costs the whole cohort rather than the one proposal that tripped on it.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sle.registry import list_tasks  # noqa: E402

# Key names that promise a number, a pair of numbers, or a list of them.
NUMERIC_NAME = re.compile(
    r"(^|_)(sigma|tolerance|budget|count|bounds|range|limit|max|min|threshold|rate|"
    r"scale|size|steps?|seconds|hours|width|height|depth|temperature|precision|"
    r"resolution|interval|epsilon|delta|n)($|_)", re.IGNORECASE)

# Names that are numeric-sounding but conventionally carry prose, and are read as prose.
PROSE_BY_CONVENTION = {"units", "velocity_units", "rate_law", "rate_units"}


def _numeric(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _numeric(node.operand)
    if isinstance(node, (ast.List, ast.Tuple)):
        return bool(node.elts) and all(_numeric(e) for e in node.elts)
    return False


def offending_keys(source: str) -> list[tuple[str, str, int]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                continue
            name = key.value
            if name in PROSE_BY_CONVENTION or not NUMERIC_NAME.search(name):
                continue
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                # A short enumerated string is a label, not prose a candidate would float().
                if " " in value.value.strip():
                    found.append((name, value.value, key.lineno))
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    parser.add_argument("--task", help="check one task instead of the inventory")
    args = parser.parse_args()

    rows = []
    for spec in list_tasks(None):
        if args.task and spec.task_id != args.task:
            continue
        evaluator = spec.task_dir / "verification" / "evaluator.py"
        if not evaluator.is_file():
            continue
        for name, value, line in offending_keys(evaluator.read_text(encoding="utf-8")):
            rows.append({"task": spec.task_id, "key": name, "line": line,
                         "value": value[:160]})
    for row in rows:
        print("%-46s %-28s line %-5d %r"
              % (row["task"], row["key"], row["line"], row["value"]))
    print("\nnumeric-sounding keys holding prose: %d across %d task(s)"
          % (len(rows), len({r["task"] for r in rows})))
    if args.output:
        Path(args.output).write_text(
            json.dumps({"findings": rows, "passed": not rows}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
