"""Immutable single-task calibration and paired-budget campaign plans.

Plans and replay summaries are operator artifacts, not frozen scientific evidence.
The executor delegates model calls to batch_evolve; replay never loads an LLM client.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sle.algorithms.common import (  # noqa: E402
    atomic_write_text, llm_condition_sha256, runtime_source_sha256,
    task_contract_sha256, task_package_sha256,
)
from sle.config import load_llm_client  # noqa: E402
from sle.provenance import source_provenance  # noqa: E402
from sle.protocol import validate_trajectory  # noqa: E402
from sle.registry import find_task  # noqa: E402

ORCHESTRATION_FILES = (
    "scripts/task_campaign.py", "scripts/calibrate_task.py", "scripts/run_delta_ladder.py",
    "scripts/batch_evolve.py", "scripts/reporting_trajectory.py",
    "scripts/report_admission_criterion.py",
)


def digest(document):
    return hashlib.sha256(json.dumps(document, sort_keys=True, allow_nan=False).encode()).hexdigest()


def orchestration_hash():
    return digest({name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                   if (ROOT / name).is_file() else None for name in ORCHESTRATION_FILES})


def bindings(task, config):
    spec = find_task(task, include_uncertified=True)
    client = load_llm_client(str(config))  # construction only; no API calls
    return {"task_id": spec.task_id, "task_package_sha256": task_package_sha256(spec),
            "task_contract_sha256": task_contract_sha256(spec),
            "runtime_source_sha256": runtime_source_sha256(),
            "llm_condition_sha256": llm_condition_sha256(client),
            "model": client.config.model, "orchestration_sha256": orchestration_hash()}


def make_plan(kind, *, task, config, workdir, seeds, budgets,
              budget_mode="proposals", proposal_cap=None, timeout=300.0):
    if kind not in {"calibration", "delta_ladder"}:
        raise ValueError("unknown campaign kind")
    if not seeds or len(set(seeds)) != len(seeds) or any(type(x) is not int or x < 0 for x in seeds):
        raise ValueError("seeds must be unique nonnegative integers")
    if not budgets or len(set(budgets)) != len(budgets) or any(
        type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in budgets
    ):
        raise ValueError("budgets must be unique positive finite numbers")
    if budgets != sorted(budgets):
        raise ValueError("budgets must be in increasing order")
    if budget_mode not in {"proposals", "active_wall"}:
        raise ValueError("unsupported budget mode")
    if budget_mode == "proposals" and any(int(x) != x for x in budgets):
        raise ValueError("proposal budgets must be integers")
    if budget_mode == "active_wall" and (type(proposal_cap) is not int or proposal_cap < 1):
        raise ValueError("active_wall requires an explicit positive --proposal-cap")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive and finite")
    config, workdir = Path(config).resolve(), Path(workdir).resolve()
    identity = bindings(task, config)
    modes = ["selection_blind"] if kind == "calibration" else ["normal", "selection_blind"]
    cohorts = []
    for index, budget in enumerate(budgets):
        cohort_root = workdir / ("budget_%02d" % index)
        cohorts.append({"id": "budget_%02d" % index, "budget": budget,
                        "proposal_budget": int(budget) if budget_mode == "proposals" else proposal_cap,
                        "active_wall_horizon_s": budget if budget_mode == "active_wall" else None,
                        "workdir": str(cohort_root), "batch_output": str(cohort_root / "batch.json")})
    cells = []
    for cohort in cohorts:
        for seed in seeds:
            for mode in modes:
                cells.append({"cohort": cohort["id"], "budget": cohort["budget"],
                              "seed": seed, "feedback_mode": mode,
                              "workdir": str(Path(cohort["workdir"]) /
                                  identity["task_id"].replace("/", "__") / "greedy_rewrite" /
                                  mode / ("seed_%d" % seed))})
    plan = {"schema_version": 1, "kind": kind, "bindings": identity,
            "source_provenance": source_provenance(ROOT), "llm_config": str(config),
            "workdir": str(workdir), "algorithm": "greedy_rewrite", "seeds": seeds,
            "feedback_modes": modes, "budget_mode": budget_mode, "budgets": budgets,
            "timeout_s": timeout, "condition_order_design": "reverse_parity",
            "cohorts": cohorts, "cells": cells,
            "interpretation": "Each budget has independently executed paired cells; seed labels do not control provider draws. Missing cells stay in the denominator.",
            "task_card_updates": "separate review only; never modified by this command"}
    plan["plan_sha256"] = digest(plan)
    return plan


def read_plan(path):
    plan = json.loads(Path(path).read_text())
    recorded = plan.pop("plan_sha256", None)
    if not recorded or digest(plan) != recorded or plan.get("schema_version") != 1:
        raise ValueError("plan content hash/schema mismatch")
    plan["plan_sha256"] = recorded
    return plan


def batch_command(plan, cohort, *, resume=False):
    command = [sys.executable, str(ROOT / "scripts/batch_evolve.py"),
               "--tasks", plan["bindings"]["task_id"], "--all", "--algorithms", plan["algorithm"],
               "--feedback-modes", ",".join(plan["feedback_modes"]),
               "--seeds", ",".join(map(str, plan["seeds"])),
               "--condition-order-design", plan["condition_order_design"],
               "--budget", str(cohort["proposal_budget"]), "--timeout", str(plan["timeout_s"]),
               "--run-role", "calibration" if plan["kind"] == "calibration" else "performance",
               "--llm-config", plan["llm_config"], "--workdir", cohort["workdir"],
               "--output", cohort["batch_output"]]
    if cohort["active_wall_horizon_s"] is not None:
        command += ["--active-wall-horizon", str(cohort["active_wall_horizon_s"])]
    if resume:
        command.append("--resume")
    return command


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _cell_result(plan, cohort, cell, batch):
    result = {**cell, "status": "missing", "endpoint": None, "baseline": None}
    try:
        if batch is None:
            return result
        if isinstance(batch, str):
            raise ValueError(batch)
        config = batch.get("config") or {}
        expected_config = {"tasks": [plan["bindings"]["task_id"]],
                           "algorithms": [plan["algorithm"]], "seeds": plan["seeds"],
                           "feedback_modes": plan["feedback_modes"],
                           "budget": cohort["proposal_budget"], "timeout_s": plan["timeout_s"],
                           "active_wall_horizon_s": cohort["active_wall_horizon_s"],
                           "llm_condition_sha256": plan["bindings"]["llm_condition_sha256"]}
        if any(config.get(key) != value for key, value in expected_config.items()):
            raise ValueError("batch configuration differs from the fixed plan")
        attempts = [run for run in batch.get("runs", [])
                    if (run.get("task"), run.get("algorithm"), run.get("seed"), run.get("feedback_mode")) ==
                    (plan["bindings"]["task_id"], plan["algorithm"], cell["seed"], cell["feedback_mode"])]
        result["attempt_count"] = len(attempts)
        if not attempts:
            return result
        entry = attempts[-1]
        if entry.get("error") or entry.get("protocol_incomplete"):
            result.update(status="failed" if entry.get("error") else "incomplete",
                          detail=entry.get("error") or entry.get("protocol_incomplete"))
            return result
        directory = Path(cell["workdir"])
        if Path(entry.get("workdir", "")).resolve() != directory:
            raise ValueError("run directory differs from scheduled cell")
        manifest = _read_json(directory / "run_manifest.json")
        expected_manifest = {key: plan["bindings"][key] for key in (
            "task_id", "task_package_sha256", "task_contract_sha256",
            "runtime_source_sha256", "llm_condition_sha256")}
        expected_manifest.update(algorithm=plan["algorithm"], seed=cell["seed"], feedback_mode=cell["feedback_mode"])
        if any(manifest.get(key) != value for key, value in expected_manifest.items()):
            raise ValueError("run manifest differs from the fixed task/model/runtime identity")
        protocol = manifest.get("protocol") or {}
        if (protocol.get("evaluator_timeout_seconds") != plan["timeout_s"] or
                protocol.get("active_wall_horizon_s") != cohort["active_wall_horizon_s"]):
            raise ValueError("run protocol differs from the planned time budget")
        from scripts.reporting_trajectory import read_incumbents
        trajectory = directory / "trajectory.jsonl"
        selected = read_incumbents(trajectory)
        events = [json.loads(line) for line in trajectory.read_text().splitlines() if line.strip()]
        validate_trajectory(events)
        snapshot_hash = (entry.get("trajectory_snapshot") or {}).get("trajectory_sha256")
        if snapshot_hash != hashlib.sha256(trajectory.read_bytes()).hexdigest():
            raise ValueError("batch snapshot is not bound to the replayed trajectory")
        if not selected:
            raise ValueError("empty trajectory")
        if any(type(event.get("accepted")) is not bool for event in events[1:]):
            raise ValueError("new campaign requires explicit acceptance records")
        if plan["budget_mode"] == "proposals" and len(events) != cohort["proposal_budget"] + 1:
            result.update(status="incomplete", detail="trajectory does not reach the planned proposal horizon")
            return result
        summary = entry.get("summary") or {}
        if plan["budget_mode"] == "active_wall" and (
            summary.get("horizon_reached") is not True or summary.get("baseline_crossed_horizon") is True
        ):
            result.update(status="incomplete", detail="active-wall horizon was not measured")
            return result
        if plan["budget_mode"] == "active_wall":
            horizon = cohort["active_wall_horizon_s"]
            for event in events:
                wall = event.get("cumulative_wall_seconds")
                if type(wall) not in (int, float) or not math.isfinite(wall) or wall < 0:
                    raise ValueError("active-wall replay requires measured event times")
                if event.get("accepted") is True and wall > horizon:
                    raise ValueError("an incumbent was accepted after the active-wall horizon")
            if events[-1]["cumulative_wall_seconds"] < horizon:
                result.update(status="incomplete", detail="trajectory ends before the active-wall horizon")
                return result
        result.update(status="complete", baseline=selected[0]["score"], endpoint=selected[-1]["score"],
                      baseline_gain=selected[-1]["score"] - selected[0]["score"],
                      trajectory_sha256=hashlib.sha256(trajectory.read_bytes()).hexdigest(),
                      manifest_sha256=digest(manifest), selected_metrics=selected[-1].get("metrics"),
                      usage=summary.get("llm"), active_wall_seconds=summary.get("wall_seconds"))
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        result.update(status="invalid_evidence", detail=str(exc))
    return result


def replay(plan):
    cells = []
    for cohort in plan["cohorts"]:
        path = Path(cohort["batch_output"])
        try:
            batch = _read_json(path) if path.is_file() else None
        except (OSError, ValueError) as exc:
            batch = "unreadable batch report: " + str(exc)
        cells += [_cell_result(plan, cohort, cell, batch) for cell in plan["cells"]
                  if cell["cohort"] == cohort["id"]]
    counts = dict(Counter(cell["status"] for cell in cells))
    paired = []
    for cohort in plan["cohorts"]:
        for seed in plan["seeds"]:
            arms = {cell["feedback_mode"]: cell for cell in cells
                    if cell["cohort"] == cohort["id"] and cell["seed"] == seed}
            if plan["kind"] == "delta_ladder":
                complete = all(arms.get(mode, {}).get("status") == "complete" for mode in plan["feedback_modes"])
                paired.append({"cohort": cohort["id"], "budget": cohort["budget"], "seed": seed,
                               "status": "complete" if complete else "incomplete",
                               "delta": arms["normal"]["endpoint"] - arms["selection_blind"]["endpoint"] if complete else None})
    ladder = []
    for budget in plan["budgets"]:
        pairs = [pair for pair in paired if pair["budget"] == budget]
        complete = [pair for pair in pairs if pair["status"] == "complete"]
        ladder.append({"budget": budget, "scheduled_pairs": len(pairs), "complete_pairs": len(complete),
                       "mean_delta": sum(pair["delta"] for pair in complete) / len(pairs)
                       if pairs and len(complete) == len(pairs) else None})
    completed = counts.get("complete", 0)
    return {"schema_version": 1, "kind": plan["kind"], "plan_sha256": plan["plan_sha256"],
            "status": "complete" if completed == len(cells) else "incomplete",
            "scheduled_cells": len(cells), "complete_cells": completed,
            "completion_rate": completed / len(cells), "cell_status_counts": counts,
            "cells": cells, "paired": paired, "ladder": ladder,
            "scientific_admission": "not_assessed", "trusted_evidence": False,
            "note": "Content-checked operator replay; no certification, difficulty label, or task-card update. Review independent reference/shortcut calibration and feasibility/held-out diagnostics before admission."}


def report_commands(plan, directory):
    """Reuse repository reports, separately from the fixed-cell completeness result."""
    directory = Path(directory)
    return [
        [sys.executable, str(ROOT / "scripts/report_admission_criterion.py"),
         "--runs", plan["workdir"], "--output", str(directory / "admission.json")],
    ]


def build_reports(plan, report, directory):
    if report["status"] != "complete":
        return {"status": "blocked_incomplete_cells"}
    if plan["budget_mode"] != "proposals":
        return {"status": "unavailable", "reason": "existing admission reporter uses proposal horizons; do not reinterpret them as seconds"}
    expected = {str(Path(cell["workdir"]) / "run_manifest.json") for cell in plan["cells"]}
    present = {str(path) for path in Path(plan["workdir"]).rglob("run_manifest.json")}
    if present != expected:
        return {"status": "blocked_unscheduled_runs", "reason": "report input tree must contain exactly the planned runs"}
    Path(directory).mkdir(parents=True, exist_ok=True)
    results = []
    for command in report_commands(plan, directory):
        done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        output = Path(command[-1])
        results.append({"script": Path(command[1]).name, "returncode": done.returncode,
                        "output": str(output),
                        "sha256": hashlib.sha256(output.read_bytes()).hexdigest() if done.returncode == 0 and output.is_file() else None})
        if done.returncode:
            return {"status": "failed", "reports": results,
                    "reason": "auxiliary reporter failed; run the listed command for diagnostics"}
    return {"status": "generated", "reports": results,
            "scope": "Existing admission criterion at its supported proposal cuts; fixed-plan completeness and per-budget paired means remain in this campaign report."}


def execute(plan, *, resume=False):
    if platform.system() != "Linux":
        raise ValueError("campaign execution requires the Linux candidate sandbox")
    provenance = source_provenance(ROOT)
    if not provenance["git_available"] or provenance["source_tree_dirty"] is not False:
        raise ValueError("execute from a clean known source revision")
    if bindings(plan["bindings"]["task_id"], plan["llm_config"]) != plan["bindings"]:
        raise ValueError("task/model/runtime/orchestration changed after planning; create a new plan")
    outcomes = []
    for cohort in plan["cohorts"]:
        command = batch_command(plan, cohort, resume=resume)
        # Stream normal batch output; no source/config contents or environment are logged here.
        done = subprocess.run(command, cwd=ROOT, check=False)
        outcomes.append({"cohort": cohort["id"], "returncode": done.returncode})
    return outcomes


def main(kind, argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True, help="immutable plan JSON; created exclusively")
    parser.add_argument("--output", type=Path, required=True, help="review summary JSON")
    parser.add_argument("--task")
    parser.add_argument("--llm-config", type=Path)
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--seeds")
    parser.add_argument("--budgets")
    parser.add_argument("--budget-mode", choices=("proposals", "active_wall"))
    parser.add_argument("--proposal-cap", type=int)
    parser.add_argument("--timeout", type=float)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true", help="default: write/review plan without model calls")
    modes.add_argument("--replay", action="store_true", help="read fixed-plan results without model calls")
    modes.add_argument("--execute", action="store_true", help="run the fixed plan; may incur provider costs")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--reports", type=Path, help="also run existing admission/discovery reports after complete replay")
    args = parser.parse_args(argv)
    try:
        if args.resume and not args.execute:
            raise ValueError("--resume requires --execute")
        if args.reports and not (args.replay or args.execute):
            raise ValueError("--reports requires --replay or --execute")
        if args.plan.resolve() == args.output.resolve():
            raise ValueError("plan and output must be distinct")
        generation = [args.task, args.llm_config, args.workdir, args.seeds, args.budgets,
                      args.budget_mode, args.proposal_cap, args.timeout]
        if args.plan.exists():
            if any(value is not None for value in generation):
                raise ValueError("existing plans are immutable; omit planning options or choose a new --plan")
            plan = read_plan(args.plan)
        else:
            if args.replay or args.execute:
                raise ValueError("first create and review a dry-run plan before replay or execution")
            if not args.task or not args.llm_config or not args.workdir:
                raise ValueError("new plans require --task, --llm-config and --workdir")
            if args.budget_mode == "active_wall" and not args.budgets:
                raise ValueError("active_wall requires explicit --budgets in seconds")
            plan = make_plan(kind, task=args.task, config=args.llm_config, workdir=args.workdir,
                             seeds=[int(x) for x in (args.seeds or "0,1,2").split(",")],
                             budgets=[float(x) for x in (args.budgets or ("1" if kind == "calibration" else "3,5,8,10,12")).split(",")],
                             budget_mode=args.budget_mode or "proposals", proposal_cap=args.proposal_cap,
                             timeout=args.timeout if args.timeout is not None else 300.0)
            args.plan.parent.mkdir(parents=True, exist_ok=True)
            with args.plan.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(plan, indent=2, allow_nan=False) + "\n")
        if plan["kind"] != kind:
            raise ValueError("plan kind does not match this command")
        outcomes = execute(plan, resume=args.resume) if args.execute else []
        report = replay(plan) if args.execute or args.replay else {
            "schema_version": 1, "status": "planned", "kind": kind,
            "plan_sha256": plan["plan_sha256"], "scheduled_cells": len(plan["cells"]),
            "complete_cells": 0, "scientific_admission": "not_assessed", "trusted_evidence": False,
            "commands": [batch_command(plan, cohort) for cohort in plan["cohorts"]]}
        report["execution_outcomes"] = outcomes
        execution_ok = all(outcome["returncode"] == 0 for outcome in outcomes)
        if not execution_ok:
            # A prior complete replay does not make a failed new execution pass.
            report["replay_status"] = report["status"]
            report["status"] = "execution_failed"
        report["report_commands"] = report_commands(plan, args.reports or args.output.parent / "science_reports")
        if args.reports:
            report["science_reports"] = build_reports(plan, report, args.reports)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(args.output, json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(report["status"], str(args.output))
        reports_ok = not args.reports or report["science_reports"]["status"] == "generated"
        return 0 if execution_ok and report["status"] in {"planned", "complete"} and reports_ok else 2
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
