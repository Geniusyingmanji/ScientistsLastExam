#!/usr/bin/env python3
"""Report each task against the two-part admission criterion, and where the evidence is missing.

A task earns its place in this benchmark by measuring iterative improvement. That takes two
things, and the order matters:

    1. necessary   the open-loop control must SATURATE with budget. A control that keeps climbing
                   means best-of-N is not exhausted, and independent sampling will eventually
                   overtake any searcher - so whatever gap you measured was an artefact of the
                   budget you happened to pick.
    2. sufficient  with best-of-N exhausted, the feedback arm must still beat it, and the gap
                   must widen with budget rather than close.

The sign of condition 1 is the opposite of what it first looks like, and an earlier version of
this script had it backwards. The evidence is in the repository: the decoder's open-loop control
is flat from budget 5 onward and its feedback arm pulls further ahead the longer it runs, while
the molecular task's control climbs 0.404 to 0.970 and its gap crosses zero near budget 7.8.
Refining beats redrawing precisely where redrawing has stopped paying.

A saturated control is not the same as a solved task: `floor` (the control never leaves zero) is
reported separately, because nothing can be measured there either way.

Condition 2 needs paired runs - the same task, same budget, `selection_blind` against `normal`.
Most tasks in this inventory have never had them, and this report says so rather than inferring a
verdict from the one arm that exists. "unknown" here is a statement about the evidence, not about
the task.

Usage:
    python scripts/report_admission_criterion.py --runs runs --output /tmp/admission.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Budgets the gap is reported at. The shape across these matters more than any single endpoint:
# a gap that grows is evidence of iteration paying off, one that peaks and turns over means
# best-of-N overtakes the searcher past the crossover.
BUDGETS = (3, 5, 8, 10, 12)

# Why the comparability key is `task_package_sha256` and not `task_contract_sha256`.
#
# Both are recorded in every manifest. The contract hash is narrower - Task.md, the initial
# program, verification/evaluator.py and the eval metadata - and it is tempting as the key,
# because it would not reject a comparison over a task whose only change was a note in its card.
#
# It is too narrow for this job. It does not cover the rest of verification/: the reference
# implementations and frozen data that several tasks recompute their anchor from at scoring time.
# Editing RNAEnsembleDesign's reference designer changes what a score means without moving the
# contract hash at all.
#
# The two failure modes are not symmetric. Rejecting a comparison that would have been valid
# costs a comparison and says so out loud. Accepting one that is not valid puts a task change
# into a report as a model difference, which is the error this whole guard exists to prevent -
# on one task it read as an eighteen-fold gap. So the broader hash wins.
#
# Measured, in case the narrower one ever looks tempting again: on this inventory the two agree
# exactly. The same 20 of 54 tasks carry more than one version under either hash, so nothing is
# currently being rejected that the contract hash would have allowed.

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

# A gap counts as a difference only if it is large next to the scores being compared. Sign alone
# is not enough: the RNA design task's feedback arm trailed by 0.0021 against scores near 1.0 -
# two parts in a thousand - and the criterion called that "harmful", the same word it gave a task
# trailing by 0.37 against scores near 0.5. Below this fraction of the open-loop mean, the arms
# are reported as indistinguishable.
MATERIAL_GAP_FRACTION = 0.02

# A clipped task whose control reaches its cap is not "exhausted and awaiting a feedback arm" - it
# is solved, and pairing it can only measure zero. Seven certified tasks sit here or near it, so
# the report names the condition rather than leaving it to be inferred from a column.
CEILING = 0.99


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


def score_modes() -> dict[str, str]:
    """Score mode per task, so a control at 1.000 can be read as a cap rather than a coincidence.

    This must not fail quietly. An earlier version caught the import error and returned an empty
    map, which made every task default to clipped and reported three uncapped tasks - including
    one whose control sits at 1.061, above any cap - as solved at their ceiling. The failure was
    invisible because the fallback was a plausible-looking answer.
    """
    from frontier_science.registry import list_tasks

    return {spec.task_id: str(spec.metadata.get("score_mode", "clipped"))
            for spec in list_tasks(None)}


def known_conditions() -> dict[str, str]:
    """Condition hash to model, for manifests written before the readable field existed.

    Recovering the attribution rather than rewriting the manifests: the artifacts stay as they
    were recorded, and the mapping is a separate auditable file.
    """
    import yaml

    path = ROOT / "frontier_science" / "llm_conditions.yaml"
    if not path.is_file():
        return {}
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(h): str(entry.get("model") or "unrecorded")
            for h, entry in (document.get("conditions") or {}).items()}


_CONDITIONS: dict[str, str] | None = None


def run_identity(workdir: Path) -> tuple[str, str, int, str, str] | None:
    """Read (task, feedback mode, seed, model, task version) from the run manifest.

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
    # Runs recorded before the manifest carried a readable model condition are labelled as such
    # rather than silently pooled with a known model: a gap computed across two model families is
    # not a gap, and this is the field that stops that happening by accident.
    model = str((document.get("llm_condition") or {}).get("model") or "")
    if not model:
        global _CONDITIONS
        if _CONDITIONS is None:
            _CONDITIONS = known_conditions()
        model = _CONDITIONS.get(str(document.get("llm_condition_sha256") or ""), "unrecorded")
    # The version of the task the run was made against. Twenty tasks in this tree carry more than
    # one, because tasks were edited between cohorts, and evidence from two versions is evidence
    # about two different tasks.
    contract = str(document.get("task_package_sha256") or "unknown")[:12]
    return str(task), str(mode), int(seed), model, contract


def collect(runs_root: Path) -> dict[tuple[str, str, str, str],
                                     dict[str, dict[int, list[float]]]]:
    """Group curves by (task, cohort, model, task version).

    Cohorts are kept apart because a run under `runs/crossover` was made at a different budget
    from one under `runs/saturation`, and averaging a gap across them would compare arms that
    were never paired.

    Models are kept apart for a stronger reason. The crossover budget is a property of the task
    and the searcher together, so a gap measured with one model says nothing about another. With
    a second model family now producing runs into the same tree, pooling would have quietly
    averaged Claude against GPT and reported the mean as though it were one measurement.

    Task versions are kept apart for the third form of the same mistake. `task_package_sha256`
    records which version of a task a run was made against, and twenty of the tasks here have
    more than one across cohorts. Saturation pools open-loop seeds across cohorts, so without
    this key it pooled seeds taken against two different versions of the task and asked whether
    best-of-N had stopped improving on the union - a question about no task in particular.
    """
    found: dict[tuple[str, str, str, str], dict[str, dict[int, list[float]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for trajectory in runs_root.glob("*/*/trajectory.jsonl"):
        workdir = trajectory.parent
        identity = run_identity(workdir)
        if identity is None:
            continue
        task, mode, seed, model, contract = identity
        curve = best_so_far(trajectory)
        if curve is None:
            continue
        key = (task, workdir.parent.name, model, contract)
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
    # Judge on the median gain, not the mean. A best-so-far curve is monotone, so a second-half
    # gain is never negative, and the mean over seeds can therefore only rise as seeds are added:
    # one climbing seed drags a set of otherwise flat controls above the threshold. That is a
    # property of the statistic, not of the task. It showed up as a one-way sweep — when a second
    # and third seed were added across this inventory, 17 of 52 tasks moved from "no headroom"
    # toward "headroom" and not one moved back. The median asks the question actually meant here:
    # does a typical run of this control still improve.
    median_gain = st.median(gains)
    # Would this decision have come out the same on the smallest seed count the criterion is
    # willing to trust? The necessary condition is a threshold test, and this report already
    # declares MIN_SEEDS_FOR_CONFIDENT_SATURATION seeds sufficient to decide it - so if some
    # subset of that size disagrees with the full sample, that declaration is wrong for this task
    # and the verdict is a property of which seeds happened to be run.
    #
    # Leave-one-out was tried first and is too weak to see this. LowThrustTransfer reads as
    # exhausted at 0.0053 over six seeds and as still climbing at 0.0193 over the first three;
    # dropping a single seed from six never moves the median far enough to flip, so leave-one-out
    # reported zero fragile verdicts on an inventory where the seed-matched comparison had just
    # shown one.
    exhausted = median_gain < MATERIAL_GAIN
    fragile = None
    k = MIN_SEEDS_FOR_CONFIDENT_SATURATION
    if len(gains) > k:
        subsets = list(itertools.combinations(gains, k))
        # Every subset, unless there are absurdly many; the count is tiny at realistic seed
        # numbers and a cap keeps a future large sweep from stalling here.
        agree = sum(1 for s in subsets[:2000]
                    if (st.median(s) < MATERIAL_GAIN) == exhausted)
        fragile = agree < len(subsets[:2000])
    return {
        "seeds": len(usable),
        # Undecidable with two seeds or fewer: any leave-one-out is then a single curve.
        # None means undecidable: with no more seeds than the minimum, there is no smaller
        # trusted subset to disagree, so the stability of the verdict is simply unknown.
        "seed_fragile": fragile,
        "median_second_half_gain": median_gain,
        "mean_second_half_gain": st.mean(gains),
        "max_second_half_gain": max(gains),
        "mean_final": st.mean(finals),
        # A control that never leaves zero is a floor, which is a different failure from
        # saturating high, and the two must not be reported as the same verdict.
        "is_floor": max(finals) <= 1e-9,
        "saturated": median_gain <= 1e-6,
        "marginal": 1e-6 < median_gain < MATERIAL_GAIN,
    }


def gap_by_budget(open_loop: dict[int, list[float]], feedback: dict[int, list[float]]) -> list[dict]:
    """Paired gap at each budget, over seeds present in both arms."""
    shared = sorted(set(open_loop) & set(feedback))
    out = []
    for budget in BUDGETS:
        deltas, opens = [], []
        for seed in shared:
            a, b = open_loop[seed], feedback[seed]
            if len(a) < budget or len(b) < budget:
                continue
            deltas.append(b[budget - 1] - a[budget - 1])
            opens.append(a[budget - 1])
        if len(deltas) < 2:
            continue
        stdev = st.stdev(deltas)
        mean = st.mean(deltas)
        # Every paired verdict here rests on four to six seeds, where one seed can carry the
        # result. `leave_one_out_worst` is the mean after dropping whichever single seed helps
        # the conclusion most: if it crosses zero, the verdict is one seed deep.
        if len(deltas) > 2:
            drops = [st.mean([d for j, d in enumerate(deltas) if j != i])
                     for i in range(len(deltas))]
            loo = min(drops) if mean > 0 else max(drops)
        else:
            loo = None
        out.append({
            "budget": budget,
            "n": len(deltas),
            "mean": mean,
            "stderr": stdev / math.sqrt(len(deltas)),
            "open_loop_mean": st.mean(opens) if opens else 0.0,
            "material": abs(mean) >= MATERIAL_GAP_FRACTION * max(abs(st.mean(opens)), 1e-9),
            "leave_one_out_worst": loo,
            "robust_to_one_seed": None if loo is None else (loo > 0) == (mean > 0),
            "wins": sum(1 for d in deltas if d > 0),
            "losses": sum(1 for d in deltas if d < 0),
        })
    return out


def verdict(sat: dict | None, gaps: list[dict], clipped: bool = False) -> tuple[str, str]:
    if sat is None:
        return "unknown", "no open-loop run long enough to judge saturation"
    if sat["is_floor"]:
        return "floor", "open-loop control never leaves zero, so nothing is measurable here"
    if sat["seeds"] < MIN_SEEDS_FOR_CONFIDENT_SATURATION:
        return "thin_screen", (
            "judged on %d open-loop seed(s); below %d this is a screen, not a measurement "
            "(median second-half gain %+.4f, ending at %.4f)"
            % (sat["seeds"], MIN_SEEDS_FOR_CONFIDENT_SATURATION,
               sat["median_second_half_gain"], sat["mean_final"])
        )
    if not sat["saturated"] and not sat["marginal"]:
        return "control_not_exhausted", (
            "open-loop control still gains %+.4f over its second half at the median seed, so "
            "best-of-N has not run out and any gap measured here depends on the budget chosen"
            % sat["median_second_half_gain"]
        )
    if clipped and sat["mean_final"] >= CEILING:
        return "solved_at_ceiling", (
            "clipped scoring with the open-loop control at %.4f, which is the cap; there is "
            "nothing above the anchor for a searcher to reach and pairing can only measure zero"
            % sat["mean_final"]
        )
    # Best-of-N is exhausted. Whether the task measures iteration now rests entirely on the gap.
    if not gaps:
        return "exhausted_unpaired", (
            "open-loop control is exhausted (median gain %+.4f, ending at %.4f) but no paired "
            "feedback arm exists, so it is unknown whether a searcher can go further"
            % (sat["median_second_half_gain"], sat["mean_final"])
        )
    if len(gaps) < 2:
        only = gaps[0]
        return "gap_at_one_budget", (
            "gap is %+.4f at budget %d (%d/%d, n=%d), the only budget with paired runs; a "
            "single point cannot show whether the gap widens or closes"
            % (only["mean"], only["budget"], only["wins"], only["losses"], only["n"])
        )
    first, last = gaps[0], gaps[-1]
    if not last.get("material", True):
        return "no_measurable_difference", (
            "gap is %+.4f at budget %d against an open-loop mean of %.4f - under %.0f%% of it, "
            "so the arms are indistinguishable rather than one being better"
            % (last["mean"], last["budget"], last["open_loop_mean"],
               100 * MATERIAL_GAP_FRACTION)
        )
    if last["mean"] <= 0:
        if last.get("robust_to_one_seed") is False:
            return "feedback_harmful_one_seed_deep", (
                "gap is %+.4f at budget %d, but dropping a single seed takes it to %+.4f - "
                "the conclusion that feedback hurts rests on one paired seed"
                % (last["mean"], last["budget"], last["leave_one_out_worst"])
            )
        return "feedback_harmful", (
            "gap is %+.4f at budget %d (%d/%d): the feedback arm does worse than its own "
            "open-loop control"
            % (last["mean"], last["budget"], last["wins"], last["losses"])
        )
    if last["mean"] >= first["mean"]:
        if last.get("robust_to_one_seed") is False:
            return "measures_iteration_one_seed_deep", (
                "gap grows to %+.4f at budget %d, but dropping a single seed takes it to "
                "%+.4f - the conclusion rests on one paired seed"
                % (last["mean"], last["budget"], last["leave_one_out_worst"])
            )
        return "measures_iteration", (
            "control exhausted and the gap still grows, %+.4f at %d to %+.4f at %d "
            "(%d/%d at the last budget, n=%d)"
            % (first["mean"], first["budget"], last["mean"], last["budget"],
               last["wins"], last["wins"] + last["losses"], last["n"]))
    return "crossover_in_range", (
        "gap peaks then narrows, %+.4f at %d down to %+.4f at %d; best-of-N is catching up"
        % (first["mean"], first["budget"], last["mean"], last["budget"])
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, help="directory holding run cohorts")
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)

    found = collect(Path(args.runs))
    modes = score_modes()

    # Saturation is a one-armed measurement, so open-loop seeds pool across cohorts: a seed run
    # under `screen3` says the same thing about this task's control as one run under
    # `saturation`. The gap does not pool - it compares two arms, and arms from different
    # cohorts were never paired with each other.
    # Saturation pools across cohorts but never across models, for the same reason gaps do not.
    pooled_open: dict[tuple[str, str, str], dict[tuple[str, int], list[float]]] = defaultdict(dict)
    for (task, cohort, model, contract), arms in found.items():
        for mode in OPEN_LOOP_MODES:
            for seed, curve in arms.get(mode, {}).items():
                key = (cohort, seed)
                existing = pooled_open[(task, model, contract)].get(key)
                if existing is None or len(curve) > len(existing):
                    pooled_open[(task, model, contract)][key] = curve

    # One row per task. Saturation pools across cohorts, so a per-cohort row would repeat the
    # same saturation verdict once per cohort and inflate every count - after the screen cohort
    # landed, 52 tasks were being reported as 93 rows. Gaps stay per cohort, listed inside the
    # task's row, because two arms from different cohorts were never paired with each other.
    rows = []
    # One row per (task, model): the same task measured by two model families is two
    # measurements, and collapsing them would hide exactly the disagreement worth reporting.
    # ... and one row per task version, for the same reason: a verdict is a statement about a
    # particular version of a task, and two versions cannot share one.
    pairs_seen = sorted({(task, model, contract) for task, _c, model, contract in found})
    for task, model, contract in pairs_seen:
        cohort_gaps = []
        for (other, cohort, other_model, other_contract), arms in sorted(found.items()):
            if other != task or other_model != model or other_contract != contract:
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
        sat = saturation(pooled_open.get((task, model, contract), {}))
        # Judge on the cohort that covers the most budgets, breaking ties on paired seeds.
        # Seeds alone is the wrong key: a cohort with eight seeds at a single budget cannot show
        # a trend at all, and ranking it first produced the verdict "gap grows with budget,
        # +0.1345 at 3 to +0.1345 at 3" - one point compared with itself.
        best = max(
            cohort_gaps, key=lambda c: (len(c["gaps"]), c["seeds"]), default=None
        )
        state, why = verdict(sat, best["gaps"] if best else [],
                             clipped=modes.get(task, "clipped") != "uncapped")
        rows.append({
            "task": task,
            "model": model,
            "task_version": contract,
            "verdict": state,
            "reason": why,
            "judged_on_cohort": best["cohort"] if best else None,
            "pooled_open_loop_seeds": len(pooled_open.get((task, model, contract), {})),
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
        "measures_iteration": 0, "measures_iteration_one_seed_deep": 1,
        "solved_at_ceiling": 90,
        "crossover_in_range": 2, "feedback_harmful": 3,
        "feedback_harmful_one_seed_deep": 4, "no_measurable_difference": 5,
        "gap_at_one_budget": 6, "exhausted_unpaired": 7, "control_not_exhausted": 8,
        "thin_screen": 9, "floor": 10, "unknown": 11,
    }
    rows.sort(key=lambda r: (order[r["verdict"]], r["task"]))

    def short(task_id: str) -> str:
        """Drop the domain prefix; the task name is what distinguishes rows here."""
        return task_id.split("/")[-1]

    print("%-30s %-16s %-22s %5s %s" % (
        "task", "model", "verdict", "used", "confidence"))
    print("-" * 96)
    for row in rows:
        # Show the seeds the verdict actually rests on, not how many exist. A run shorter than
        # six proposals cannot be judged for saturation and is excluded, so the two differ.
        used = row["saturation"]["seeds"] if row["saturation"] else 0
        extra = ("" if used == row["pooled_open_loop_seeds"]
                 else " (%d too short to judge)" % (row["pooled_open_loop_seeds"] - used))
        print("%-30s %-16s %-22s %5d %s%s" % (
            short(row["task"])[:30], row["model"][:16], row["verdict"], used,
            row["confidence"], extra))
        print("      %s" % row["reason"])
        for entry in row["paired_cohorts"]:
            marker = " <- judged" if entry["cohort"] == row["judged_on_cohort"] else ""
            print("      cohort %s, %d paired seeds%s" % (
                entry["cohort"], entry["seeds"], marker))
            for gap in entry["gaps"]:
                loo = gap["leave_one_out_worst"]
                tail = ("" if loo is None else
                        "  loo %+.4f%s" % (loo, "" if gap["robust_to_one_seed"] else " FLIPS"))
                print("        budget %2d  gap %+8.4f  se %.4f  %d/%d  n=%d%s" % (
                    gap["budget"], gap["mean"], gap["stderr"],
                    gap["wins"], gap["losses"], gap["n"], tail))

    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["verdict"]] += 1
    paired = sum(1 for row in rows if row["gap_by_budget"])
    tasks = {row["task"] for row in rows}
    tasks_paired = {row["task"] for row in rows if row["gap_by_budget"]}
    tasks_measuring = {row["task"] for row in rows if row["verdict"] == "measures_iteration"}
    models = sorted({row["model"] for row in rows})

    # Where two models measured the same task, whether they agree is the question a single-model
    # verdict cannot answer, so it is printed rather than left to be read off the table.
    # `unrecorded` is the absence of a model, not a third model. Counting it as one makes every
    # task with a pre-attribution run look contested: the first cross-model report showed 16
    # disagreements of which most were a known model against "we do not know which model".
    # Keyed by task version as well as task. Two models that ran different versions of a task
    # were not measuring the same thing, and reading their verdicts as a disagreement attributes
    # a task edit to the models: before this key was added, LowThrustTransfer was reported as a
    # three-way disagreement while only two of the three had run the same task.
    by_version: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for row in rows:
        if row["model"] == "unrecorded":
            continue
        by_version[(row["task"], row["task_version"])][row["model"]] = row["verdict"]
    contested = {"%s @%s" % (task, version): verdicts
                 for (task, version), verdicts in by_version.items()
                 if len(verdicts) > 1 and len(set(verdicts.values())) > 1}
    agreed = {"%s @%s" % (task, version): verdicts
              for (task, version), verdicts in by_version.items()
              if len(verdicts) > 1 and len(set(verdicts.values())) == 1}
    # Counted so that "the models disagree less now" cannot be mistaken for better agreement when
    # it is really less overlap.
    split_by_version = sorted({task for task, _v in by_version
                               if len({v for t, v in by_version if t == task}) > 1})
    # A run can abort mid-trajectory - an evaluator infrastructure failure ends one outright -
    # and a short curve then looks like a complete run at a smaller budget. Neither the gap nor
    # the saturation test can tell the difference, so the count is surfaced rather than hidden.
    # Compare within a cohort, not within a task. Cohorts were run at different budgets on
    # purpose - a budget-3 run is not a truncated budget-12 run - so comparing across them
    # counts deliberate design as breakage.
    lengths: dict[tuple[str, str], list[int]] = defaultdict(list)
    for key, arms in found.items():
        for mode_curves in arms.values():
            for curve in mode_curves.values():
                lengths[key].append(len(curve))
    truncated = sum(
        sum(1 for n in seen if n < max(seen)) for seen in lengths.values() if seen
    )
    total_runs = sum(len(seen) for seen in lengths.values())

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
    print("models present:", ", ".join(models))
    print("distinct tasks: %d" % len(tasks))
    if agreed or contested:
        print("task versions measured by more than one model: %d agree, %d disagree"
              % (len(agreed), len(contested)))
        if split_by_version:
            print("  %d task(s) carry more than one version in this tree, so some pairs of "
                  "models\n  have no common version to be compared on: %s"
                  % (len(split_by_version),
                     ", ".join(short(t) for t in split_by_version[:6])
                     + (" ..." if len(split_by_version) > 6 else "")))
        for task, verdicts in sorted(contested.items()):
            print("  %-30s %s" % (
                short(task), "; ".join("%s=%s" % kv for kv in sorted(verdicts.items()))))
    print("runs that ended short of their own cohort: %d of %d"
          % (truncated, total_runs))
    # One row per (task, model), not per task: the same task measured by two model families is
    # two measurements.
    assert len(rows) == len({(r["task"], r["model"], r["task_version"]) for r in rows}), \
        "one row per task, model and task version"
    print("distinct tasks with paired evidence for the sufficient condition: %d of %d"
          % (len(tasks_paired), len(tasks)))
    print("distinct tasks shown to measure iteration: %d" % len(tasks_measuring))
    for name in sorted(tasks_measuring):
        print("   ", name)
    # Reported next to the qualifying list rather than folded into it. A task admitted on a
    # saturation that a trusted-size subset of its own seeds would reverse has not been shown to
    # satisfy the necessary condition; it has been shown that the seeds run so far do not settle
    # the question.
    fragile_rows = [r for r in rows
                    if (r.get("saturation") or {}).get("seed_fragile")
                    and r["verdict"].startswith("measures_iteration")]
    print("of those, resting on a saturation that a %d-seed subset would reverse: %d"
          % (MIN_SEEDS_FOR_CONFIDENT_SATURATION, len(fragile_rows)))
    for r in sorted(fragile_rows, key=lambda r: r["task"]):
        sat = r["saturation"]
        print("    %-30s %-16s %d seeds, median second-half gain %.4f (threshold %.2f)"
              % (short(r["task"]), r["model"][:16], sat["seeds"],
                 sat["median_second_half_gain"], MATERIAL_GAIN))

    # The only pool that can add qualifying tasks: real headroom, never paired.
    # One entry per task, not per (task, cohort): saturation now pools across cohorts, so a task
    # present in four cohorts would otherwise be listed four identical times. A task that has
    # been paired anywhere is not a candidate, however its other cohorts happen to be labelled.
    paired_tasks = {row["task"] for row in rows if row["gap_by_budget"]}
    best_by_task: dict[str, tuple] = {}
    for row in rows:
        if row["verdict"] != "exhausted_unpaired":
            continue
        if row["task"] in paired_tasks:
            continue
        sat = row["saturation"]
        best_by_task[row["task"]] = (
            sat["mean_final"], sat["median_second_half_gain"], sat["seeds"],
            row["task"], row["verdict"],
        )
    # Lowest settling point first. A control that has run out at 0.998 leaves a searcher almost
    # nothing to demonstrate, however exhausted it is; one that runs out at 0.12 leaves the whole
    # range. Ranking by remaining room is the only ordering that makes this a useful queue.
    candidates = sorted(best_by_task.values())
    print()
    print("worth pairing next (best-of-N exhausted, feedback arm never run):")
    for final, gain, seeds, name, _state in candidates:
        print("    %-34s control settles at %.4f  median gain %+.4f  seeds=%d"
              % (name.split("/")[-1], final, gain, seeds))
    if not candidates:
        print("    none: every task with an exhausted control has already been paired")

    Path(args.output).write_text(json.dumps({
        "schema_version": 2,
        "note": "condition 1 (open-loop non-saturation) is necessary; condition 2 (a feedback "
                "gap that does not close with budget) is what makes a task measure iteration",
        "budgets": list(BUDGETS),
        "row_count": len(rows),
        "note_rows": "one row per task; paired gaps listed per cohort inside each row",
        "distinct_task_count": len(tasks),
        "models": models,
        "tasks_with_more_than_one_version": split_by_version,
        "qualifying_but_seed_fragile": [
            {"task": r["task"], "model": r["model"], "task_version": r["task_version"]}
            for r in rows if (r.get("saturation") or {}).get("seed_fragile")
            and r["verdict"].startswith("measures_iteration")],
        "cross_model_agreement": {t: v for t, v in sorted(agreed.items())},
        "cross_model_disagreement": {t: v for t, v in sorted(contested.items())},
        "short_run_count": truncated,
        "total_run_count": total_runs,
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
