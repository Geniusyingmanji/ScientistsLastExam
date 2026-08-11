#!/usr/bin/env python3
"""Report each task against the two-part admission criterion, and where the evidence is missing.

A task earns its place in this benchmark by measuring iterative improvement. That takes two
things, and the order matters:

    1. necessary   the open-loop control must not saturate with budget. If best-of-N stops
                   paying after a few draws, there is nothing left for a searcher to add.
    2. sufficient  the feedback arm must beat the open-loop arm, and the gap should widen with
                   budget rather than close. Headroom that no searcher can climb is not headroom
                   that measures anything.

Condition 1 alone was the earlier criterion, and it is not enough. A measured counterexample is
in this repository: MolecularLeadOptimization at (320, 0.20) has a strictly climbing open-loop
curve and an evolvability gap that is flat at zero across budgets 3 to 12, because every proposal
sits on a low plateau with no exploitable gradient. Passing 1 and failing 2 means the task is too
hard to measure with, not that it is a good task.

Condition 2 needs paired runs — the same task, same budget, `selection_blind` against `normal`.
Most tasks in this inventory have never had them, and this report says so rather than inferring a
verdict from the one arm that exists. "unknown" here is a statement about the evidence, not about
the task.

Usage:
    python scripts/report_admission_criterion.py --runs runs --output /tmp/admission.json
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

# Budgets the gap is reported at. The shape across these matters more than any single endpoint:
# a gap that grows is evidence of iteration paying off, one that peaks and turns over means
# best-of-N overtakes the searcher past the crossover.
BUDGETS = (3, 5, 8, 10, 12)

OPEN_LOOP_MODES = ("selection_blind", "blind")
FEEDBACK_MODES = ("normal",)


def best_so_far(path: Path) -> list[float] | None:
    """The best-so-far curve over proposals. Invalid proposals score zero, as the harness does."""
    if not path.is_file():
        return None
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    proposals = sorted(
        (r for r in rows if int(r.get("step", 0) or 0) > 0),
        key=lambda r: int(r["step"]),
    )
    if not proposals:
        return None
    curve, best = [], 0.0
    for row in proposals:
        score = float(row.get("score") or 0.0) if row.get("valid") else 0.0
        best = max(best, score)
        curve.append(best)
    return curve


def run_identity(workdir: Path) -> tuple[str, str, int] | None:
    """Read (task, feedback mode, seed) from the run manifest.

    The directory name cannot be trusted for this. Budget-sweep cohorts are named for their
    budget rather than their task - `runs/crossover/b20_normal_s0` - so parsing the name invents
    tasks called "b20" and silently splits one task's evidence across several fictitious ones.
    The manifest records the task, the mode and the seed authoritatively.
    """
    manifest = workdir / "run_manifest.json"
    if not manifest.is_file():
        return None
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    task = document.get("task_id")
    mode = document.get("feedback_mode")
    seed = document.get("seed")
    if not task or not mode or seed is None:
        return None
    return str(task), str(mode), int(seed)


def collect(runs_root: Path) -> dict[tuple[str, str], dict[str, dict[int, list[float]]]]:
    """Group curves by (task, cohort).

    Cohorts are kept apart on purpose. A run under `runs/crossover` was made at a different
    budget from one under `runs/saturation`, and averaging a gap across them would compare arms
    that were never paired.
    """
    found: dict[tuple[str, str], dict[str, dict[int, list[float]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for trajectory in runs_root.glob("*/*/trajectory.jsonl"):
        workdir = trajectory.parent
        identity = run_identity(workdir)
        if identity is None:
            continue
        task, mode, seed = identity
        curve = best_so_far(trajectory)
        if curve is None:
            continue
        key = (task, workdir.parent.name)
        existing = found[key][mode].get(seed)
        if existing is None or len(curve) > len(existing):
            found[key][mode][seed] = curve
    return found


def saturation(curves: dict[int, list[float]]) -> dict | None:
    """Does the open-loop control still improve over the second half of its budget?"""
    usable = [c for c in curves.values() if len(c) >= 6]
    if not usable:
        return None
    gains, finals = [], []
    for curve in usable:
        midpoint = curve[len(curve) // 2 - 1]
        gains.append(curve[-1] - midpoint)
        finals.append(curve[-1])
    return {
        "seeds": len(usable),
        "mean_second_half_gain": st.mean(gains),
        "mean_final": st.mean(finals),
        # A control that never leaves zero is a floor, which is a different failure from
        # saturating high, and the two must not be reported as the same verdict.
        "is_floor": max(finals) <= 1e-9,
        "saturated": st.mean(gains) <= 1e-6,
    }


def gap_by_budget(open_loop: dict[int, list[float]], feedback: dict[int, list[float]]) -> list[dict]:
    """Paired gap at each budget, over seeds present in both arms."""
    shared = sorted(set(open_loop) & set(feedback))
    out = []
    for budget in BUDGETS:
        deltas = []
        for seed in shared:
            a, b = open_loop[seed], feedback[seed]
            if len(a) < budget or len(b) < budget:
                continue
            deltas.append(b[budget - 1] - a[budget - 1])
        if len(deltas) < 2:
            continue
        stdev = st.stdev(deltas)
        out.append({
            "budget": budget,
            "n": len(deltas),
            "mean": st.mean(deltas),
            "stderr": stdev / math.sqrt(len(deltas)),
            "wins": sum(1 for d in deltas if d > 0),
            "losses": sum(1 for d in deltas if d < 0),
        })
    return out


def verdict(sat: dict | None, gaps: list[dict]) -> tuple[str, str]:
    if sat is None:
        return "unknown", "no open-loop run long enough to judge saturation"
    if sat["is_floor"]:
        return "floor", "open-loop control never leaves zero"
    if sat["saturated"]:
        return "no_headroom", (
            "open-loop control gains %.4f over its second half" % sat["mean_second_half_gain"]
        )
    if not gaps:
        return "headroom_unverified", (
            "open-loop still climbing (+%.4f over the second half) but no paired feedback arm "
            "exists, so it is unknown whether the headroom is climbable"
            % sat["mean_second_half_gain"]
        )
    first, last = gaps[0], gaps[-1]
    if last["mean"] <= 0:
        return "headroom_unclimbable", (
            "gap is %+.4f at budget %d; headroom exists but feedback does not exploit it"
            % (last["mean"], last["budget"])
        )
    if last["mean"] >= first["mean"]:
        return "measures_iteration", (
            "gap grows with budget, %+.4f at %d to %+.4f at %d (%d/%d at the last budget)"
            % (first["mean"], first["budget"], last["mean"], last["budget"],
               last["wins"], last["wins"] + last["losses"])
        )
    return "crossover_in_range", (
        "gap peaks then narrows, %+.4f at %d down to %+.4f at %d; best-of-N is catching up"
        % (first["mean"], first["budget"], last["mean"], last["budget"])
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, help="directory holding run cohorts")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    found = collect(Path(args.runs))
    rows = []
    for key in sorted(found):
        task, cohort = key
        arms = found[key]
        open_loop: dict[int, list[float]] = {}
        for mode in OPEN_LOOP_MODES:
            open_loop.update(arms.get(mode, {}))
        feedback: dict[int, list[float]] = {}
        for mode in FEEDBACK_MODES:
            feedback.update(arms.get(mode, {}))
        sat = saturation(open_loop)
        gaps = gap_by_budget(open_loop, feedback) if open_loop and feedback else []
        state, why = verdict(sat, gaps)
        rows.append({
            "task": task,
            "cohort": cohort,
            "verdict": state,
            "reason": why,
            "open_loop_seeds": len(open_loop),
            "feedback_seeds": len(feedback),
            "saturation": sat,
            "gap_by_budget": gaps,
        })

    # A task may appear under several cohorts; report each, and count distinct tasks separately
    # so a well-sampled task does not look like several passing ones.
    order = {
        "measures_iteration": 0, "crossover_in_range": 1, "headroom_unclimbable": 2,
        "headroom_unverified": 3, "no_headroom": 4, "floor": 5, "unknown": 6,
    }
    rows.sort(key=lambda r: (order[r["verdict"]], r["task"]))

    def short(task_id: str) -> str:
        """Drop the domain prefix; the task name is what distinguishes rows here."""
        return task_id.split("/")[-1][:34]

    print("%-34s %-14s %-22s %5s %4s" % ("task", "cohort", "verdict", "open", "fb"))
    print("-" * 84)
    for row in rows:
        print("%-34s %-14s %-22s %5d %4d" % (
            short(row["task"]), row["cohort"][:14], row["verdict"],
            row["open_loop_seeds"], row["feedback_seeds"]))
        print("      %s" % row["reason"])
        for gap in row["gap_by_budget"]:
            print("        budget %2d  gap %+8.4f  se %.4f  %d/%d  n=%d" % (
                gap["budget"], gap["mean"], gap["stderr"], gap["wins"], gap["losses"], gap["n"]))

    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["verdict"]] += 1
    paired = sum(1 for row in rows if row["gap_by_budget"])
    tasks = {row["task"] for row in rows}
    tasks_paired = {row["task"] for row in rows if row["gap_by_budget"]}
    tasks_measuring = {row["task"] for row in rows if row["verdict"] == "measures_iteration"}
    print()
    print("verdicts by (task, cohort):", dict(sorted(counts.items())))
    print("distinct tasks: %d" % len(tasks))
    print("distinct tasks with paired evidence for the sufficient condition: %d of %d"
          % (len(tasks_paired), len(tasks)))
    print("distinct tasks shown to measure iteration: %d" % len(tasks_measuring))
    for name in sorted(tasks_measuring):
        print("   ", name)

    Path(args.output).write_text(json.dumps({
        "schema_version": 2,
        "note": "condition 1 (open-loop non-saturation) is necessary; condition 2 (a feedback "
                "gap that does not close with budget) is what makes a task measure iteration",
        "budgets": list(BUDGETS),
        "row_count": len(rows),
        "distinct_task_count": len(tasks),
        "distinct_tasks_with_paired_evidence": len(tasks_paired),
        "distinct_tasks_measuring_iteration": sorted(tasks_measuring),
        "paired_evidence_row_count": paired,
        "verdict_counts": dict(counts),
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
