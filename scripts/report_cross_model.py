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

from sle.task_versions import version_class  # noqa: E402
from sle.run_verification import verify_run  # noqa: E402

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
    conditions = known_conditions()
    out = []
    # Recursive, because two drivers write into this tree at different depths: `run_cohort.sh`
    # puts a run one level down and `batch_evolve.py` nests it by task, algorithm, mode and seed.
    # A fixed-depth glob finds the first and silently finds nothing in the second, which reads as
    # a model that was never run rather than as a layout this did not expect. Run identity comes
    # from the manifest, so depth carries no meaning here anyway.
    for trajectory in sorted(runs_root.rglob("trajectory.jsonl")):
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
        runtime_source = str(document.get("runtime_source_sha256") or "unrecorded")
        trusted_runtime = str(
            (document.get("trusted_evaluator_runtime") or {}).get(
                "fingerprint_sha256"
            ) or "unrecorded"
        )
        algorithm = str(document.get("algorithm") or "unrecorded")
        condition = str(document.get("llm_condition_sha256") or "unrecorded")
        model = (
            str((document.get("llm_condition") or {}).get("model") or "")
            or conditions.get(condition, "unrecorded")
        )
        verified_budget = None
        trusted_evidence = False
        try:
            verification = verify_run(workdir)
            verified_budget = verification.get("budget")
            trusted_evidence = bool(
                verification.get("verified") is True
                and verification.get("trusted_evaluator_runtime_sha256")
                == trusted_runtime
                and str(document.get("task_id") or "")
                and document.get("task_package_sha256")
                and model != "unrecorded"
                and condition != "unrecorded"
                and algorithm != "unrecorded"
                and runtime_source != "unrecorded"
                and trusted_runtime != "unrecorded"
                and str(document.get("feedback_mode") or "")
                and isinstance(document.get("seed"), int)
                and isinstance(verified_budget, int)
                and not isinstance(verified_budget, bool)
                and verified_budget >= 0
            )
        except (OSError, ValueError):
            pass
        out.append({
            "task": str(document.get("task_id")),
            "model": model,
            "mode": str(document.get("feedback_mode")),
            "seed": document.get("seed"),
            "best": max(scores) if scores else 0.0,
            "valid": len(scores),
            "proposals": len(proposals),
            "input_tokens": int(usage.get("input_tokens", 0) or 0),
            "output_tokens": int(usage.get("output_tokens", 0) or 0),
            "llm_condition_sha256": condition,
            "algorithm": algorithm,
            "runtime_source_sha256": runtime_source,
            "trusted_evaluator_runtime_sha256": trusted_runtime,
            "trusted_evidence": trusted_evidence,
            "proposal_budget": verified_budget,
            # The equivalence class, not the raw hash: sixteen tasks record two hashes that are
            # the same task, and comparing on the hash discarded that evidence.
            "contract": version_class(str(document.get("task_id")),
                                      str(document.get("task_package_sha256") or ""))[:14],
        })
    return out


def condition_identity(run: dict) -> tuple[str, str, str, str, str]:
    """A model condition before task, mode, seed and budget are added."""
    return (
        run["model"], run["llm_condition_sha256"], run["algorithm"],
        run["runtime_source_sha256"],
        run["trusted_evaluator_runtime_sha256"],
    )


def condition_document(identity: tuple[str, str, str, str, str]) -> dict:
    return dict(zip((
        "model", "llm_condition_sha256", "algorithm", "runtime_source_sha256",
        "trusted_evaluator_runtime_sha256",
    ), identity))


def condition_label(identity: tuple[str, str, str, str, str]) -> str:
    return "%s@%s/%s/%s/%s" % (
        identity[0], identity[1][:12], identity[2], identity[3][:12],
        identity[4][:12],
    )


def arm_document(arm: tuple[str, str, str, str, str, str, int]) -> dict:
    return {
        **condition_document(arm[:5]),
        "feedback_mode": arm[5],
        "proposal_budget": arm[6],
    }


def arm_label(arm: tuple[str, str, str, str, str, str, int]) -> str:
    return "%s/%s/b%d" % (condition_label(arm[:5]), arm[5], arm[6])


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
    trusted_runs = [
        run for run in runs
        if run["trusted_evidence"] and run["model"] != "unrecorded"
    ]
    models = sorted({r["model"] for r in trusted_runs})
    if len(models) < 2:
        print("only %d model(s) with a recorded condition: %s"
              % (len(models), ", ".join(models) or "none"))
        print("a cross-model comparison needs two; run the benchmark under a second model first.")

    # Two models can only be compared on a task if they ran the same version of it. Twenty of the
    # 54 tasks in this repository carry more than one `task_package_sha256` across cohorts,
    # because tasks were edited between runs, and comparing across that difference reports a task
    # change as a model difference - on one task the gap looked like 18x. The hash was recorded
    # all along; nothing was checking it at comparison time.
    contracts: dict[str, dict[tuple[str, ...], set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for run in trusted_runs:
        if run["mode"] in OPEN_LOOP_MODES:
            arm = condition_identity(run) + (
                run["mode"], run["proposal_budget"],
            )
            contracts[run["task"]][arm].add(run["contract"])

    # Open-loop score per (model, task, contract), averaged over seeds. The open-loop arm is the
    # right axis for a ranking: it is what the task yields to independent sampling, independent of
    # whether the searcher's feedback loop happens to help.
    scores: dict[tuple[str, ...], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    tokens: dict[tuple[str, ...], list[tuple[int, int]]] = defaultdict(list)
    validity: dict[
        tuple[tuple[str, ...], str, str, str, int], list[float]
    ] = defaultdict(list)
    for run in trusted_runs:
        identity = condition_identity(run)
        tokens[identity].append((run["input_tokens"], run["output_tokens"]))
        if run["mode"] in OPEN_LOOP_MODES:
            arm = identity + (run["mode"], run["proposal_budget"])
            scores[arm][run["task"]].append(run["best"])
        validity[(
            identity, run["task"], run["contract"], run["mode"],
            run["proposal_budget"],
        )].append(
            run["valid"] / run["proposals"] if run["proposals"] else 0.0)

    print("=== open-loop score, compared pairwise on shared task versions ===")
    # Pairwise rather than across all models at once. Requiring every model to share a contract
    # excluded every task here, because one model's runs predate a round of task edits - and that
    # would have thrown away the one comparison that is valid.
    def comparable_conditions(first: tuple[str, ...], second: tuple[str, ...]) -> bool:
        return bool(first[0] != second[0] and first[2:] == second[2:])

    def shared_tasks(first: tuple[str, ...], second: tuple[str, ...]) -> list[str]:
        out = []
        for task in sorted(set(scores[first]) & set(scores[second])):
            a_contracts = contracts[task][first]
            b_contracts = contracts[task][second]
            if len(a_contracts) == 1 and a_contracts == b_contracts:
                out.append(task)
        return out

    comparisons = []
    identities = sorted(scores)
    incomparable_condition_pairs = []
    for i, first in enumerate(identities):
        for second in identities[i + 1:]:
            if not comparable_conditions(first, second):
                if first[0] != second[0] and set(scores[first]) & set(scores[second]):
                    incomparable_condition_pairs.append({
                        "conditions": [
                            arm_document(first), arm_document(second)
                        ],
                        "shared_task_names": sorted(
                            set(scores[first]) & set(scores[second])
                        ),
                        "reason": (
                            "algorithm, runtime, feedback mode, or proposal budget differs"
                        ),
                    })
                continue
            tasks_here = shared_tasks(first, second)
            skipped = sorted((set(scores[first]) & set(scores[second])) - set(tasks_here))
            print()
            print("%s vs %s" % (arm_label(first), arm_label(second)))
            base = {
                "models": [first[0], second[0]],
                "conditions": [arm_document(first), arm_document(second)],
            }
            if not tasks_here:
                print("  no task where both ran the same version"
                      + ("; %d excluded for differing versions" % len(skipped) if skipped else ""))
                comparisons.append({**base, "tasks": [], "rho": None,
                                    "excluded_for_contract_mismatch": skipped})
                continue
            xs, ys = [], []
            print("  %-30s %14s %14s" % ("task", first[0][:14], second[0][:14]))
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
            comparisons.append({**base, "tasks": tasks_here, "rho": rho,
                                "excluded_for_contract_mismatch": skipped})
    shared = sorted({t for c in comparisons for t in c["tasks"]})
    if incomparable_condition_pairs:
        print()
        print(
            "%d cross-model condition pair(s) were not compared because algorithm or "
            "runtime/statistical-arm identity differs" % len(incomparable_condition_pairs)
        )

    print()
    print("=== proposal validity by model and arm ===")
    validity_rows = []
    for (identity, task, contract, mode, budget), rates in sorted(validity.items()):
        validity_rows.append({
            **condition_document(identity),
            "task": task,
            "task_version": contract,
            "feedback_mode": mode,
            "proposal_budget": budget,
            "run_count": len(rates),
            "mean_valid_rate": st.mean(rates),
        })
        print("  %-20s %-24s @%-8s %s %.2f" % (
            condition_label(identity)[:20], task.split("/")[-1][:24],
            contract[:8], "%s/b%d" % (mode, budget), st.mean(rates),
        ))

    print()
    print("=== cost ===")
    cost_rows = []
    for identity in sorted(tokens):
        model = identity[0]
        total_in = sum(a for a, _ in tokens[identity])
        total_out = sum(b for _, b in tokens[identity])
        price = PRICES.get(model)
        dollars = (total_in / 1e6 * price[0] + total_out / 1e6 * price[1]) if price else None
        cost_rows.append({**condition_document(identity), "runs": len(tokens[identity]),
                          "input_tokens": total_in, "output_tokens": total_out,
                          "estimated_usd": dollars})
        print("  %-20s %3d runs  in=%9d  out=%9d  %s"
              % (condition_label(identity)[:20], len(tokens[identity]), total_in, total_out,
                 "$%.2f" % dollars if dollars is not None else "no published price"))

    verdicts: dict[str, dict[str, str]] = {}
    comparable: dict[str, dict[str, str]] = {}
    if args.admission and Path(args.admission).is_file():
        report = json.loads(Path(args.admission).read_text(encoding="utf-8"))
        by_version: dict[
            tuple[str, str, str, str, str, tuple[int, ...]], dict[str, str]
        ] = defaultdict(dict)
        unknown_version = 0
        for row in report.get("rows", []):
            required = (
                "task", "model", "llm_condition_sha256", "task_version",
                "runtime_source_sha256", "trusted_evaluator_runtime_sha256",
                "algorithm",
            )
            raw_signature = row.get("paired_budget_signature")
            valid_signature = bool(
                isinstance(raw_signature, list)
                and raw_signature
                and all(
                    isinstance(value, int) and not isinstance(value, bool) and value >= 0
                    for value in raw_signature
                )
            )
            if (
                row.get("model") == "unrecorded"
                or row.get("trusted_evidence") is not True
                or any(not row.get(field) for field in required)
                or not valid_signature
            ):
                unknown_version += 1
                continue
            identity = (
                str(row["model"]), str(row["llm_condition_sha256"]),
                str(row["algorithm"]), str(row["runtime_source_sha256"]),
                str(row["trusted_evaluator_runtime_sha256"]),
            )
            actor = condition_label(identity)
            verdicts.setdefault(str(row["task"]), {})[actor] = str(row["verdict"])
            comparison = (
                str(row["task"]), str(row["task_version"]),
                str(row["runtime_source_sha256"]),
                str(row["trusted_evaluator_runtime_sha256"]),
                str(row["algorithm"]),
                tuple(raw_signature),
            )
            by_version[comparison][actor] = str(row["verdict"])
        # Grouped by task version, not filtered on global agreement across every model. An
        # earlier version required all models to share one version and so dropped a whole task
        # whenever a third model had run a different one - discarding the claude/gpt-5.5
        # comparison on six tasks where those two had in fact run the same version.
        comparable = {
            "%s @%s runtime=%s trusted=%s algorithm=%s budgets=%s" % (
                task, version, runtime[:12], trusted[:12], algorithm,
                ",".join(str(value) for value in signature),
            ): actors
            for (task, version, runtime, trusted, algorithm, signature), actors
            in by_version.items()
            if len({actor.split("@", 1)[0] for actor in actors}) > 1
        }
        contested = {k: v for k, v in comparable.items() if len(set(v.values())) > 1}
        agreed = {k: v for k, v in comparable.items() if len(set(v.values())) == 1}
        split = sorted({task for task, _v, _r, _tr, _a, _b in by_version
                        if len({v for t, v, *_rest in by_version if t == task}) > 1})
        print()
        print("=== verdict agreement, within a task version ===")
        print("  task versions carrying a verdict from more than one model: %d"
              % len(comparable))
        print("  agree: %d   disagree: %d" % (len(agreed), len(contested)))
        if split:
            print("  %d task(s) exist in more than one version here, so a pair of models that "
                  "ran\n  different versions of one is not compared on it: %s"
                  % (len(split), ", ".join(t.split("/")[-1] for t in split[:5])
                     + (" ..." if len(split) > 5 else "")))
        if unknown_version:
            print("  %d verdict(s) skipped: the version they were reached against is not "
                  "recorded" % unknown_version)
        for task, per_model in sorted(contested.items()):
            print("    %-34s %s" % (task.split("/")[-1][:34],
                                    "; ".join("%s=%s" % kv for kv in sorted(per_model.items()))))

    Path(args.output).write_text(json.dumps({
        "schema_version": 3,
        "note": "score ranking and admission verdicts are reported separately; they can disagree",
        "models": models,
        "shared_tasks": shared,
        "pairwise": comparisons,
        "incomparable_condition_pairs": incomparable_condition_pairs,
        "open_loop_scores": {
            arm_label(identity): {
                task: st.mean(values) for task, values in per_task.items()
            }
            for identity, per_task in scores.items()
        },
        "cost": cost_rows,
        "proposal_validity": validity_rows,
        "unattributable_run_count": len(runs) - len(trusted_runs),
        "verdicts": verdicts,
        "verdicts_same_version": comparable,
    }, indent=2), encoding="utf-8")
    print()
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
