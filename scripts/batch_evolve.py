#!/usr/bin/env python3
"""Run reproducible, multi-seed Frontier-Science experiments.

The output contains every raw run plus per-task and overall mean/95% CI for
terminal best score, best-so-far AUC over charged proposal/benchmark
``budget_units``, actual ``oracle_calls``, wall time, tokens, and estimated cost.
Only the seven certified tasks are selected unless ``--all`` is explicit.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import multiprocessing
import platform
import random
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
from frontier_science.llm import LLMClient  # noqa: E402
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


def _condition_order(
    feedback_modes: list[str], seed: int, design: str = "reverse_parity",
    *, schedule_index: int | None = None,
) -> list[str]:
    """Return the preregistered within-block condition execution order."""
    modes = list(feedback_modes)
    if design == "reverse_parity":
        return list(reversed(modes)) if int(seed) % 2 else modes
    if design == "balanced_williams":
        if len(modes) != 4 or len(set(modes)) != 4:
            raise ValueError("balanced_williams requires exactly four distinct modes")
        # A B D C, B C A D, C D B A, D A C B. Each condition occupies each
        # position once and every directed first-order carryover occurs once.
        rows = (
            (0, 1, 3, 2),
            (1, 2, 0, 3),
            (2, 3, 1, 0),
            (3, 0, 2, 1),
        )
        index = int(seed) if schedule_index is None else int(schedule_index)
        return [modes[position] for position in rows[index % len(rows)]]
    raise ValueError("unknown condition order design %r" % design)


def _condition_schedule(
    feedback_modes: list[str], seeds: list[int], design: str,
    randomization_seed: int | None,
) -> list[list[str]]:
    """Build and freeze the full within-block condition schedule."""
    if design == "balanced_williams":
        if randomization_seed is None:
            raise ValueError(
                "balanced_williams requires --condition-order-randomization-seed"
            )
        row_indices = [index % 4 for index in range(len(seeds))]
        random.Random(int(randomization_seed)).shuffle(row_indices)
        return [
            _condition_order(
                feedback_modes, seed, design, schedule_index=row_index
            )
            for seed, row_index in zip(seeds, row_indices)
        ]
    if randomization_seed is not None:
        raise ValueError(
            "--condition-order-randomization-seed requires balanced_williams"
        )
    return [
        _condition_order(feedback_modes, seed, design)
        for seed in seeds
    ]


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


def _execution_blocks(
    task_ids: list[str], algorithms: list[str], seeds: list[int],
    condition_schedule: list[list[str]],
) -> list[dict[str, Any]]:
    if len(seeds) != len(condition_schedule):
        raise ValueError("condition schedule does not match replicate identifiers")
    blocks = []
    for task_id in task_ids:
        for algorithm in algorithms:
            for seed, ordered_modes in zip(seeds, condition_schedule):
                blocks.append({
                    "block_index": len(blocks) + 1,
                    "task": task_id,
                    "algorithm": algorithm,
                    "seed": int(seed),
                    "feedback_modes": list(ordered_modes),
                })
    return blocks


def _execute_block(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute one task/algorithm/replicate block in an isolated process.

    Conditions remain serial in their frozen Williams order.  Only distinct
    blocks may be scheduled concurrently, so Python RNG state, environment
    changes and LLM client accounting cannot leak between blocks.
    """
    task_id = str(payload["task"])
    algorithm_name = str(payload["algorithm"])
    seed = int(payload["seed"])
    spec = find_task(task_id, include_uncertified=True)
    algorithm = get_algorithm(algorithm_name)
    # The parent hashes this exact config object before dispatch.  Do not
    # re-read a mutable git-ignored YAML file inside the worker.
    llm = LLMClient(payload["llm_config"])
    work_root = Path(payload["work_root"])
    skip_keys = set(payload.get("skip_keys") or [])
    entries = []
    logs = []
    for position, feedback_mode in enumerate(payload["feedback_modes"], 1):
        key = _run_key(task_id, algorithm_name, feedback_mode, seed)
        if key in skip_keys:
            logs.append("skip completed %s" % key)
            continue
        run_dir = (
            work_root / task_id.replace("/", "__") / algorithm_name
            / feedback_mode / ("seed_%d" % seed)
        )
        checkpoint = run_dir / "checkpoint.json"
        trajectory = run_dir / "trajectory.jsonl"
        manifest = run_dir / "run_manifest.json"
        full_resume = bool(
            checkpoint.is_file() and trajectory.is_file() and manifest.is_file()
        )
        baseline_retry = bool(
            manifest.is_file() and not checkpoint.exists()
            and not trajectory.exists()
        )
        resume_cell = bool(payload["resume"] and (full_resume or baseline_retry))
        partial_resume_state = bool(payload["resume"] and run_dir.exists()
                                    and any(run_dir.iterdir()) and not resume_cell)
        started = time.monotonic()
        cell_logs = []
        try:
            if partial_resume_state:
                raise ValueError(
                    "incomplete cell state lacks the full resume artifact set"
                )
            result = algorithm(
                spec,
                llm,
                budget=int(payload["budget"]),
                timeout_s=float(payload["timeout_s"]),
                workdir=run_dir,
                seed=seed,
                resume=resume_cell,
                feedback_mode=feedback_mode,
                log_fn=cell_logs.append,
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
        entry["execution_block_index"] = int(payload["block_index"])
        entry["within_block_position"] = position
        entries.append(entry)
        logs.extend("[%s] %s" % (feedback_mode, line) for line in cell_logs)
        if entry.get("error"):
            logs.append(
                "[%s] block halted before later conditions after outer error"
                % feedback_mode
            )
            break
    return {
        "block_index": int(payload["block_index"]),
        "task": task_id,
        "algorithm": algorithm_name,
        "seed": seed,
        "entries": entries,
        "logs": logs,
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
    parser.add_argument(
        "--condition-order-randomization-seed", type=int, default=None,
        help="preregistered seed that randomizes balanced Williams rows over blocks",
    )
    parser.add_argument("--seeds", type=_seeds, default=[0, 1, 2, 3, 4])
    parser.add_argument(
        "--condition-order-design",
        choices=("reverse_parity", "balanced_williams"),
        default="reverse_parity",
        help="within-task/identifier execution-order schedule",
    )
    parser.add_argument("--budget", type=int, default=30)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--block-workers", type=int, default=1,
        help=(
            "maximum concurrent task/algorithm/replicate blocks; conditions "
            "inside each block remain serial in the frozen order"
        ),
    )
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
    if args.block_workers < 1:
        raise SystemExit("--block-workers must be >= 1")
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
    try:
        condition_schedule = _condition_schedule(
            feedback_modes,
            args.seeds,
            args.condition_order_design,
            args.condition_order_randomization_seed,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

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
        "condition_order": args.condition_order_design,
        "condition_order_randomization_seed": (
            args.condition_order_randomization_seed
        ),
        "condition_order_schedule": [
            {"replicate_identifier": seed, "feedback_modes": order}
            for seed, order in zip(args.seeds, condition_schedule)
        ],
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
        "block_workers": args.block_workers,
        "block_parallelism": {
            "unit": "task_algorithm_replicate",
            "within_block_conditions": "serial_in_condition_order_schedule",
            "cross_block_scheduling": "fixed_submission_order_nonadaptive",
            "maximum_concurrent_blocks": args.block_workers,
        },
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
    blocks = _execution_blocks(
        [spec.task_id for spec in specs], algorithms, args.seeds,
        condition_schedule,
    )
    payloads = [
        {
            **block,
            "llm_config": llm.config,
            "work_root": str(work_root),
            "budget": args.budget,
            "timeout_s": args.timeout,
            "resume": args.resume,
            "skip_keys": sorted(done),
        }
        for block in blocks
        if any(
            _run_key(
                block["task"], block["algorithm"], mode, block["seed"]
            ) not in done
            for mode in block["feedback_modes"]
        )
    ]
    # Persist the cohort plan and source provenance before any worker can make
    # an LLM call. A process interruption can then be resumed without
    # reconstructing an unrecorded design.
    document["aggregate"] = aggregate_runs(document.get("runs") or [])
    atomic_write_text(
        output, json.dumps(document, indent=2, allow_nan=False) + "\n"
    )

    def retain_block(result: dict[str, Any]) -> None:
        for line in result.get("logs") or []:
            print("  " + line, flush=True)
        document.setdefault("runs", []).extend(result.get("entries") or [])
        document["aggregate"] = aggregate_runs(document["runs"])
        atomic_write_text(
            output, json.dumps(document, indent=2, allow_nan=False) + "\n"
        )
        print(
            "[block %d/%d] complete %s|%s|%d" % (
                result["block_index"], len(blocks), result["task"],
                result["algorithm"], result["seed"],
            ),
            flush=True,
        )

    if args.block_workers == 1:
        for payload in payloads:
            retain_block(_execute_block(payload))
    else:
        context = multiprocessing.get_context("spawn")
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=args.block_workers, mp_context=context,
        ) as executor:
            future_payload = {
                executor.submit(_execute_block, payload): payload
                for payload in payloads
            }
            for future in concurrent.futures.as_completed(future_payload):
                payload = future_payload[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001 - retain crashed blocks
                    document.setdefault("block_failures", []).append({
                        "block_index": payload["block_index"],
                        "task": payload["task"],
                        "algorithm": payload["algorithm"],
                        "seed": payload["seed"],
                        "feedback_modes": payload["feedback_modes"],
                        "error": "BlockWorkerError: %s" % type(exc).__name__,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    })
                    document["aggregate"] = aggregate_runs(
                        document.get("runs") or []
                    )
                    atomic_write_text(
                        output,
                        json.dumps(document, indent=2, allow_nan=False) + "\n",
                    )
                    print(
                        "[block %d/%d] worker failed %s|%s|%d" % (
                            payload["block_index"], len(blocks),
                            payload["task"], payload["algorithm"],
                            payload["seed"],
                        ),
                        flush=True,
                    )
                    continue
                retain_block(result)

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
