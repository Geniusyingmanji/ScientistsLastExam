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

# Published list prices per million tokens, used only to report what a comparison cost. Absent
# for a model means the cost column is blank rather than guessed.
PRICES = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

OPEN_LOOP_MODES = ("selection_blind", "blind")


def known_conditions() -> dict[str, str]:
    """Condition hash to model, for manifests predating the readable field. See the YAML."""
    import yaml

    path = ROOT / "frontier_science" / "llm_conditions.yaml"
    if not path.is_file():
        return {}
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(h): str(entry.get("model") or "unrecorded")
            for h, entry in (document.get("conditions") or {}).items()}


def read_runs(runs_root: Path) -> list[dict]:
    conditions = known_conditions()
    out = []
    for trajectory in runs_root.glob("*/*/trajectory.jsonl"):
        workdir = trajectory.parent
        manifest = workdir / "run_manifest.json"
        if not manifest.is_file():
            continue
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = []
        for line in trajectory.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        proposals = [r for r in rows if int(r.get("step", 0) or 0) > 0]
        if not proposals:
            continue
        scores = [float(r.get("score") or 0.0) for r in proposals if r.get("valid")]
        usage = {}
        for row in reversed(rows):
            if row.get("llm"):
                usage = row["llm"]
                break
        out.append({
            "task": str(document.get("task_id")),
            "model": (str((document.get("llm_condition") or {}).get("model") or "")
                      or conditions.get(str(document.get("llm_condition_sha256") or ""),
                                        "unrecorded")),
            "mode": str(document.get("feedback_mode")),
            "seed": document.get("seed"),
            "best": max(scores) if scores else 0.0,
            "valid": len(scores),
            "proposals": len(proposals),
            "input_tokens": int(usage.get("input_tokens", 0) or 0),
            "output_tokens": int(usage.get("output_tokens", 0) or 0),
            "contract": str(document.get("task_package_sha256") or "")[:12],
        })
    return out


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

    runs = read_runs(Path(args.runs))
    models = sorted({r["model"] for r in runs if r["model"] != "unrecorded"})
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
    # Separately over every arm, because a verdict is computed from both arms while the score
    # ranking uses only the open-loop one. Keying the verdict check off the open-loop map dropped
    # every task a model had only run under `normal`.
    all_arm_contracts: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for run in runs:
        if run["model"] == "unrecorded":
            continue
        all_arm_contracts[run["task"]][run["model"]].add(run["contract"])
        if run["mode"] in OPEN_LOOP_MODES:
            contracts[run["task"]][run["model"]].add(run["contract"])

    # Open-loop score per (model, task, contract), averaged over seeds. The open-loop arm is the
    # right axis for a ranking: it is what the task yields to independent sampling, independent of
    # whether the searcher's feedback loop happens to help.
    scores: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    tokens: dict[str, list[tuple[int, int]]] = defaultdict(list)
    validity: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for run in runs:
        tokens[run["model"]].append((run["input_tokens"], run["output_tokens"]))
        if run["model"] == "unrecorded":
            continue
        if run["mode"] in OPEN_LOOP_MODES:
            scores[run["model"]][run["task"]].append(run["best"])
        validity[run["model"]][run["mode"]].append(
            run["valid"] / run["proposals"] if run["proposals"] else 0.0)

    print("=== open-loop score, compared pairwise on shared task versions ===")
    # Pairwise rather than across all models at once. Requiring every model to share a contract
    # excluded every task here, because one model's runs predate a round of task edits - and that
    # would have thrown away the one comparison that is valid.
    def shared_tasks(first: str, second: str) -> list[str]:
        out = []
        for task in sorted(set(scores[first]) & set(scores[second])):
            a_contracts = contracts[task][first]
            b_contracts = contracts[task][second]
            if len(a_contracts) == 1 and a_contracts == b_contracts:
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
        total_in = sum(a for a, _ in tokens[model])
        total_out = sum(b for _, b in tokens[model])
        price = PRICES.get(model)
        dollars = (total_in / 1e6 * price[0] + total_out / 1e6 * price[1]) if price else None
        cost_rows.append({"model": model, "runs": len(tokens[model]),
                          "input_tokens": total_in, "output_tokens": total_out,
                          "estimated_usd": dollars})
        print("  %-20s %3d runs  in=%9d  out=%9d  %s"
              % (model[:20], len(tokens[model]), total_in, total_out,
                 "$%.2f" % dollars if dollars is not None else "no published price"))

    verdicts: dict[str, dict[str, str]] = {}
    stated_versions: dict[str, dict[str, str]] = {}
    comparable: dict[str, dict[str, str]] = {}
    if args.admission and Path(args.admission).is_file():
        report = json.loads(Path(args.admission).read_text(encoding="utf-8"))
        for row in report.get("rows", []):
            model = row.get("model", "unrecorded")
            # Skip runs recorded before the manifest carried a model. "We do not know which model"
            # cannot agree or disagree with anything.
            if model == "unrecorded":
                continue
            verdicts.setdefault(row["task"], {})[model] = row["verdict"]
            # The admission report now states which version of the task a verdict was reached
            # against. Prefer it over the version inferred from the run tree: it is the same
            # fact, recorded by the report that formed the verdict rather than reconstructed.
            stated = row.get("task_version")
            if stated:
                stated_versions.setdefault(row["task"], {})[model] = str(stated)
        # Same contract rule as the score comparison. A verdict is about a task, so two verdicts
        # reached against different versions of that task disagree about nothing.
        comparable, dropped = {}, 0
        for task, per_model in verdicts.items():
            stated = stated_versions.get(task, {})

            def version_of(model_name: str) -> str | None:
                if model_name in stated:
                    return stated[model_name]
                seen = all_arm_contracts[task][model_name]
                return next(iter(seen)) if len(seen) == 1 else None

            kept = {m: v for m, v in per_model.items() if version_of(m) is not None}
            versions = {version_of(m) for m in kept}
            if len(kept) > 1 and len(versions) == 1:
                comparable[task] = kept
            elif len(per_model) > 1:
                dropped += 1
        contested = {t: v for t, v in comparable.items() if len(set(v.values())) > 1}
        agreed = {t: v for t, v in comparable.items() if len(set(v.values())) == 1}
        print()
        print("=== verdict agreement, on shared task versions ===")
        print("  tasks with a verdict from more than one model, same version: %d"
              % (len(agreed) + len(contested)))
        print("  agree: %d   disagree: %d" % (len(agreed), len(contested)))
        if dropped:
            print("  %d further multi-model tasks excluded: the models ran different versions"
                  % dropped)
        for task, per_model in sorted(contested.items()):
            print("    %-30s %s" % (task.split("/")[-1][:30],
                                    "; ".join("%s=%s" % kv for kv in sorted(per_model.items()))))

    Path(args.output).write_text(json.dumps({
        "schema_version": 1,
        "note": "score ranking and admission verdicts are reported separately; they can disagree",
        "models": models,
        "shared_tasks": shared,
        "pairwise": comparisons,
        "open_loop_scores": {m: {t: st.mean(v) for t, v in scores[m].items()} for m in scores},
        "cost": cost_rows,
        "verdicts": verdicts,
        "verdicts_same_version": comparable,
    }, indent=2), encoding="utf-8")
    print()
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
