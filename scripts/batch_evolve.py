#!/usr/bin/env python3
"""Run reproducible, multi-seed Frontier-Science experiments.

The output contains every raw run plus per-task and overall mean/95% CI for
terminal best score, best-so-far AUC over charged proposal/benchmark
``budget_units``, actual ``oracle_calls``, wall time, tokens, and estimated cost.
Only the seven certified tasks are selected unless ``--all`` is explicit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.algorithms import ALGORITHMS, get_algorithm  # noqa: E402
from frontier_science.algorithms.common import llm_condition_sha256  # noqa: E402
from frontier_science.algorithms.common import atomic_write_text  # noqa: E402
from frontier_science.algorithms.common import feedback_scope  # noqa: E402
from frontier_science.config import load_llm_client  # noqa: E402
from frontier_science.protocol import mean_confidence_interval  # noqa: E402
from frontier_science.protocol import compact_trajectory_snapshot  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402
from frontier_science.registry import find_task, list_tasks  # noqa: E402


def _csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _seeds(value: str) -> list[int]:
    try:
        seeds = [int(part) for part in _csv(value)]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("seeds must be comma-separated integers") from exc
    if not seeds:
        raise argparse.ArgumentTypeError("at least one seed is required")
    return seeds


def _run_key(task_id: str, algorithm: str, feedback_mode: str, seed: int) -> str:
    return "%s|%s|%s|%d" % (task_id, algorithm, feedback_mode, seed)


def _condition_order(feedback_modes: list[str], seed: int) -> list[str]:
    """Counterbalance sequential condition order across replicate identifiers."""
    modes = list(feedback_modes)
    return list(reversed(modes)) if int(seed) % 2 else modes


def _preregistration_record(path: Path | None) -> dict[str, Any] | None:
    """Bind an optional preregistration artifact into the run configuration."""

    if path is None:
        return None
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SystemExit("--preregistration must name a regular file")
    payload = resolved.read_bytes()
    try:
        recorded_path = str(resolved.relative_to(ROOT))
    except ValueError:
        recorded_path = str(resolved)
    return {
        "path": recorded_path,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    }


def _latest_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        latest[_run_key(
            run["task"], run["algorithm"], run["feedback_mode"], int(run["seed"])
        )] = run
    return [latest[key] for key in sorted(latest)]


def aggregate_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    fields = {
        "best_score": lambda run: run["best"],
        "best_so_far_auc": lambda run: run["summary"]["best_so_far_auc"],
        "budget_units": lambda run: run["summary"]["budget_units"],
        "oracle_calls": lambda run: run["summary"]["oracle_calls"],
        "wall_seconds": lambda run: run["summary"]["wall_seconds"],
        "input_tokens": lambda run: run["summary"]["llm"].get("input_tokens"),
        "output_tokens": lambda run: run["summary"]["llm"].get("output_tokens"),
        "total_tokens": lambda run: run["summary"]["llm"].get("total_tokens"),
        "estimated_cost_usd": lambda run: run["summary"]["llm"].get(
            "estimated_cost_usd"
        ),
    }
    current = _latest_runs(runs)
    attempts_by_run: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        attempts_by_run.setdefault(_run_key(
            run["task"], run["algorithm"], run["feedback_mode"], int(run["seed"])
        ), []).append(run)
    groups: dict[str, list[dict[str, Any]]] = {}
    for run in current:
        key = "%s|%s|%s" % (run["task"], run["algorithm"], run["feedback_mode"])
        groups.setdefault(key, []).append(run)

    by_condition = {}
    for key, group in sorted(groups.items()):
        successful_group = [run for run in group if not run.get("error")]
        group_attempts = [
            attempt
            for run in group
            for attempt in attempts_by_run[_run_key(
                run["task"], run["algorithm"], run["feedback_mode"], int(run["seed"])
            )]
        ]
        recovered = sum(
            not run.get("error") and any(
                attempt.get("error") for attempt in attempts_by_run[_run_key(
                    run["task"], run["algorithm"], run["feedback_mode"], int(run["seed"])
                )]
            )
            for run in group
        )
        by_condition[key] = {
            # ``n`` remains the valid-only sample size for compatibility. The
            # scheduled denominator and retry history are retained separately so
            # a recovered condition cannot erase an earlier failure.
            "n": len(successful_group),
            "scheduled_n": len(group),
            "successful_runs": len(successful_group),
            "terminal_failed_runs": len(group) - len(successful_group),
            "completion_rate": len(successful_group) / len(group),
            "attempt_count": len(group_attempts),
            "failed_attempts": sum(bool(run.get("error")) for run in group_attempts),
            "recovered_runs": recovered,
            **{name: mean_confidence_interval(getter(run) for run in successful_group)
               for name, getter in fields.items()},
        }
    successful = [run for run in current if not run.get("error")]
    failed_attempts = sum(bool(run.get("error")) for run in runs)
    recovered_run_keys = {
        key
        for key, attempts in attempts_by_run.items()
        if not attempts[-1].get("error") and any(run.get("error") for run in attempts)
    }
    valid_only = {
        name: mean_confidence_interval(getter(run) for run in successful)
        for name, getter in fields.items()
    } if successful else {}
    return {
        "attempt_count": len(runs),
        "superseded_attempts": len(runs) - len(current),
        "failed_attempts": failed_attempts,
        "attempt_failure_rate": failed_attempts / len(runs) if runs else 0.0,
        "recovered_runs": len(recovered_run_keys),
        "successful_runs": len(successful),
        "failed_runs": len(current) - len(successful),
        "intent_to_evaluate": {
            "scheduled_runs": len(current),
            "successful_runs": len(successful),
            "terminal_failed_runs": len(current) - len(successful),
            "completion_rate": len(successful) / len(current) if current else 0.0,
            "run_cells_with_any_failed_attempt": sum(
                any(run.get("error") for run in attempts)
                for attempts in attempts_by_run.values()
            ),
            "recovered_runs": len(recovered_run_keys),
        },
        "quality_metrics_scope": (
            "latest successful runs only; interpret jointly with intent_to_evaluate "
            "and failed_attempts"
        ),
        "by_condition": by_condition,
        "overall": valid_only,
        "overall_valid_only": valid_only,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", default=None, help="comma-separated task IDs/names")
    parser.add_argument("--all", action="store_true", help="include uncertified inventory")
    parser.add_argument("--algorithms", default="greedy_rewrite", help="comma-separated algorithms")
    parser.add_argument(
        "--feedback-modes", default="normal",
        help=(
            "normal,none,shuffled,score_only,delayed_replay,selection_blind "
            "(the last three protocol controls are greedy-only)"
        ),
    )
    parser.add_argument("--seeds", type=_seeds, default=[0, 1, 2, 3, 4])
    parser.add_argument("--budget", type=int, default=30)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--llm-config", default=None)
    parser.add_argument(
        "--preregistration", type=Path, default=None,
        help="immutable preregistration artifact to hash-bind into the report",
    )
    parser.add_argument("--workdir", type=Path, default=ROOT / "runs" / "experiments")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--resume", action="store_true", help="resume individual runs and result file")
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(raw_argv)
    if args.budget < 0:
        raise SystemExit("--budget must be non-negative")
    algorithms = _csv(args.algorithms)
    unknown = sorted(set(algorithms) - set(ALGORITHMS))
    if unknown:
        raise SystemExit("unknown algorithms: %s" % ", ".join(unknown))
    feedback_modes = _csv(args.feedback_modes)
    unknown_modes = sorted(
        set(feedback_modes) - {
            "normal", "none", "shuffled", "score_only", "delayed_replay",
            "selection_blind",
        }
    )
    if unknown_modes:
        raise SystemExit("unknown feedback modes: %s" % ", ".join(unknown_modes))
    greedy_only_modes = {"score_only", "delayed_replay", "selection_blind"}
    requested_greedy_only = sorted(set(feedback_modes) & greedy_only_modes)
    if requested_greedy_only and set(algorithms) != {"greedy_rewrite"}:
        raise SystemExit(
            "%s implemented only for greedy_rewrite; run upstream backend controls "
            "as separately named conditions" % ", ".join(requested_greedy_only)
        )

    include_uncertified = bool(args.all)
    if args.tasks:
        specs = [find_task(name, include_uncertified=include_uncertified) for name in _csv(args.tasks)]
    else:
        specs = list_tasks(None if args.all else "certified")
    if not specs:
        raise SystemExit("no tasks selected")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or (ROOT / "experiments" / ("protocol_%s.json" % timestamp))
    output = output.expanduser().resolve()
    work_root = args.workdir.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    work_root.mkdir(parents=True, exist_ok=True)
    llm = load_llm_client(args.llm_config)
    provenance = source_provenance(
        ROOT, command=[sys.executable, str(Path(__file__).resolve()), *raw_argv]
    )
    endpoint_hash = hashlib.sha256(llm.config.base_url.encode("utf-8")).hexdigest()
    current_environment = {"python": sys.version, "platform": platform.platform()}
    experiment_config = {
        "tasks": [spec.task_id for spec in specs],
        "algorithms": algorithms,
        "feedback_modes": feedback_modes,
        "trajectory_snapshot_schema_version": 2,
        "feedback_protocols": {
            mode: feedback_scope(mode) for mode in feedback_modes
        },
        "condition_order": "as_listed_for_even_seeds_reversed_for_odd_seeds",
        "preregistration": _preregistration_record(args.preregistration),
        "seeds": args.seeds,
        "replicate_identifier_scope": (
            "controls local Python/random ordering only; the endpoint exposes no "
            "server-side generation seed, so same-number cells do not share model draws"
        ),
        "resource_matching": {
            "proposal_budget_and_max_output_tokens": "matched by configuration",
            "realized_input_output_and_total_tokens": (
                "measured per event; not assumed matched; use a preregistered common-token "
                "horizon or model token imbalance explicitly"
            ),
        },
        "budget": args.budget,
        "timeout_s": args.timeout,
        "work_root": str(work_root),
        "llm_condition_sha256": llm_condition_sha256(llm),
        "llm": {
            "wire": llm.config.wire,
            "endpoint_sha256": endpoint_hash,
            "model": llm.config.model,
            "max_output_tokens": llm.config.max_output_tokens,
            "temperature": llm.config.temperature,
            "reasoning_effort": llm.config.reasoning_effort,
            "input_cost_per_million": llm.config.input_cost_per_million,
            "output_cost_per_million": llm.config.output_cost_per_million,
            "server_side_seed_control": False,
        },
    }

    document: dict[str, Any]
    if args.resume and output.is_file():
        document = json.loads(output.read_text(encoding="utf-8"))
        if document.get("config") != experiment_config:
            raise SystemExit("refusing to resume: experiment config does not match the report")
        if document.get("environment") != current_environment:
            raise SystemExit("refusing to resume: Python/platform environment does not match")
        previous = document.get("source_provenance") or {}
        if (
            previous.get("git_revision") != provenance.get("git_revision")
            or previous.get("source_tree_dirty") != provenance.get("source_tree_dirty")
            or previous.get("source_changes") != provenance.get("source_changes")
        ):
            raise SystemExit("refusing to resume: source provenance does not match the report")
    elif args.resume:
        raise SystemExit("--resume requires an existing --output report")
    else:
        document = {
            "schema_version": 1,
            "trust_status": "TRUSTED_SECURE_EVAL",
            "evidence_scope": "PROTOCOL_SMOKE_ONLY" if args.budget == 0 else "MODEL_PERFORMANCE",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_provenance": provenance,
            "environment": current_environment,
            "config": experiment_config,
            "runs": [],
        }
        if args.budget == 0:
            document["warning"] = (
                "Baseline-only multi-seed smoke: validates protocol/artifacts, not search performance."
            )
    done = {
        _run_key(run["task"], run["algorithm"], run["feedback_mode"], int(run["seed"]))
        for run in _latest_runs(document.get("runs", []))
        if not run.get("error")
    }
    total = len(specs) * len(algorithms) * len(feedback_modes) * len(args.seeds)
    counter = 0
    for spec in specs:
        for algorithm_name in algorithms:
            algorithm = get_algorithm(algorithm_name)
            for seed in args.seeds:
                for feedback_mode in _condition_order(feedback_modes, seed):
                    counter += 1
                    key = _run_key(spec.task_id, algorithm_name, feedback_mode, seed)
                    if key in done:
                        print("[%d/%d] skip completed %s" % (counter, total, key), flush=True)
                        continue
                    run_dir = work_root / spec.task_id.replace("/", "__") / algorithm_name / feedback_mode / ("seed_%d" % seed)
                    print("[%d/%d] %s" % (counter, total, key), flush=True)
                    started = time.monotonic()
                    try:
                        result = algorithm(
                            spec, llm, budget=args.budget, timeout_s=args.timeout,
                            workdir=run_dir, seed=seed, resume=args.resume,
                            feedback_mode=feedback_mode, log_fn=lambda line: print("  " + line),
                        )
                        entry = {
                            "task": spec.task_id,
                            "algorithm": result.algorithm,
                            "feedback_mode": feedback_mode,
                            "seed": seed,
                            "baseline": result.baseline_score,
                            "best": result.best_score,
                            "accepted": result.accepted,
                            "evaluated": result.evaluated,
                            "workdir": str(run_dir),
                            "summary": result.summary,
                            # Generated only after the backend returns. Sealed science
                            # metrics remain outside all agent/search-owned state.
                            "trajectory_snapshot": compact_trajectory_snapshot(
                                run_dir / "trajectory.jsonl", schema_version=2
                            ),
                        }
                    except Exception as exc:  # noqa: BLE001 - retain failed conditions
                        entry = {
                            "task": spec.task_id,
                            "algorithm": algorithm_name,
                            "feedback_mode": feedback_mode,
                            "seed": seed,
                            "workdir": str(run_dir),
                            "error": "%s: %s" % (type(exc).__name__, exc),
                            "wall_seconds": time.monotonic() - started,
                        }
                    document.setdefault("runs", []).append(entry)
                    document["aggregate"] = aggregate_runs(document["runs"])
                    atomic_write_text(
                        output, json.dumps(document, indent=2, allow_nan=False) + "\n"
                    )

    document["completed_at"] = datetime.now(timezone.utc).isoformat()
    document["aggregate"] = aggregate_runs(document["runs"])
    execution_passed = (
        document["aggregate"]["failed_runs"] == 0
        and document["aggregate"]["successful_runs"] == total
    )
    finalize_report_trust(document, execution_passed)
    atomic_write_text(output, json.dumps(document, indent=2, allow_nan=False) + "\n")
    print("Results: %s" % output)
    return 0 if execution_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
