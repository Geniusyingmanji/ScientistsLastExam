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


def summarize(directory: Path) -> dict | None:
    proposals = read_trajectory(directory)
    if not proposals:
        return None
    valid = [r for r in proposals if r.get("valid")]
    scores = [float(r.get("score") or 0.0) for r in valid]
    kinds = Counter(
        str(r.get("candidate_failure_kind") or "unspecified")
        for r in proposals if not r.get("valid")
    )
    return {
        "workdir": directory.name,
        "proposals": len(proposals),
        "valid": len(valid),
        "protocol_pass_rate": len(valid) / len(proposals),
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
    rows.sort(key=lambda r: (r["protocol_pass_rate"], r["workdir"]))

    contract_bound = [r for r in rows
                      if r["protocol_pass_rate"] < args.pass_threshold]

    print("%-40s %6s %6s %9s %12s" % (
        "workdir", "props", "valid", "pass_rate", "sci|valid"))
    print("-" * 78)
    for r in rows:
        sci = r["science_given_valid_mean"]
        print("%-40s %6d %6d %9.2f %12s" % (
            r["workdir"][:40], r["proposals"], r["valid"], r["protocol_pass_rate"],
            "-" if sci is None else "%.4f" % sci))

    print()
    print("contract-bound (pass rate < %.2f): %d of %d"
          % (args.pass_threshold, len(contract_bound), len(rows)))
    for r in contract_bound:
        print("  %-40s pass=%.2f  failures=%s"
              % (r["workdir"][:40], r["protocol_pass_rate"], r["failure_kinds"]))

    allkinds: Counter = Counter()
    for r in rows:
        allkinds.update(r["failure_kinds"])
    print()
    print("failure kinds across all runs:", dict(allkinds.most_common()))

    Path(args.output).write_text(json.dumps({
        "schema_version": 1,
        "runs_root": str(root),
        "pass_threshold": args.pass_threshold,
        "task_count": len(rows),
        "contract_bound_count": len(contract_bound),
        "failure_kinds_total": dict(allkinds),
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
