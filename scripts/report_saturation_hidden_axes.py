#!/usr/bin/env python3
"""Is a task called saturated actually finished, or only finished on the axis anyone can see?

`combined_score` is the only score a searcher receives. Robustness, mechanism recovery and every
per-instance metric are evaluator-only by the visibility contract - deliberately, so a searcher
cannot optimise them directly. The consequence for the saturation verdict is that it is computed
from the one number the searcher was steering by, and it says nothing about the axes the searcher
never saw.

That matters because saturation is what retires a task. `CalorimeterDesign` reads 1.0121 at a
single proposal, above its reference witness, and is classified `saturated_on_ramp`. Re-evaluating
that same candidate shows `robustness_score` of exactly 0.0 on every instance - its worst-shift
utility sits at the *shipped baseline*. The searcher beat the witness on the visible axis and
gained nothing at all on the hidden one. Retiring the task on that evidence would discard a task
half of which is untouched.

This re-evaluates the best recorded candidate for each task and reports what the hidden axes say.
It cannot be read off the recorded trajectory: the visibility filter strips those metrics before
they are written, which is the whole point, so the candidate has to be scored again.

Usage:
    python scripts/report_saturation_hidden_axes.py --runs runs --output .research/hidden_axes.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.evaluate import evaluate_candidate  # noqa: E402
from sle.metric_visibility import SEARCH_VISIBLE_KEYS  # noqa: E402
from sle.registry import find_task, list_tasks  # noqa: E402

# An axis is "hidden" when the searcher never receives it. Anything normalised the same way the
# headline score is - zero at the shipped baseline, one at the reference - is comparable to it.
HIDDEN_AXIS_HINTS = ("robustness", "mechanism", "heldout", "confirmation", "refusal", "coverage")


def _best_candidate(task_id: str, runs_root: Path) -> Path | None:
    """The highest-scoring recorded program for this task, whichever cohort produced it."""
    best, best_score = None, None
    for manifest in runs_root.rglob("run_manifest.json"):
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if document.get("task_id") != task_id:
            continue
        program = manifest.parent / "best_program.py"
        checkpoint = manifest.parent / "checkpoint.json"
        if not program.is_file() or not checkpoint.is_file():
            continue
        try:
            score = json.loads(checkpoint.read_text(encoding="utf-8")).get("best_score")
        except (OSError, ValueError):
            continue
        if isinstance(score, (int, float)) and (best_score is None or score > best_score):
            best, best_score = program, score
    return best


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, default=ROOT / "runs")
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--task", default=None, help="check one task instead of the inventory")
    ap.add_argument("--timeout", type=float, default=900.0)
    args = ap.parse_args(argv)

    specs = [spec for spec in list_tasks(None)
             if args.task is None or spec.task_id == args.task]
    rows = []
    for spec in specs:
        program = _best_candidate(spec.task_id, args.runs)
        if program is None:
            rows.append({"task": spec.task_id, "status": "no recorded candidate on disk"})
            continue
        try:
            metrics = evaluate_candidate(spec, program, timeout_s=args.timeout)
        except Exception as error:  # noqa: BLE001 - reported per task, never fatal
            rows.append({"task": spec.task_id, "status": "could not score: %s" % str(error)[:160]})
            continue
        if metrics.get("infrastructure_failure"):
            rows.append({"task": spec.task_id, "status": "infrastructure failure while scoring"})
            continue
        hidden = {
            key: value for key, value in metrics.items()
            if key not in SEARCH_VISIBLE_KEYS
            and isinstance(value, (int, float)) and not isinstance(value, bool)
            and any(hint in key for hint in HIDDEN_AXIS_HINTS)
        }
        headline = metrics.get("combined_score")
        # A hidden axis sitting at zero means the candidate is exactly as good as the shipped
        # baseline there: the searcher gained nothing on it, whatever the headline says.
        untouched = sorted(key for key, value in hidden.items() if value == 0.0)
        rows.append({
            "task": spec.task_id,
            "status": "scored",
            "candidate": program.relative_to(ROOT).as_posix()  # noqa: E501
            if str(program).startswith(str(ROOT)) else str(program),
            "combined_score": headline,
            "hidden_axes": hidden,
            "hidden_axes_at_baseline": untouched,
        })
        if untouched:
            print("%-46s headline %-8s  untouched: %s" % (
                spec.task_id[:46],
                "%.4f" % headline if isinstance(headline, (int, float)) else headline,
                ", ".join(untouched[:3])))

    scored = [row for row in rows if row.get("status") == "scored"]
    half_done = [row for row in scored if row["hidden_axes_at_baseline"]]
    print()
    print("scored %d tasks; %d have a hidden axis still at the shipped baseline"
          % (len(scored), len(half_done)))
    if half_done:
        print("A saturation verdict on any of these describes the visible axis only.")

    if args.output:
        args.output.write_text(json.dumps({
            "schema_version": 1,
            "note": "hidden axes are evaluator-only by the visibility contract, so they cannot be "
                    "read off a recorded trajectory and the candidate is scored again here",
            "scored_task_count": len(scored),
            "tasks_with_a_hidden_axis_at_baseline": [row["task"] for row in half_done],
            "rows": rows,
        }, indent=2) + "\n", encoding="utf-8")
        print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
