#!/usr/bin/env python3
"""Compare what two models say about the same tasks, on score and on verdict.

A benchmark that has only ever been run by one model cannot claim to discriminate. It also cannot
know whether its verdicts are about the tasks or about that model: the crossover budget is a
property of the task and the searcher together, so "this task measures iteration" is, strictly, a
statement about one searcher until a second one repeats it.

This reports three things and keeps them apart, because they can disagree:

    score agreement    do the models rank the tasks the same way? Spearman's rho over the
                       open-loop scores, which is the axis a leaderboard would use.
    verdict agreement  do they reach the same admission verdict per task? A rank correlation can
                       be high while the verdicts differ, because a verdict depends on the shape
                       of the gap rather than on the level of the score.
    cost               tokens and dollars per run, which is what makes a comparison affordable or
                       not, and which no other report in this repository tracks.

Nothing here is averaged into a single "agreement score". Two models agreeing on the ranking while
disagreeing on which tasks measure iteration is the interesting case, and one number would erase
it.

Usage:
    python scripts/report_cross_model.py --runs runs --output /tmp/cross_model.json
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.reporting_runtime import report_runtime_binding  # noqa: E402
from sle.task_versions import version_class  # noqa: E402
from scripts.reporting_trajectory import read_events, read_incumbents, trajectory_selection_evidence

# Published list prices per million tokens, used only to report what a comparison cost. Absent
# for a model means the cost column is blank rather than guessed.
PRICES = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

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


def known_conditions() -> dict[str, str]:
    """Condition hash to model, for manifests predating the readable field. See the YAML."""
    import yaml

    path = ROOT / "sle" / "llm_conditions.yaml"
    if not path.is_file():
        return {}
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(h): str(entry.get("model") or "unrecorded")
            for h, entry in (document.get("conditions") or {}).items()}


def read_runs(runs_root: Path) -> list[dict]:
    """Read each run with its recorded selection and comparison conditions."""
    conditions = known_conditions()
    out = []
    for manifest in sorted(runs_root.rglob("run_manifest.json")):
        workdir = manifest.parent
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            out.append({"status": "invalid_manifest", "run_directory": str(workdir),
                        "error": "%s: %s" % (manifest, exc)})
            continue
        run = {
            "task": str(document.get("task_id") or "unrecorded"),
            "model": (str((document.get("llm_condition") or {}).get("model") or "")
                      or conditions.get(str(document.get("llm_condition_sha256") or ""), "unrecorded")),
            "condition": document.get("llm_condition_sha256") or "unrecorded",
            "runtime": document.get("runtime_source_sha256") or "unrecorded",
            "algorithm": document.get("algorithm") or "unrecorded",
            "budget": document.get("budget"),
            "mode": str(document.get("feedback_mode")), "seed": document.get("seed"),
            "run_directory": str(workdir.resolve()), "endpoint": "incumbent",
            "contract": version_class(str(document.get("task_id")),
                                      str(document.get("task_package_sha256") or "unknown"))[:14],
            "input_tokens": 0, "output_tokens": 0,
        }
        run.update(report_runtime_binding(workdir, document))
        trajectory = workdir / "trajectory.jsonl"
        try:
            rows = read_events(trajectory)
            selected = read_incumbents(trajectory)
            if not selected:
                raise ValueError("empty trajectory")
            proposals = rows[1:]
            valid = sum(bool(row.get("valid")) for row in proposals)
            summary_path = workdir / "summary.json"
            summary = json.loads(summary_path.read_text()) if summary_path.is_file() else {}
            # ensure_run_manifest does not record the proposal budget. The runner
            # records it in summary.json; trajectory length is the observed count,
            # never a substitute for the planned horizon.
            recorded_budget = (run["proposal_budget"] if run["trusted_evidence"]
                               else summary.get("budget"))
            if run["budget"] is not None and recorded_budget is not None and run["budget"] != recorded_budget:
                raise ValueError("manifest and summary proposal budgets disagree")
            if run["budget"] is None:
                run["budget"] = recorded_budget
                run["budget_source"] = "summary.json" if recorded_budget is not None else "unrecorded"
            else:
                run["budget_source"] = "run_manifest.json"
            if run["budget"] is not None and (type(run["budget"]) is not int or run["budget"] < 0):
                raise ValueError("recorded proposal budget must be a nonnegative integer")
            for field, expected in (("task_id", run["task"]), ("algorithm", run["algorithm"]),
                                    ("seed", run["seed"]), ("feedback_mode", run["mode"])):
                if field in summary and summary[field] != expected:
                    raise ValueError("summary identity differs from manifest: " + field)
            def usage_total(field):
                values = [(event.get("llm") or {}).get(field) for event in proposals]
                return sum(values) if all(type(v) is int and v >= 0 for v in values) else None
            status = "protocol_incomplete" if summary.get("protocol_incomplete") or not valid else "ok"
            if status == "ok" and run["budget"] is not None and len(proposals) != run["budget"]:
                status = "incomplete_proposal_horizon"
            run.update(
                status=status,
                best=float(selected[-1]["score"]), valid=valid, proposals=len(proposals),
                observed_budget=len(proposals),
                selection_evidence=trajectory_selection_evidence(rows),
                input_tokens=usage_total("input_tokens"),
                output_tokens=usage_total("output_tokens"),
            )
        except (OSError, ValueError) as exc:
            run.update(status="invalid_trajectory", error="%s: %s" % (trajectory, exc))
        out.append(run)
    return out


def comparison_scope(run: dict) -> tuple:
    return (run["contract"], run["runtime"], run.get("trusted_evaluator_runtime_sha256"), run["algorithm"],
            run["budget"], run.get("observed_budget"), run["endpoint"])


def attributable_score_run(run: dict) -> bool:
    return (run.get("status") == "ok"
            and (run.get("verification_status") == "legacy_format"
                 or run.get("trusted_evidence") is True)
            and all(run.get(field) not in (None, "", "unknown", "unrecorded")
                    for field in ("model", "condition", "runtime", "algorithm", "contract", "budget"))
            and run.get("selection_evidence", {}).get("status") == "recorded")


def spearman(a: list[float], b: list[float]) -> float | None:
    """Rank correlation, with ties handled by average rank."""
    n = len(a)
    if n < 3:
        return None

    def ranks(values):
        order = sorted(range(n), key=lambda i: values[i])
        out = [0.0] * n
        index = 0
        while index < n:
            stop = index
            while stop + 1 < n and values[order[stop + 1]] == values[order[index]]:
                stop += 1
            average = (index + stop) / 2.0 + 1.0
            for position in range(index, stop + 1):
                out[order[position]] = average
            index = stop + 1
        return out

    ra, rb = ranks(a), ranks(b)
    mean_a, mean_b = st.mean(ra), st.mean(rb)
    num = sum((x - mean_a) * (y - mean_b) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - mean_a) ** 2 for x in ra)
                    * sum((y - mean_b) ** 2 for y in rb))
    return None if den == 0 else num / den


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--admission", default=None,
                    help="admission_criterion.json, to compare verdicts as well as scores")
    args = ap.parse_args(argv)

    run_records = read_runs(Path(args.runs))
    runs = [r for r in run_records if attributable_score_run(r)]
    models = sorted({r["model"] for r in run_records if r.get("model", "unrecorded") != "unrecorded"})
    if len(models) < 2:
        print("only %d model(s) with a recorded condition: %s"
              % (len(models), ", ".join(models) or "none"))
        print("a cross-model comparison needs two; run the benchmark under a second model first.")

    # Two models can only be compared on a task if they ran the same version of it. Twenty of the
    # 54 tasks in this repository carry more than one `task_package_sha256` across cohorts,
    # because tasks were edited between runs, and comparing across that difference reports a task
    # change as a model difference - on one task the gap looked like 18x. The hash was recorded
    # all along; nothing was checking it at comparison time.
    contracts: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    scopes = defaultdict(lambda: defaultdict(set))
    model_conditions = defaultdict(lambda: defaultdict(set))
    for run in runs:
        if run["model"] == "unrecorded":
            continue
        if run["mode"] in OPEN_LOOP_MODES:
            contracts[run["task"]][run["model"]].add(run["contract"])
            scopes[run["task"]][run["model"]].add(comparison_scope(run))
            model_conditions[run["task"]][run["model"]].add(run["condition"])

    # Open-loop score per (model, task, contract), averaged over seeds. The open-loop arm is the
    # right axis for a ranking: it is what the task yields to independent sampling, independent of
    # whether the searcher's feedback loop happens to help.
    scores: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    tokens: dict[str, list[tuple[int, int]]] = defaultdict(list)
    validity: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for run in run_records:
        if "model" in run:
            tokens[run["model"]].append((run["input_tokens"], run["output_tokens"]))
    for run in runs:
        if run["model"] == "unrecorded":
            continue
        if run["mode"] in OPEN_LOOP_MODES:
            scores[run["model"]][run["task"]].append(run["best"])
        validity[run["model"]][run["mode"]].append(
            run["valid"] / run["proposals"] if run["proposals"] else 0.0)

    score_groups = defaultdict(list)
    for run in runs:
        if run["mode"] in OPEN_LOOP_MODES:
            score_groups[(run["task"], run["model"], run["condition"], comparison_scope(run))].append(run)
    score_rows = [
        {"task": task, "model": model, "llm_condition_sha256": condition,
         "task_version": scope[0], "runtime_source_sha256": scope[1], "algorithm": scope[2],
         "budget": scope[3], "observed_budget": scope[4], "endpoint": scope[5],
         "n": len(group), "mean": st.mean(run["best"] for run in group),
         "run_directories": [run["run_directory"] for run in group]}
        for (task, model, condition, scope), group in score_groups.items()
    ]

    print("=== open-loop score, compared pairwise on shared task versions ===")
    # Pairwise rather than across all models at once. Requiring every model to share a contract
    # excluded every task here, because one model's runs predate a round of task edits - and that
    # would have thrown away the one comparison that is valid.
    def shared_tasks(first: str, second: str) -> list[str]:
        out = []
        for task in sorted(set(scores[first]) & set(scores[second])):
            a_contracts = contracts[task][first]
            b_contracts = contracts[task][second]
            a_scopes, b_scopes = scopes[task][first], scopes[task][second]
            if (len(a_contracts) == 1 and a_contracts == b_contracts
                    and len(a_scopes) == 1 and a_scopes == b_scopes
                    and len(model_conditions[task][first]) == 1
                    and len(model_conditions[task][second]) == 1):
                out.append(task)
        return out

    comparisons = []
    for i, first in enumerate(models):
        for second in models[i + 1:]:
            tasks_here = shared_tasks(first, second)
            skipped = sorted((set(scores[first]) & set(scores[second])) - set(tasks_here))
            print()
            print("%s vs %s" % (first, second))
            if not tasks_here:
                print("  no task where both ran the same version"
                      + ("; %d excluded for differing versions" % len(skipped) if skipped else ""))
                comparisons.append({"models": [first, second], "tasks": [], "rho": None,
                                    "excluded_for_contract_mismatch": skipped})
                continue
            xs, ys = [], []
            print("  %-30s %14s %14s" % ("task", first[:14], second[:14]))
            for task in tasks_here:
                x, y = st.mean(scores[first][task]), st.mean(scores[second][task])
                xs.append(x)
                ys.append(y)
                print("  %-30s %14.4f %14.4f" % (task.split("/")[-1][:30], x, y))
            rho = spearman(xs, ys)
            print("  rank correlation over %d shared-version tasks: %s"
                  % (len(tasks_here),
                     "not computable (fewer than 3)" if rho is None else "%.3f" % rho))
            if skipped:
                print("  %d further shared tasks excluded because the two ran different "
                      "versions" % len(skipped))
            comparisons.append({"models": [first, second], "tasks": tasks_here, "rho": rho,
                                "excluded_for_contract_mismatch": skipped})
    shared = sorted({t for c in comparisons for t in c["tasks"]})

    print()
    print("=== proposal validity by model and arm ===")
    for model in sorted(validity):
        parts = ["%s %.2f" % (mode, st.mean(rates))
                 for mode, rates in sorted(validity[model].items())]
        print("  %-20s %s" % (model[:20], "  ".join(parts)))

    print()
    print("=== cost ===")
    cost_rows = []
    for model in sorted(tokens):
        total_in = sum(a for a, _ in tokens[model]) if all(a is not None for a, _ in tokens[model]) else None
        total_out = sum(b for _, b in tokens[model]) if all(b is not None for _, b in tokens[model]) else None
        price = PRICES.get(model)
        dollars = (total_in / 1e6 * price[0] + total_out / 1e6 * price[1]) if price and total_in is not None and total_out is not None else None
        cost_rows.append({"model": model, "runs": len(tokens[model]),
                          "input_tokens": total_in, "output_tokens": total_out,
                          "estimated_usd": dollars})
        print("  %-20s %3d runs  in=%9s  out=%9s  %s"
              % (model[:20], len(tokens[model]), total_in, total_out,
                 "$%.2f" % dollars if dollars is not None else "no published price"))

    verdicts, comparable = {}, {}
    verdict_rows, ambiguous_legacy_verdicts = [], []
    if args.admission and Path(args.admission).is_file():
        report = json.loads(Path(args.admission).read_text(encoding="utf-8"))
        grouped_legacy = defaultdict(list)
        by_scope = defaultdict(dict)
        for source in report.get("rows", []):
            model = source.get("model", "unrecorded")
            if model == "unrecorded":
                continue
            row = dict(source)
            task = row["task"]
            grouped_legacy[(task, model)].append(row)
            candidates = [run for run in runs if run["task"] == task and run["model"] == model
                          and (not row.get("task_version") or run["contract"] == row["task_version"])]
            for field, run_field in (("task_version", "contract"), ("runtime_source_sha256", "runtime"),
                                     ("algorithm", "algorithm"), ("budget", "budget"),
                                     ("llm_condition_sha256", "condition")):
                if row.get(field) is None:
                    values = {run[run_field] for run in candidates}
                    row[field] = next(iter(values)) if len(values) == 1 else None
            row["endpoint"] = row.get("endpoint") or "incumbent"
            fields = ("task_version", "runtime_source_sha256", "algorithm", "budget",
                      "llm_condition_sha256")
            row["comparison_status"] = (
                "comparable" if all(row.get(field) not in (None, "", "unknown", "unrecorded")
                                    for field in fields) else "unresolved_identity")
            verdict_rows.append(row)
            if row["comparison_status"] != "comparable":
                continue
            scope = (task, row["task_version"], row["runtime_source_sha256"],
                     row["algorithm"], row["budget"], row["endpoint"])
            model_condition = model + "@" + row["llm_condition_sha256"]
            if model_condition in by_scope[scope]:
                raise ValueError("duplicate admission verdict identity: %s %s" % (scope, model_condition))
            by_scope[scope][model_condition] = row["verdict"]
        # Preserve the old convenience view only when no row would be discarded.
        for (task, model), entries in sorted(grouped_legacy.items()):
            if len(entries) == 1:
                verdicts.setdefault(task, {})[model] = entries[0]["verdict"]
            else:
                ambiguous_legacy_verdicts.append({"task": task, "model": model, "row_count": len(entries)})
        comparable = {
            "%s @%s runtime=%s algorithm=%s budget=%s endpoint=%s" % scope: values
            for scope, values in by_scope.items()
            if len({name.rsplit("@", 1)[0] for name in values}) > 1
        }
        contested = {k: v for k, v in comparable.items() if len(set(v.values())) > 1}
        agreed = {k: v for k, v in comparable.items() if len(set(v.values())) == 1}
        versions = defaultdict(set)
        for row in verdict_rows:
            versions[row["task"]].add(row.get("task_version"))
        split = [task for task, values in versions.items() if len(values) > 1]
        print()
        print("=== verdict agreement, within task version, runtime, algorithm and budget ===")
        print("  agree: %d   disagree: %d" % (len(agreed), len(contested)))
        if split:
            print("  tasks carrying more than one version:", ", ".join(sorted(split)))
        for task, per_model in sorted(contested.items()):
            print("  %s: %s" % (task, per_model))

    Path(args.output).write_text(json.dumps({
        "schema_version": 2,
        "endpoint": "incumbent",
        "run_records": run_records,
        "excluded_run_count": len(run_records) - len(runs),
        "note": "score ranking and admission verdicts are reported separately; they can disagree",
        "models": models,
        "shared_tasks": shared,
        "pairwise": comparisons,
        "score_rows": score_rows,
        # Legacy convenience view has a value only where a task/model has one scope.
        "open_loop_scores": {m: {t: st.mean(v) for t, v in scores[m].items()
                                  if len(scopes[t][m]) == 1 and len(model_conditions[t][m]) == 1}
                             for m in scores},
        "cost": cost_rows,
        "verdicts": verdicts,
        "verdict_rows": verdict_rows,
        "ambiguous_legacy_verdicts": ambiguous_legacy_verdicts,
        "verdicts_same_version": comparable,
    }, indent=2), encoding="utf-8")
    print()
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
