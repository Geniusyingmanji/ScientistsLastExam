#!/usr/bin/env python3
"""Separate protocol conformance from scientific capability in run trajectories.

A task whose submissions are rejected and a task whose science is hard both produce a zero, and
the budget-one census could not tell them apart. This reports two numbers per task instead of
one: how often a proposal was even accepted, and how well the accepted ones scored.

    protocol_pass_rate   valid proposals / total proposals
    science_given_valid  mean and best score over the valid proposals only

A low pass rate with a high conditional score means the contract is the obstacle, not the
science. A high pass rate with a low conditional score is genuine scientific difficulty.

Usage:
    python scripts/report_protocol_vs_science.py --runs runs/saturation --output /tmp/pvs.json
"""
from __future__ import annotations

import argparse
import json
import statistics as st
from collections import Counter
from pathlib import Path


def read_trajectory(directory: Path) -> list[dict]:
    path = directory / "trajectory.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    # step 0 is the shipped baseline, not a proposal
    return [r for r in rows if int(r.get("step", 0) or 0) > 0]


def _kind(row: dict) -> str:
    """The taxonomy lives inside the metrics payload, not at the top level of the row."""
    metrics = row.get("metrics") or {}
    return str(metrics.get("candidate_failure_kind")
               or row.get("candidate_failure_kind") or "unspecified")


def _executed(row: dict) -> bool:
    """Did the candidate run to completion, whatever the oracle then decided about it?

    A proposal that crashed, timed out or was killed never reached the science. A proposal that
    ran and was then judged infeasible did reach it and failed there. Counting both as "protocol
    failure" - which an earlier version of this report did - overstates how much of this
    inventory is blocked by its contracts. In the paired and screening cohorts the split is 202
    that never executed against 136 that executed and were ruled infeasible, several of the
    latter carrying a real score the oracle computed before rejecting them.
    """
    metrics = row.get("metrics") or {}
    if metrics.get("candidate_failure_kind"):
        return False
    if metrics.get("infrastructure_failure") or metrics.get("timeout"):
        return False
    # A completed evaluation leaves a scored metrics payload behind.
    return bool(metrics) and "combined_score" in metrics


def summarize(directory: Path) -> dict | None:
    proposals = read_trajectory(directory)
    if not proposals:
        return None
    valid = [r for r in proposals if r.get("valid")]
    scores = [float(r.get("score") or 0.0) for r in valid]
    rejected = [r for r in proposals if not r.get("valid")]
    infeasible = [r for r in rejected if _executed(r)]
    unexecuted = [r for r in rejected if not _executed(r)]
    kinds = Counter(_kind(r) for r in unexecuted)
    reached_science = len(valid) + len(infeasible)
    return {
        "workdir": directory.name,
        "proposals": len(proposals),
        "valid": len(valid),
        # How often a proposal ran at all. This is the contract-and-execution question.
        "execution_rate": reached_science / len(proposals),
        # How often a proposal that ran was also feasible. This is a scientific question.
        "feasible_given_executed": (len(valid) / reached_science) if reached_science else None,
        "infeasible_but_executed": len(infeasible),
        "never_executed": len(unexecuted),
        "science_given_valid_mean": st.mean(scores) if scores else None,
        "science_given_valid_best": max(scores) if scores else None,
        "failure_kinds": dict(kinds),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, help="directory containing run workdirs")
    ap.add_argument("--output", required=True)
    ap.add_argument("--pass-threshold", type=float, default=0.5,
                    help="pass rate below which the contract is flagged as the obstacle")
    args = ap.parse_args()

    root = Path(args.runs)
    rows = [s for s in (summarize(d) for d in sorted(root.iterdir()) if d.is_dir()) if s]
    rows.sort(key=lambda r: (r["execution_rate"], r["workdir"]))

    contract_bound = [r for r in rows if r["execution_rate"] < args.pass_threshold]

    print("%-38s %6s %6s %7s %9s %10s" % (
        "workdir", "props", "valid", "ran", "feasible", "sci|valid"))
    print("-" * 82)
    for r in rows:
        sci = r["science_given_valid_mean"]
        feas = r["feasible_given_executed"]
        print("%-38s %6d %6d %7.2f %9s %10s" % (
            r["workdir"][:38], r["proposals"], r["valid"], r["execution_rate"],
            "-" if feas is None else "%.2f" % feas,
            "-" if sci is None else "%.4f" % sci))

    print()
    print("contract-bound (fewer than %.0f%% of proposals even executed): %d of %d"
          % (100 * args.pass_threshold, len(contract_bound), len(rows)))
    for r in contract_bound:
        print("  %-38s ran=%.2f  never executed: %s"
              % (r["workdir"][:38], r["execution_rate"], r["failure_kinds"]))

    ran_but_infeasible = sum(r["infeasible_but_executed"] for r in rows)
    never_ran = sum(r["never_executed"] for r in rows)
    print()
    print("rejected proposals: %d never executed, %d executed and were ruled infeasible"
          % (never_ran, ran_but_infeasible))
    print("  the second group is a scientific failure, not a contract one, and an earlier")
    print("  version of this report counted them together")

    allkinds: Counter = Counter()
    for r in rows:
        allkinds.update(r["failure_kinds"])
    print()
    print("failure kinds across all runs:", dict(allkinds.most_common()))

    Path(args.output).write_text(json.dumps({
        "schema_version": 1,
        "runs_root": str(root),
        "pass_threshold": args.pass_threshold,
        "note": "execution_rate is the contract question; feasible_given_executed is the "
                "scientific one. They were previously conflated into one pass rate.",
        "task_count": len(rows),
        "contract_bound_count": len(contract_bound),
        "failure_kinds_total": dict(allkinds),
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
