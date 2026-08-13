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

from sle.registry import list_tasks  # noqa: E402

# Several naming conventions coexist in the inventory. Preference order runs from the strictest
# evidence (held-out worlds) to the weakest (development worlds the searcher could see).
AXES = {
    "mechanism": (
        "heldout_mechanism_score",
        "mechanism_score",
        "development_mechanism_score",
        "development_body_support_f1",
        # Same axis, different vocabulary. Without these, a task that measures mechanism recovery
        # thoroughly reads as not measuring it at all.
        "heldout_supported_correct_model_rate",
        "development_supported_correct_model_rate",
        "heldout_hypothesis_score",
        "development_hypothesis_score",
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
    # A fourth column, not a fourth axis. The triple says how good a discovery was; this says
    # whether one was attempted at all. Without it a task can read as impossibly hard when what
    # actually happened is that every proposal declined every world - and the two call for
    # opposite responses. Six tasks in this inventory score exactly zero, and all six turn out to
    # be blanket abstention rather than difficulty: refusal 1.00 with coverage 0.00 on every
    # valid proposal. The scoring is right to give that nothing, because a task that pays for
    # declining is a task that can be farmed by declining. What was wrong was that the report
    # could not tell the two apart.
    "coverage": (
        "heldout_discovery_coverage",
        "development_discovery_coverage",
        "development_supported_claim_coverage",
        "development_attempt_rate",
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


# Some evaluators publish a count where the report needs a rate, and do not publish the
# denominator that would turn one into the other. That is a different defect from not measuring
# the axis at all, and conflating them sends the fix to the wrong place: a count with no
# denominator means the number is in the evaluator but unusable downstream.
COUNT_ONLY = {
    "fdr": ("heldout_false_discoveries", "development_false_discoveries",
            "validation_false_discoveries"),
    "refusal": ("heldout_correct_abstentions", "development_correct_abstentions",
                "validation_correct_abstentions"),
}


def extract(metrics: dict) -> dict:
    out = {}
    for axis, candidates in AXES.items():
        for key in candidates:
            if key in metrics and isinstance(metrics[key], (int, float)):
                out[axis] = {"value": float(metrics[key]), "key": key}
                break
        else:
            counted = next(
                (key for key in COUNT_ONLY.get(axis, ()) if key in metrics), None
            )
            out[axis] = (
                {"value": None, "key": counted, "status": "count_without_denominator"}
                if counted else None
            )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    wanted = discovery_task_names()
    root = Path(args.runs)

    # Every run of the task, found by reading the manifest rather than by matching directory
    # names, and across cohorts rather than inside one. The previous version looked only at
    # `runs/<one cohort>/<name>_*` and then used `matches[0]` - the first directory it happened
    # to find - so it reported "no valid proposal" for all nineteen discovery tasks against a
    # tree holding hundreds of them, and would have reported one arbitrary run if it had found
    # any. Directory names are not reliable here either: budget-sweep cohorts are named for their
    # budget, not their task.
    by_task: dict[str, list[Path]] = {}
    for manifest in root.glob("*/*/run_manifest.json"):
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        task_id = str(document.get("task_id") or "")
        name = task_id.split("/")[-1]
        if name in wanted:
            by_task.setdefault(name, []).append(manifest.parent)

    rows = []
    for name in sorted(wanted):
        candidates = [m for m in (best_metrics(d) for d in by_task.get(name, []))
                      if m is not None]
        # The best valid proposal anywhere, which is what a leaderboard would show.
        metrics = max(candidates, key=lambda m: float(m.get("combined_score") or 0.0),
                      default=None)
        # Which axes any run of this task publishes, not just the best-scoring one. An evaluator
        # that started publishing an axis after its best run was recorded would otherwise be
        # reported as never measuring it, which is a different and more damning claim.
        published_anywhere = {axis for m in candidates
                              for axis, entry in extract(m).items() if entry is not None}
        if metrics is None:
            rows.append({"task": name, "status": "no valid proposal"})
            continue
        axes = extract(metrics)
        rows.append({
            "task": name,
            "status": "ok",
            "runs_seen": len(by_task.get(name, [])),
            "axes_published_by_some_run": sorted(published_anywhere),
            "combined_score": metrics.get("combined_score"),
            "axes": axes,
            "missing_axes": [a for a, v in axes.items() if v is None],
            "count_without_denominator": [
                a for a, v in axes.items()
                if v is not None and v.get("status") == "count_without_denominator"
            ],
        })

    def cell(entry):
        if entry is None:
            return "     -  "
        if entry.get("value") is None:
            return "  count "
        return "%8.4f" % entry["value"]

    print("discovery triple, best valid proposal per task. never averaged.")
    print("coverage is not part of the triple: it says whether a discovery was attempted.")
    print("%-32s %9s %9s %9s %9s %9s"
          % ("task", "combined", "mechanism", "fdr", "refusal", "coverage"))
    print("-" * 84)
    for r in rows:
        if r["status"] != "ok":
            print("%-32s %9s   %s" % (r["task"][:32], "-", r["status"]))
            continue
        a = r["axes"]
        print("%-32s %9.4f %s %s %s %s" % (
            r["task"][:32], r["combined_score"] or 0.0,
            cell(a["mechanism"]), cell(a["fdr"]), cell(a["refusal"]),
            cell(a.get("coverage"))))

    # Called out separately, because a task read as impossibly hard and a task nobody attempted
    # need opposite responses and the combined score shows the same 0.0000 for both.
    def value_of(row, axis):
        entry = (row.get("axes") or {}).get(axis)
        return None if entry is None else entry.get("value")

    # A task that publishes no coverage metric has not been shown to decline; it has been shown
    # to be unmeasured on this question. Folding the two together flagged GravityInversion, which
    # scores 0.9941 with a mechanism score of 0.8593, as having attempted nothing.
    declined = [r for r in rows if r["status"] == "ok"
                and value_of(r, "coverage") is not None
                and value_of(r, "coverage") <= 1e-9]
    unmeasured = [r for r in rows if r["status"] == "ok" and value_of(r, "coverage") is None
                  and "coverage" not in (r.get("axes_published_by_some_run") or [])]
    # Measured, but not on the run that scored best. Saying these are unmeasured would be wrong.
    stale = [r for r in rows if r["status"] == "ok" and value_of(r, "coverage") is None
             and "coverage" in (r.get("axes_published_by_some_run") or [])]
    if declined:
        print()
        print("tasks where the best valid proposal attempted no discovery at all: %d of %d"
              % (len(declined), sum(1 for r in rows if r["status"] == "ok")))
        for r in declined:
            print("  %-32s refusal %s, coverage 0" % (
                r["task"][:32], cell((r.get("axes") or {}).get("refusal")).strip()))
        print("  These score zero correctly - a task that pays for declining can be farmed by")
        print("  declining - but the zero is a refusal, not a difficulty, and recalibrating the")
        print("  anchor would be treating the wrong thing.")
    if unmeasured:
        print()
        print("tasks whose evaluator publishes no coverage metric: %d" % len(unmeasured))
        print("  " + ", ".join(r["task"][:28] for r in unmeasured))
        print("  Whether a discovery was attempted cannot be read off any run of these.")
    if stale:
        print()
        print("tasks whose best proposal predates their coverage metric: %d" % len(stale))
        print("  " + ", ".join(r["task"].split("/")[-1][:28] for r in stale))
        print("  The evaluator publishes it now; the highest-scoring run on record was made")
        print("  before it did, so the column is blank for that particular proposal.")

    incomplete = [r for r in rows if r.get("missing_axes")]
    countonly = [r for r in rows if r.get("count_without_denominator")]
    print()
    print("tasks missing at least one axis outright: %d of %d" % (len(incomplete), len(rows)))
    for r in incomplete:
        print("  %-32s missing %s" % (r["task"][:32], r["missing_axes"]))
    print()
    print("tasks publishing a count where a rate is needed: %d" % len(countonly))
    for r in countonly:
        keys = [v["key"] for a, v in r["axes"].items()
                if v is not None and v.get("status") == "count_without_denominator"]
        print("  %-32s %s -> %s" % (
            r["task"][:32], r["count_without_denominator"], keys))
    if countonly:
        print("  the evaluator measures these; it publishes the numerator without the world")
        print("  count that would make it a rate. Fixing it edits the task package and so")
        print("  rebinds that task's analysis artifacts - a governance step, not a cleanup.")

    Path(args.output).write_text(json.dumps({
        "schema_version": 1,
        "note": "the three axes are reported separately and must not be averaged",
        "task_count": len(rows),
        "incomplete_count": len(incomplete),
        "count_without_denominator_count": len(countonly),
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
