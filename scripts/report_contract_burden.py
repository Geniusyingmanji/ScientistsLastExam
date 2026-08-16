#!/usr/bin/env python3
"""How much of a task's difficulty is its contract rather than its science.

The benchmark states a design constraint: contract complexity must not become a difficulty axis,
because a zero earned by failing to guess the submission format cannot be distinguished from a
zero earned by the science being hard. The constraint was asserted from anecdote - "tasks that
fail on protocol have a median evaluator of 808 lines" - and never measured.

It is measurable, and it is being violated. Over the tasks with recorded runs, the rank
correlation between hidden-evaluator length and the fraction of proposals that are even valid is
about -0.64. The shortest evaluators accept 86-100% of proposals; the longest accept 0-66%. On
`CalorimeterDesign` the shipped baseline is valid and scores, while every one of 36 model
proposals raises at runtime: the contract is satisfiable, and editing the solution without
breaking it is the thing being measured.

This reports it per task so the claim can be rechecked, and ranks by where simplification would
buy the most. It deliberately does not compute a single "burden score": validity rate and
evaluator size are different quantities, and a task can be long because its science needs it.

    valid_rate      fraction of proposals the oracle accepted at all
    runtime_errors  of the rejected ones, how many failed by raising rather than by scoring badly
    evaluator_lines size of the hidden contract the candidate must satisfy

Usage:
    python scripts/report_contract_burden.py --runs runs --output /tmp/burden.json
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.registry import list_tasks  # noqa: E402

MIN_PROPOSALS = 10


def spearman(a: list[float], b: list[float]) -> float | None:
    n = len(a)
    if n < 3:
        return None

    def ranks(values):
        order = sorted(range(n), key=lambda i: values[i])
        out = [0.0] * n
        index = 0
        while index < n:
            stop = index
            while stop + 1 < n and values[order[stop + 1]] == values[order[index]]:
                stop += 1
            average = (index + stop) / 2.0 + 1.0
            for position in range(index, stop + 1):
                out[order[position]] = average
            index = stop + 1
        return out

    ra, rb = ranks(a), ranks(b)
    mean_a, mean_b = st.mean(ra), st.mean(rb)
    num = sum((x - mean_a) * (y - mean_b) for x, y in zip(ra, rb))
    den = (sum((x - mean_a) ** 2 for x in ra) * sum((y - mean_b) ** 2 for y in rb)) ** 0.5
    return None if den == 0 else num / den


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)

    sizes, baselines = {}, {}
    for spec in list_tasks(None):
        evaluator = spec.task_dir / "verification" / "evaluator.py"
        if evaluator.is_file():
            sizes[spec.task_id] = len(evaluator.read_text(encoding="utf-8").splitlines())
        program = spec.initial_program_path
        if program.is_file():
            baselines[spec.task_id] = len(program.read_text(encoding="utf-8").splitlines())

    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    # What went in, recorded beside what came out. This report's numbers are quoted in the README,
    # and a run root is not a fixed thing: point it at `runs/` today and it averages the runs made
    # before a fix together with the ones made after, producing a number between the two that
    # matches neither and names nothing. A reader who cannot see which runs produced a figure
    # cannot tell that from a real result.
    inputs: list[dict[str, Any]] = []
    for manifest in sorted(Path(args.runs).glob("*/*/run_manifest.json")):
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        task = str(document.get("task_id") or "")
        if task not in sizes:
            continue
        trajectory = manifest.parent / "trajectory.jsonl"
        if not trajectory.is_file():
            continue
        inputs.append({
            "run": manifest.parent.as_posix(),
            "task": task,
            "feedback_mode": document.get("feedback_mode"),
            "seed": document.get("seed"),
            # The package the run was scored against. Runs from either side of a task edit can sit
            # under one root, and these hashes are what tells them apart after the fact.
            "task_package_sha256": document.get("task_package_sha256"),
            "task_contract_sha256": document.get("task_contract_sha256"),
        })
        for line in trajectory.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if int(row.get("step", 0) or 0) < 1:
                continue
            bucket = counts[task]
            bucket["proposals"] += 1
            if row.get("valid"):
                bucket["valid"] += 1
                continue
            metrics = row.get("metrics") or {}
            kind = str(metrics.get("candidate_failure_kind") or "unlabelled")
            bucket["kind:" + kind] += 1

    rows = []
    for task, bucket in counts.items():
        total = bucket["proposals"]
        if total < MIN_PROPOSALS:
            continue
        rejected = total - bucket["valid"]
        kinds = {k[5:]: v for k, v in bucket.items() if k.startswith("kind:")}
        rows.append({
            "task": task,
            "evaluator_lines": sizes[task],
            "baseline_lines": baselines.get(task),
            "proposals": total,
            "valid_rate": bucket["valid"] / total,
            "rejected": rejected,
            "runtime_error_share": (kinds.get("candidate_runtime_error", 0) / rejected
                                    if rejected else None),
            "failure_kinds": kinds,
        })
    rows.sort(key=lambda r: -r["evaluator_lines"])

    rho = spearman([r["evaluator_lines"] for r in rows], [r["valid_rate"] for r in rows])
    print("%-32s %7s %8s %9s %8s" % ("task", "lines", "baseline", "valid", "runtime"))
    print("-" * 70)
    for row in rows:
        print("%-32s %7d %8s %9.2f %8s" % (
            row["task"].split("/")[-1][:32], row["evaluator_lines"],
            row["baseline_lines"] if row["baseline_lines"] is not None else "-",
            row["valid_rate"],
            "%.2f" % row["runtime_error_share"]
            if row["runtime_error_share"] is not None else "-"))

    print()
    print("tasks with at least %d proposals: %d" % (MIN_PROPOSALS, len(rows)))
    print("rank correlation, evaluator length against proposal validity: %s"
          % ("not computable" if rho is None else "%.3f" % rho))
    print()
    print("A negative correlation here is a design failure, not a discovery about science. The")
    print("benchmark's own constraint is that contract complexity must not be a difficulty axis,")
    print("because a zero earned by failing to guess the submission format cannot be told apart")
    print("from a zero earned by hard science.")

    worst = [r for r in rows if r["valid_rate"] < 0.5]
    if worst:
        print()
        print("tasks rejecting more than half of all proposals (%d):" % len(worst))
        for row in worst:
            print("  %-32s %d evaluator lines, %.0f%% valid, %s"
                  % (row["task"].split("/")[-1][:32], row["evaluator_lines"],
                     100 * row["valid_rate"],
                     "mostly runtime errors" if (row["runtime_error_share"] or 0) > 0.5
                     else "mixed failure kinds"))
        print("  Simplifying these buys more measurable science than any new task would.")

    Path(args.output).write_text(json.dumps({
        "schema_version": 1,
        "note": "validity rate and evaluator size are reported separately; a long evaluator is "
                "not automatically a defect, but a long evaluator that rejects most proposals is",
        "min_proposals": MIN_PROPOSALS,
        "runs_root": str(args.runs),
        "input_run_count": len(inputs),
        "distinct_task_packages_measured": sorted(
            {row["task_package_sha256"] for row in inputs if row["task_package_sha256"]}),
        "inputs": inputs,
        "rank_correlation_lines_vs_validity": rho,
        "rows": rows,
    }, indent=2), encoding="utf-8")
    packages = {row["task_package_sha256"] for row in inputs if row["task_package_sha256"]}
    by_task = defaultdict(set)
    for row in inputs:
        if row["task_package_sha256"]:
            by_task[row["task"]].add(row["task_package_sha256"])
    mixed = sorted(task for task, seen in by_task.items() if len(seen) > 1)
    print()
    print("read %d runs under %s, spanning %d distinct task packages"
          % (len(inputs), args.runs, len(packages)))
    if mixed:
        print("these tasks were measured against more than one package, so their rate here is an")
        print("average across task versions rather than a measurement of any one of them:")
        for task in mixed[:8]:
            print("    %-46s %d packages" % (task[:46], len(by_task[task])))
    print()
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
