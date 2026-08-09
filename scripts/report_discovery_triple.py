#!/usr/bin/env python3
"""Report the discovery triple for every scientific_role: discovery task, never averaged.

A discovery task asks whether a hidden mechanism was recovered, and a single maximised scalar
cannot express that. CausaLab measured GPT-5.2-high at 92% task accuracy with an all-edge F1 of
0.471 on the same setting: objective score and mechanism recovery are different quantities, and
collapsing them hides exactly the failure that matters.

The oracles already compute the axes. They are being folded into combined_score, so this reads
them back out:

    mechanism   did the submitted equation / graph / parameters match the hidden truth
    fdr         did the agent claim a discovery on a world where the truth is out of library
    refusal     did the agent decline when it should have

The three are printed side by side and deliberately never combined. A task missing an axis is
reported as missing rather than imputed.

Usage:
    python scripts/report_discovery_triple.py --runs runs/saturation --output /tmp/triple.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.registry import list_tasks  # noqa: E402

# Several naming conventions coexist in the inventory. Preference order runs from the strictest
# evidence (held-out worlds) to the weakest (development worlds the searcher could see).
AXES = {
    "mechanism": (
        "heldout_mechanism_score",
        "mechanism_score",
        "development_mechanism_score",
        "development_body_support_f1",
    ),
    "fdr": (
        "heldout_false_discovery_rate",
        "development_false_discovery_rate",
    ),
    "refusal": (
        "heldout_unsupported_refusal_rate",
        "development_unsupported_refusal_rate",
        "development_correct_refusal_rate",
        "null_abstention_correct",
    ),
}


def discovery_task_names() -> set[str]:
    names = set()
    for spec in list_tasks(None):
        if str(spec.metadata.get("scientific_role", "")) == "discovery":
            names.add(str(spec.metadata.get("task")))
    return names


def best_metrics(directory: Path) -> dict | None:
    """Metrics of the highest-scoring valid proposal, which is what a leaderboard would show."""
    path = directory / "trajectory.jsonl"
    if not path.is_file():
        return None
    best, best_score = None, None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if int(row.get("step", 0) or 0) <= 0 or not row.get("valid"):
            continue
        score = float(row.get("score") or 0.0)
        if best_score is None or score > best_score:
            best, best_score = (row.get("metrics") or {}), score
    return best


def extract(metrics: dict) -> dict:
    out = {}
    for axis, candidates in AXES.items():
        for key in candidates:
            if key in metrics and isinstance(metrics[key], (int, float)):
                out[axis] = {"value": float(metrics[key]), "key": key}
                break
        else:
            out[axis] = None
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    wanted = discovery_task_names()
    root = Path(args.runs)
    rows = []
    for name in sorted(wanted):
        matches = [d for d in root.iterdir() if d.is_dir() and d.name.startswith(name + "_")]
        metrics = best_metrics(matches[0]) if matches else None
        if metrics is None:
            rows.append({"task": name, "status": "no valid proposal"})
            continue
        axes = extract(metrics)
        rows.append({
            "task": name,
            "status": "ok",
            "combined_score": metrics.get("combined_score"),
            "axes": axes,
            "missing_axes": [a for a, v in axes.items() if v is None],
        })

    def cell(entry):
        return "     -  " if entry is None else "%8.4f" % entry["value"]

    print("discovery triple, best valid proposal per task. never averaged.")
    print("%-32s %9s %9s %9s %9s" % ("task", "combined", "mechanism", "fdr", "refusal"))
    print("-" * 74)
    for r in rows:
        if r["status"] != "ok":
            print("%-32s %9s   %s" % (r["task"][:32], "-", r["status"]))
            continue
        a = r["axes"]
        print("%-32s %9.4f %s %s %s" % (
            r["task"][:32], r["combined_score"] or 0.0,
            cell(a["mechanism"]), cell(a["fdr"]), cell(a["refusal"])))

    incomplete = [r for r in rows if r.get("missing_axes")]
    print()
    print("tasks missing at least one axis: %d of %d" % (len(incomplete), len(rows)))
    for r in incomplete:
        print("  %-32s missing %s" % (r["task"][:32], r["missing_axes"]))

    Path(args.output).write_text(json.dumps({
        "schema_version": 1,
        "note": "the three axes are reported separately and must not be averaged",
        "task_count": len(rows),
        "incomplete_count": len(incomplete),
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
