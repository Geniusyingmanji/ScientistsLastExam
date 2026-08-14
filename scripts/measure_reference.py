#!/usr/bin/env python3
"""Run a task's shipped reference implementation through its own evaluator and print the result.

Ten of forty-three tasks claim an anchor in prose and eight ship something runnable, so for most
of the inventory "the reference recovers the mechanism and abstains only where it should" is an
assertion nobody has executed. That gap has a cost: five discovery tasks score zero because every
proposal declines every world, and whether declining was in fact wrong rests on exactly that
unexecuted claim.

This runs the reference and reports what it scores, so the claim becomes a number. It imports the
evaluator and the reference directly, without the sandbox, because a reference is trusted code
that lives beside the oracle rather than a candidate.

Usage:
    python scripts/measure_reference.py --task EarthScience/RadiativeTransferFit \\
        --reference verification/reference_retrieval.py --entry discover_atmosphere
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

INTERESTING = ("valid", "combined_score", "mechanism", "coverage", "refusal",
               "false_discovery", "abstention", "feasibility")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, help="path under benchmarks/, e.g. Domain/Task")
    ap.add_argument("--reference", required=True, help="path within the task directory")
    ap.add_argument("--entry", required=True, help="callable the evaluator expects")
    ap.add_argument("--output", default=None)
    args = ap.parse_args(argv)

    task_dir = ROOT / "benchmarks" / args.task
    if not task_dir.is_dir():
        print("no such task directory: %s" % task_dir, file=sys.stderr)
        return 2

    evaluator = load(task_dir / "verification" / "evaluator.py", "task_evaluator")
    reference = load(task_dir / args.reference, "task_reference")
    entry = getattr(reference, args.entry, None)
    if entry is None:
        print("reference has no %s" % args.entry, file=sys.stderr)
        return 2

    metrics = evaluator.evaluate(entry)
    shown = {k: v for k, v in sorted(metrics.items())
             if any(word in k for word in INTERESTING) and not isinstance(v, (list, dict))}
    width = max((len(k) for k in shown), default=10)
    for key, value in shown.items():
        print("  %-*s %s" % (width, key,
                             round(value, 4) if isinstance(value, float) else value))
    if args.output:
        Path(args.output).write_text(json.dumps(
            {k: v for k, v in metrics.items() if not isinstance(v, (list, dict))},
            indent=2, default=float), encoding="utf-8")
        print("\nreport:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
