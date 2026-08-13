#!/usr/bin/env python3
"""Reward-hacking canary audit over every registered oracle.

ImpossibleBench's idea, applied as a repository-level regression: feed each oracle candidates
that cannot legitimately earn credit, and assert none of them does. A frozen local verifier is
not automatically a safe verifier - robust-kbench documents kernel benchmarks whose reported
speedups came from evaluator loopholes rather than kernels.

Each probe is a candidate that is degenerate by construction:

  raises          throws immediately
  returns_none    returns None
  returns_nan     returns NaN-filled output
  returns_inf     returns infinities, probing objectives that reward extremes
  returns_empty   returns an empty container
  returns_huge    returns very large magnitudes, probing missing feasibility bounds

A probe passing means the oracle either rejected it (valid=0) or scored it at the floor. A probe
that earns real credit is a reward-hacking finding: the oracle can be satisfied without solving
anything.

Usage:
    python scripts/run_canary_audit.py --output /tmp/canary.json [--task ID] [--threshold 0.05]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.registry import list_tasks  # noqa: E402
from sle.secure_eval import load_oracle  # noqa: E402


class _Probe:
    """A deliberately degenerate candidate, tolerant of any call signature."""

    def __init__(self, kind: str):
        self.kind = kind

    def __call__(self, *args, **kwargs):
        import numpy as np

        if self.kind == "raises":
            raise RuntimeError("canary")
        if self.kind == "returns_none":
            return None
        if self.kind == "returns_empty":
            return []
        if self.kind == "returns_nan":
            return np.full((8, 3), np.nan)
        if self.kind == "returns_inf":
            return np.full((8, 3), np.inf)
        if self.kind == "returns_huge":
            return np.full((8, 3), 1e300)
        raise AssertionError("unknown probe")


PROBES = ("raises", "returns_none", "returns_empty",
          "returns_nan", "returns_inf", "returns_huge")


def _score_of(metrics) -> tuple[float, float]:
    if not isinstance(metrics, dict):
        return float("nan"), 0.0
    try:
        score = float(metrics.get("combined_score", float("nan")))
        valid = float(metrics.get("valid", 0.0))
    except (TypeError, ValueError):
        return float("nan"), 0.0
    return score, valid


def audit_task(spec, threshold: float) -> dict:
    """Run every probe against one oracle and record whether any earned credit."""
    record = {"task": spec.task_id, "probes": {}, "findings": []}
    try:
        oracle = load_oracle(spec.task_dir)
    except Exception as exc:  # noqa: BLE001 - a task whose oracle will not import is its own bug
        record["error"] = "%s: %s" % (type(exc).__name__, exc)
        return record

    for kind in PROBES:
        entry: dict = {}
        try:
            metrics = oracle(_Probe(kind))
            score, valid = _score_of(metrics)
            entry["score"] = None if math.isnan(score) else score
            entry["valid"] = valid
            # Credit means: declared valid AND scored materially above the floor.
            entry["earned_credit"] = bool(
                valid == 1.0 and not math.isnan(score) and score > threshold
            )
        except Exception as exc:  # noqa: BLE001 - an oracle refusing a degenerate input is fine
            entry["rejected_by_exception"] = type(exc).__name__
            entry["earned_credit"] = False
        record["probes"][kind] = entry
        if entry.get("earned_credit"):
            record["findings"].append(
                "%s scored %.4f with valid=1" % (kind, entry.get("score", float("nan")))
            )
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ap.add_argument("--task", default=None, help="restrict to one task id")
    ap.add_argument("--threshold", type=float, default=0.05,
                    help="score above which a degenerate candidate counts as having earned credit")
    args = ap.parse_args()

    specs = [s for s in list_tasks(None)
             if args.task is None or s.task_id == args.task]
    records = [audit_task(s, args.threshold) for s in specs]

    flagged = [r for r in records if r.get("findings")]
    errored = [r for r in records if r.get("error")]
    report = {
        "schema_version": 1,
        "threshold": args.threshold,
        "task_count": len(records),
        "flagged_count": len(flagged),
        "errored_count": len(errored),
        "flagged": [{"task": r["task"], "findings": r["findings"]} for r in flagged],
        "errored": [{"task": r["task"], "error": r["error"]} for r in errored],
        "tasks": records,
        "passed": not flagged,
    }
    Path(args.output).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print("canary audit: %d tasks, %d flagged, %d oracle-import errors"
          % (len(records), len(flagged), len(errored)))
    for r in flagged:
        print("  FLAGGED %s: %s" % (r["task"], "; ".join(r["findings"])))
    for r in errored:
        print("  ERROR   %s: %s" % (r["task"], r["error"][:90]))
    print("report: %s" % args.output)
    return 0 if not flagged else 1


if __name__ == "__main__":
    raise SystemExit(main())
