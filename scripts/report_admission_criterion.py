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

# A second-half gain has to be big enough to be worth a searcher's budget before it counts as
# headroom. Without a floor, a control sitting at 0.9991 that drifts up by 0.0025 reads as "still
# climbing", which is noise wearing the label of opportunity. The threshold is a judgement, so it
# is named and printed rather than buried: a gain under this is reported as marginal, not as
# headroom, and marginal tasks are not proposed as candidates for paired follow-up.
MATERIAL_GAIN = 0.01

# Saturation read from a single seed is a guess. Measured: TrussWeightMinimization was ranked the
# strongest headroom candidate in the inventory on one seed showing a +0.4098 second-half gain;
# four paired seeds put that gain at +0.0000. A one-seed verdict is reported with the count
# attached so it cannot be mistaken for a measurement.
MIN_SEEDS_FOR_CONFIDENT_SATURATION = 3


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
        "marginal": 1e-6 < st.mean(gains) < MATERIAL_GAIN,
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
    if sat["marginal"]:
        return "marginal_headroom", (
            "open-loop gains only %+.4f over its second half, ending at %.4f; below the %.2f "
            "materiality threshold this is drift, not headroom"
            % (sat["mean_second_half_gain"], sat["mean_final"], MATERIAL_GAIN)
        )
    if not gaps and sat["seeds"] < MIN_SEEDS_FOR_CONFIDENT_SATURATION:
        return "headroom_single_seed", (
            "open-loop appears to climb (+%.4f over the second half, ending at %.4f) but on "
            "%d seed(s); below %d seeds this is not a saturation measurement"
            % (sat["mean_second_half_gain"], sat["mean_final"], sat["seeds"],
               MIN_SEEDS_FOR_CONFIDENT_SATURATION)
        )
    if not gaps:
        return "headroom_unverified", (
            "open-loop still climbing (+%.4f over the second half) but no paired feedback arm "
            "exists, so it is unknown whether the headroom is climbable"
            % sat["mean_second_half_gain"]
        )
    if len(gaps) < 2:
        only = gaps[0]
        return "gap_at_one_budget", (
            "gap is %+.4f at budget %d (%d/%d, n=%d), the only budget with paired runs; a "
            "single point cannot show whether the gap widens or closes"
            % (only["mean"], only["budget"], only["wins"], only["losses"], only["n"])
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

    # Saturation is a one-armed measurement, so open-loop seeds pool across cohorts: a seed run
    # under `screen3` says the same thing about this task's control as one run under
    # `saturation`. The gap does not pool - it compares two arms, and arms from different
    # cohorts were never paired with each other.
    pooled_open: dict[str, dict[int, list[float]]] = defaultdict(dict)
    for (task, cohort), arms in found.items():
        for mode in OPEN_LOOP_MODES:
            for seed, curve in arms.get(mode, {}).items():
                key = (cohort, seed)
                existing = pooled_open[task].get(key)
                if existing is None or len(curve) > len(existing):
                    pooled_open[task][key] = curve

    # One row per task. Saturation pools across cohorts, so a per-cohort row would repeat the
    # same saturation verdict once per cohort and inflate every count - after the screen cohort
    # landed, 52 tasks were being reported as 93 rows. Gaps stay per cohort, listed inside the
    # task's row, because two arms from different cohorts were never paired with each other.
    rows = []
    tasks_seen = sorted({task for task, _ in found})
    for task in tasks_seen:
        cohort_gaps = []
        for (other, cohort), arms in sorted(found.items()):
            if other != task:
                continue
            open_loop: dict[int, list[float]] = {}
            for mode in OPEN_LOOP_MODES:
                open_loop.update(arms.get(mode, {}))
            feedback: dict[int, list[float]] = {}
            for mode in FEEDBACK_MODES:
                feedback.update(arms.get(mode, {}))
            if not open_loop or not feedback:
                continue
            gaps = gap_by_budget(open_loop, feedback)
            if gaps:
                cohort_gaps.append({"cohort": cohort, "gaps": gaps,
                                    "seeds": len(set(open_loop) & set(feedback))})
        sat = saturation(pooled_open.get(task, {}))
        # Judge on the cohort that covers the most budgets, breaking ties on paired seeds.
        # Seeds alone is the wrong key: a cohort with eight seeds at a single budget cannot show
        # a trend at all, and ranking it first produced the verdict "gap grows with budget,
        # +0.1345 at 3 to +0.1345 at 3" - one point compared with itself.
        best = max(
            cohort_gaps, key=lambda c: (len(c["gaps"]), c["seeds"]), default=None
        )
        state, why = verdict(sat, best["gaps"] if best else [])
        rows.append({
            "task": task,
            "verdict": state,
            "reason": why,
            "judged_on_cohort": best["cohort"] if best else None,
            "pooled_open_loop_seeds": len(pooled_open.get(task, {})),
            "paired_cohorts": cohort_gaps,
            "saturation": sat,
            "gap_by_budget": best["gaps"] if best else [],
        })

    # Every verdict carries how many open-loop seeds stand behind it. Most of this inventory was
    # screened one seed per task, and one seed misled in the case that was checked, so a verdict
    # without its seed count reads as far more settled than it is.
    for row in rows:
        seeds = row["saturation"]["seeds"] if row["saturation"] else 0
        row["confidence"] = (
            "measured" if seeds >= MIN_SEEDS_FOR_CONFIDENT_SATURATION
            else "single_seed_screen" if seeds else "none"
        )

    order = {
        "measures_iteration": 0, "crossover_in_range": 1, "headroom_unclimbable": 2,
        "gap_at_one_budget": 3, "headroom_unverified": 4, "headroom_single_seed": 5,
        "marginal_headroom": 6, "no_headroom": 7, "floor": 8, "unknown": 9,
    }
    rows.sort(key=lambda r: (order[r["verdict"]], r["task"]))

    def short(task_id: str) -> str:
        """Drop the domain prefix; the task name is what distinguishes rows here."""
        return task_id.split("/")[-1][:34]

    print("%-34s %-22s %5s %s" % ("task", "verdict", "pool", "confidence"))
    print("-" * 84)
    for row in rows:
        print("%-34s %-22s %5d %s" % (
            short(row["task"]), row["verdict"],
            row["pooled_open_loop_seeds"], row["confidence"]))
        print("      %s" % row["reason"])
        for entry in row["paired_cohorts"]:
            marker = " <- judged" if entry["cohort"] == row["judged_on_cohort"] else ""
            print("      cohort %s, %d paired seeds%s" % (
                entry["cohort"], entry["seeds"], marker))
            for gap in entry["gaps"]:
                print("        budget %2d  gap %+8.4f  se %.4f  %d/%d  n=%d" % (
                    gap["budget"], gap["mean"], gap["stderr"],
                    gap["wins"], gap["losses"], gap["n"]))

    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["verdict"]] += 1
    paired = sum(1 for row in rows if row["gap_by_budget"])
    tasks = {row["task"] for row in rows}
    tasks_paired = {row["task"] for row in rows if row["gap_by_budget"]}
    tasks_measuring = {row["task"] for row in rows if row["verdict"] == "measures_iteration"}
    judged = [r for r in rows if r["confidence"] != "none"]
    thin_screen = [r for r in judged if r["confidence"] == "single_seed_screen"]
    print()
    print("verdicts by task:", dict(sorted(counts.items())))
    print("saturation verdicts resting on fewer than %d open-loop seeds: %d of %d (%.0f%%)"
          % (MIN_SEEDS_FOR_CONFIDENT_SATURATION, len(thin_screen), len(judged),
             100.0 * len(thin_screen) / len(judged) if judged else 0.0))
    thin_by_verdict: dict[str, int] = defaultdict(int)
    for row in thin_screen:
        thin_by_verdict[row["verdict"]] += 1
    print("  of those:", dict(sorted(thin_by_verdict.items())))
    print("  a single seed misread the one case that was later paired, and it misread it as")
    print("  climbing, so the no_headroom and floor verdicts above may understate headroom")
    print("  just as the headroom ones overstated it.")
    print("distinct tasks: %d" % len(tasks))
    assert len(rows) == len(tasks), "one row per task"
    print("distinct tasks with paired evidence for the sufficient condition: %d of %d"
          % (len(tasks_paired), len(tasks)))
    print("distinct tasks shown to measure iteration: %d" % len(tasks_measuring))
    for name in sorted(tasks_measuring):
        print("   ", name)

    # The only pool that can add qualifying tasks: real headroom, never paired.
    # One entry per task, not per (task, cohort): saturation now pools across cohorts, so a task
    # present in four cohorts would otherwise be listed four identical times. A task that has
    # been paired anywhere is not a candidate, however its other cohorts happen to be labelled.
    paired_tasks = {row["task"] for row in rows if row["gap_by_budget"]}
    best_by_task: dict[str, tuple] = {}
    for row in rows:
        if row["verdict"] not in ("headroom_unverified", "headroom_single_seed"):
            continue
        if row["task"] in paired_tasks:
            continue
        sat = row["saturation"]
        best_by_task[row["task"]] = (
            sat["mean_second_half_gain"], sat["mean_final"], sat["seeds"],
            row["task"], row["verdict"],
        )
    candidates = sorted(best_by_task.values(), reverse=True)
    print()
    print("worth pairing next (apparent headroom, no feedback arm ever run), gain floor %.2f:"
          % MATERIAL_GAIN)
    for gain, final, seeds, name, state in candidates:
        note = "  [thin screen]" if state == "headroom_single_seed" else ""
        print("    %-34s gain %+.4f  ending at %.4f  seeds=%d%s"
              % (name.split("/")[-1], gain, final, seeds, note))
    thin = sum(1 for c in candidates if c[4] == "headroom_single_seed")
    if thin:
        print("  %d of %d rest on fewer than %d pooled open-loop seeds. The first such candidate"
              % (thin, len(candidates), MIN_SEEDS_FOR_CONFIDENT_SATURATION))
        print("  that was actually paired, TrussWeightMinimization, showed no second-half gain")
        print("  once four seeds were run, so treat the ranking as a queue, not a finding.")

    Path(args.output).write_text(json.dumps({
        "schema_version": 2,
        "note": "condition 1 (open-loop non-saturation) is necessary; condition 2 (a feedback "
                "gap that does not close with budget) is what makes a task measure iteration",
        "budgets": list(BUDGETS),
        "row_count": len(rows),
        "note_rows": "one row per task; paired gaps listed per cohort inside each row",
        "distinct_task_count": len(tasks),
        "distinct_tasks_with_paired_evidence": len(tasks_paired),
        "distinct_tasks_measuring_iteration": sorted(tasks_measuring),
        "paired_evidence_row_count": paired,
        "verdict_counts": dict(counts),
        "single_seed_screen_count": len(thin_screen),
        "judged_count": len(judged),
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
