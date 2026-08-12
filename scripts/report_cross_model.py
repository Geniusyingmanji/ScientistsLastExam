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


def read_runs(runs_root: Path) -> list[dict]:
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
            "model": str((document.get("llm_condition") or {}).get("model") or "unrecorded"),
            "mode": str(document.get("feedback_mode")),
            "seed": document.get("seed"),
            "best": max(scores) if scores else 0.0,
            "valid": len(scores),
            "proposals": len(proposals),
            "input_tokens": int(usage.get("input_tokens", 0) or 0),
            "output_tokens": int(usage.get("output_tokens", 0) or 0),
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

    # Open-loop score per (model, task), averaged over seeds. The open-loop arm is the right axis
    # for a ranking: it is what the task yields to independent sampling, independent of whether
    # the searcher's feedback loop happens to help.
    scores: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    tokens: dict[str, list[tuple[int, int]]] = defaultdict(list)
    validity: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for run in runs:
        tokens[run["model"]].append((run["input_tokens"], run["output_tokens"]))
        if run["mode"] in OPEN_LOOP_MODES:
            scores[run["model"]][run["task"]].append(run["best"])
        validity[run["model"]][run["mode"]].append(
            run["valid"] / run["proposals"] if run["proposals"] else 0.0)

    print("=== open-loop score per task, by model ===")
    shared = sorted(set.intersection(*[set(scores[m]) for m in models]) if len(models) > 1
                    else set())
    if not shared:
        print("no task has been run by more than one model yet")
    else:
        header = "%-30s" % "task" + "".join("%16s" % m[:16] for m in models)
        print(header)
        print("-" * len(header))
        columns: dict[str, list[float]] = {m: [] for m in models}
        for task in shared:
            cells = []
            for model in models:
                value = st.mean(scores[model][task])
                columns[model].append(value)
                cells.append("%16.4f" % value)
            print("%-30s%s" % (task.split("/")[-1][:30], "".join(cells)))
        print()
        for i, first in enumerate(models):
            for second in models[i + 1:]:
                rho = spearman(columns[first], columns[second])
                print("rank correlation %s vs %s over %d shared tasks: %s"
                      % (first, second, len(shared),
                         "not computable (fewer than 3 tasks)" if rho is None else "%.3f" % rho))

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
    if args.admission and Path(args.admission).is_file():
        report = json.loads(Path(args.admission).read_text(encoding="utf-8"))
        for row in report.get("rows", []):
            verdicts.setdefault(row["task"], {})[row.get("model", "unrecorded")] = row["verdict"]
        contested = {t: v for t, v in verdicts.items()
                     if len(v) > 1 and len(set(v.values())) > 1}
        agreed = {t: v for t, v in verdicts.items()
                  if len(v) > 1 and len(set(v.values())) == 1}
        print()
        print("=== verdict agreement ===")
        print("  tasks with a verdict from more than one model: %d" % (len(agreed) + len(contested)))
        print("  agree: %d   disagree: %d" % (len(agreed), len(contested)))
        for task, per_model in sorted(contested.items()):
            print("    %-30s %s" % (task.split("/")[-1][:30],
                                    "; ".join("%s=%s" % kv for kv in sorted(per_model.items()))))

    Path(args.output).write_text(json.dumps({
        "schema_version": 1,
        "note": "score ranking and admission verdicts are reported separately; they can disagree",
        "models": models,
        "shared_tasks": shared if len(models) > 1 else [],
        "open_loop_scores": {m: {t: st.mean(v) for t, v in scores[m].items()} for m in scores},
        "cost": cost_rows,
        "verdicts": verdicts,
    }, indent=2), encoding="utf-8")
    print()
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
