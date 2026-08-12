#!/usr/bin/env python3
"""Audit whether each task poses the kind of problem this benchmark is about.

Three audits now sit side by side and answer different questions:

    audit_tasks.py              is the task card well formed
    audit_benchmark_standards   is the science underneath it sound
    audit_theme_fit (this one)  is it the right kind of problem in the first place

The benchmark is about open-ended scientific work that keeps rewarding effort — the regime
AlphaFold-style and AlphaEvolve-style results live in. A task can have a community oracle, a
recomputed anchor and a clean card, and still be the wrong shape: "implement a known algorithm"
is real work with a unique answer, and no amount of iteration improves on the answer once found.

Everything below is read from the task package. None of it needs a run, which is the point: the
admission criterion needs paired experiments and can only be applied to tasks that have them,
while the shape of a task can be checked the day it is written.

  open_ended            the anchor is not itself a solution a correct implementation reaches.
                        Counted against when the card describes its reference as a manufactured,
                        closed-form or analytic solution, as unit fidelity, or as the optimum.
                        A hidden truth existing does not count: every discovery task has one.
  frontier_anchored     scored uncapped against a reference the field would want to beat, so
                        exceeding it is a result rather than an overflow.
  continuously_scored   the score is a quality measure, not a threshold. A task that pays out on
                        crossing a line cannot show incremental improvement past it.
  role_declared         scientific_role is optimization or discovery - the two forms this
                        benchmark claims to cover.
  discovery_axes        for discovery tasks only: the evaluator emits mechanism recovery, a
                        false-discovery rate and a refusal rate. A discovery task that reports
                        one scalar cannot say whether the discovery was right.

The verdicts are printed per task and never averaged into a score. A task failing `open_ended` is
not a bad task - it is a different kind of task, and the honest response is to label it rather
than to pretend it measures iteration.

Usage:
    python scripts/audit_theme_fit.py --output /tmp/theme.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from frontier_science.registry import list_tasks  # noqa: E402

# Phrases that say the anchor itself is a solution a correct implementation reaches. Written
# narrowly on purpose: a first version matched the bare word "exact" and flagged four tasks
# wrongly. "scores exactly 0 by construction" describes a baseline, which is supposed to be
# trivial; "exact-recipe confirmation" is a compound word; and "the exact hidden graph" describes
# the truth a discovery task is trying to recover, which every discovery task has. None of those
# says the reference is easy to reach, which is the only thing this check is about.
# Up to two intervening words, which may be hyphenated: the real phrases in this inventory are
# "manufactured sine-series solution" and "unit global-phase-invariant process fidelity". A first
# attempt allowed only a single plain word between and silently missed both, which is the reverse
# of the over-matching it was written to fix.
_GAP = r"(?:[\w-]+\s+){0,2}"
CLOSED_FORM = re.compile(
    r"\b(?:"
    r"manufactured\s+" + _GAP + r"solution"
    r"|closed[- ]form\s+" + _GAP + r"solution"
    r"|analytic(?:al)?\s+" + _GAP + r"solution"
    r"|exact\s+" + _GAP + r"solution"
    r"|(?:true|global)\s+optim(?:um|al)"
    r"|optimal\s+" + _GAP + r"solution"
    r"|unit\s+" + _GAP + r"fidelity"
    r")\b",
    re.IGNORECASE,
)

# A score that pays out on crossing a line. Threshold language in the normalization sentence.
THRESHOLD = re.compile(
    r"\b(threshold|target of|at least|passes? if|meets? the criterion|binary|pass/fail)\b",
    re.IGNORECASE,
)

MECHANISM_KEYS = ("mechanism_score", "mechanism", "body_support_f1", "edge_f1")
FDR_KEYS = ("false_discovery_rate", "false_discoveries")
REFUSAL_KEYS = ("refusal_rate", "correct_abstention", "abstention", "correct_refusal")

CHECKS = ("open_ended", "frontier_anchored", "continuously_scored", "role_declared",
          "discovery_axes")


def emits(source: str, keys) -> bool:
    return any(re.search(r'["\']\w*%s\w*["\']' % re.escape(k), source) for k in keys)


def check(spec, card: dict) -> dict:
    evaluator = spec.task_dir / "verification" / "evaluator.py"
    source = evaluator.read_text(encoding="utf-8") if evaluator.is_file() else ""
    normalization = card.get("normalization") or {}
    # The baseline is excluded: it is meant to be trivially reachable, and reading it here is
    # what made the decoder task - whose anchor is minimum-weight matching, explicitly not the
    # optimum - look like it had a closed-form answer.
    reference_text = " ".join(
        str(normalization.get(key, "")) for key in ("reference", "score"))
    role = str(spec.metadata.get("scientific_role", ""))
    uncapped = str(spec.metadata.get("score_mode", "clipped")) == "uncapped"

    is_discovery = role == "discovery"
    return {
        "open_ended": not bool(CLOSED_FORM.search(reference_text)),
        "frontier_anchored": uncapped,
        "continuously_scored": not bool(THRESHOLD.search(reference_text)),
        "role_declared": role in {"optimization", "discovery"},
        # Not applicable to optimization tasks; reported as None so it is not counted as a failure.
        "discovery_axes": (
            None if not is_discovery
            else (emits(source, MECHANISM_KEYS) and emits(source, FDR_KEYS)
                  and emits(source, REFUSAL_KEYS))
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)

    rows = []
    for spec in list_tasks(None):
        try:
            card = yaml.safe_load(
                (spec.task_dir / "TASK_CARD.yaml").read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            card = {}
        result = check(spec, card)
        applicable = [v for v in result.values() if v is not None]
        rows.append({
            "task": spec.task_id,
            "role": str(spec.metadata.get("scientific_role", "")),
            "score_mode": str(spec.metadata.get("score_mode", "clipped")),
            "checks": result,
            "met": sum(1 for v in applicable if v),
            "applicable": len(applicable),
        })
    rows.sort(key=lambda r: (-r["met"] / max(1, r["applicable"]), r["task"]))

    print("%-34s %-12s %-9s %s" % ("task", "role", "score", "  ".join(c[:4] for c in CHECKS)))
    print("-" * 92)
    for row in rows:
        cells = "  ".join(
            ("yes " if row["checks"][c] else " .  ") if row["checks"][c] is not None else " -  "
            for c in CHECKS)
        print("%-34s %-12s %-9s %s  %d/%d" % (
            row["task"].split("/")[-1][:34], row["role"], row["score_mode"], cells,
            row["met"], row["applicable"]))

    print()
    print("legend:", ", ".join("%s=%s" % (c[:4], c) for c in CHECKS), "( - = not applicable)")
    print()
    totals: Counter = Counter()
    denom: Counter = Counter()
    for row in rows:
        for name, value in row["checks"].items():
            if value is None:
                continue
            denom[name] += 1
            if value:
                totals[name] += 1
    print("inventory of %d tasks:" % len(rows))
    for name in CHECKS:
        print("  %-22s %3d / %-3d" % (name, totals[name], denom[name]))

    closed = [r["task"] for r in rows if not r["checks"]["open_ended"]]
    print()
    print("tasks whose own card describes a reference a correct implementation simply reaches "
          "(%d):" % len(closed))
    for name in closed:
        print("   ", name)
    print("  These are not defective. They ask for a known method and have a unique answer, so")
    print("  iteration stops paying once it is found. Labelling them as such is more useful than")
    print("  measuring an evolvability gap on them.")

    thin_discovery = [r["task"] for r in rows
                      if r["role"] == "discovery" and r["checks"]["discovery_axes"] is False]
    if thin_discovery:
        print()
        print("discovery tasks not emitting all three axes (%d):" % len(thin_discovery))
        for name in thin_discovery:
            print("   ", name)

    Path(args.output).write_text(json.dumps({
        "schema_version": 1,
        "note": "checks are reported separately; a task failing open_ended is a different kind of "
                "task rather than a worse one",
        "checks": list(CHECKS),
        "task_count": len(rows),
        "met_counts": {name: totals[name] for name in CHECKS},
        "applicable_counts": {name: denom[name] for name in CHECKS},
        "closed_form_reference": closed,
        "discovery_missing_axes": thin_discovery,
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print()
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
