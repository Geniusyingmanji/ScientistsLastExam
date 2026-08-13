"""Adapter for the official OpenEvolve population/MAP-Elites implementation."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

from ..llm import LLMClient
from ..evaluate import INVALID_SCORE
from ..metric_visibility import load_full_metrics
from ..protocol import sha256_text
from ..spec import TaskSpec
from ..upstream_evaluator import write_configured_wrapper
from .common import (
    EvolveResult,
    TrajectoryRecorder,
    atomic_write_text,
    ensure_run_manifest,
    latest_numbered_directory,
    metrics_score,
    reconstruction_path,
    require_evaluation_budget,
    require_distribution,
    validate_feedback_mode,
    write_summary,
)

OPENEVOLVE_VERSION = "0.2.26"
OPENEVOLVE_COMMIT = "ad9c9c1769e55a776549715b5b48e13a84a93a30"


def _load_openevolve():
    try:
        from openevolve import Config, OpenEvolve
        from openevolve.config import LLMModelConfig
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "OpenEvolve requires the official `openevolve==%s` package and Python >=3.10. "
            "Install it with `python3.10 -m pip install openevolve==%s`."
            % (OPENEVOLVE_VERSION, OPENEVOLVE_VERSION)
        ) from exc
    distribution = require_distribution("openevolve", OPENEVOLVE_VERSION)
    return Config, OpenEvolve, LLMModelConfig, distribution


def _programs(controller) -> list[Any]:
    return sorted(
        controller.database.programs.values(),
        key=lambda p: (int(getattr(p, "iteration_found", 0) or 0), float(p.timestamp or 0.0)),
    )


def _run_async(coroutine):
    """Run an upstream coroutine from the synchronous public API."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    raise RuntimeError("openevolve backend must be called outside a running asyncio loop")


def openevolve(
    spec: TaskSpec,
    llm: LLMClient,
    budget: int = 10,
    timeout_s: float = 300.0,
    workdir: Optional[Path] = None,
    log_fn: Callable[[str], None] = print,
    seed: int = 0,
    resume: bool = False,
    feedback_mode: str = "normal",
) -> EvolveResult:
    # Upstream OpenEvolve always conditions its mutations on evaluator feedback.
    validate_feedback_mode(feedback_mode, ("normal",))
    if budget < 0:
        raise ValueError("budget must be non-negative")
    if budget > 0 and llm.config.wire != "chat":
        raise ValueError("official OpenEvolve 0.2.26 supports OpenAI-compatible chat wire only")
    Config, OpenEvolve, LLMModelConfig, distribution = _load_openevolve()

    workdir = Path(
        workdir
        or spec.task_dir / "runs" / ("openevolve_%s" % time.strftime("%Y%m%d_%H%M%S"))
    ).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    ensure_run_manifest(
        workdir, spec=spec, llm=llm, algorithm="openevolve", seed=seed,
        feedback_mode=feedback_mode, resume=resume,
        upstream={"name": "openevolve", "version": OPENEVOLVE_VERSION,
                  "commit": OPENEVOLVE_COMMIT},
    )
    upstream_dir = workdir / "upstream"
    upstream_dir.mkdir(parents=True, exist_ok=True)
    trajectory_path = workdir / "trajectory.jsonl"
    if trajectory_path.exists() and not resume:
        raise FileExistsError("workdir already contains a run; use --resume or a new --workdir")

    rebuild_path = reconstruction_path(trajectory_path)
    recorder = TrajectoryRecorder(
        rebuild_path,
        algorithm="openevolve",
        task_id=spec.task_id,
        seed=seed,
        budget=budget,
        feedback_mode=feedback_mode,
        resume=False,
    )

    config = Config()
    config.max_iterations = budget
    config.random_seed = seed
    # OpenEvolve's default 10,000-character cap discards a candidate *before* evaluation, so a
    # task whose solution is a long program is silently censored rather than scored. Measured on
    # QuantumErrorDecoder at budget 40: 29 of 40 iterations were dropped this way, leaving 12
    # evaluated programs and a best score that reads as a plateau but is a lower bound. Scale the
    # cap with the model's output allowance, since that is what actually bounds a generation.
    config.max_code_length = max(
        int(getattr(config, "max_code_length", 10000) or 10000),
        4 * int(llm.config.max_output_tokens),
    )
    config.database.random_seed = seed
    config.database.db_path = None
    config.evaluator.timeout = max(1, int(timeout_s))
    config.evaluator.parallel_evaluations = 1
    config.evaluator.cascade_evaluation = False
    config.checkpoint_interval = 1
    config.diff_based_evolution = False
    config.prompt.system_message = (
        "You are an expert computational scientist. Improve the candidate program for this "
        "task while preserving its required entrypoint and output contract.\n\n"
        + spec.agent_visible_text()
    )
    model = LLMModelConfig(
        name=llm.config.model,
        api_base=llm.config.base_url,
        api_key=llm.config.api_key or "DUMMY_API_KEY_FOR_LOCAL_GATEWAY",
        temperature=llm.config.temperature,
        max_tokens=llm.config.max_output_tokens,
        timeout=max(1, int(llm.config.timeout_seconds)),
        retries=3,
        retry_delay=2,
        random_seed=seed,
        reasoning_effort=llm.config.reasoning_effort,
    )
    config.llm.models = [model]
    config.llm.evaluator_models = [model]
    config.llm.api_base = llm.config.base_url
    config.llm.api_key = model.api_key

    evaluator_file = write_configured_wrapper(
        workdir / "upstream_evaluator.py", spec.task_id, timeout_s,
        full_metrics_dir=workdir / "trusted_full_metrics",
    )
    controller = OpenEvolve(
        initial_program_path=str(spec.initial_program_path),
        evaluation_file=str(evaluator_file),
        config=config,
        output_dir=str(upstream_dir),
    )
    checkpoint = latest_numbered_directory(upstream_dir / "checkpoints", "checkpoint_")
    checkpoint_arg = str(checkpoint) if resume and checkpoint is not None else None
    if resume and checkpoint_arg is None:
        raise FileNotFoundError("--resume requested but no OpenEvolve checkpoint exists")

    completed_iterations = 0
    if checkpoint is not None:
        try:
            completed_iterations = int(checkpoint.name.rsplit("_", 1)[1])
        except (IndexError, ValueError):
            completed_iterations = 0
    remaining_iterations = budget - completed_iterations if resume else budget
    if remaining_iterations < 0:
        raise ValueError("requested budget is smaller than the resumed checkpoint")
    started = time.monotonic()
    if remaining_iterations == 0 and checkpoint_arg is not None:
        controller.database.load(checkpoint_arg)
        best = controller.database.get_best_program()
    else:
        best = _run_async(
            controller.run(iterations=remaining_iterations, checkpoint_path=checkpoint_arg)
        )
    if best is None:
        raise RuntimeError("OpenEvolve returned no program")
    programs = _programs(controller)
    if not programs:
        raise RuntimeError("OpenEvolve database is empty")
    require_evaluation_budget("OpenEvolve", len(programs), budget)

    by_id = {p.id: p for p in programs}
    oracle_calls = 0
    best_raw = INVALID_SCORE
    baseline_score = None
    unevaluated = 0
    history: list[dict[str, Any]] = []
    # Recorded steps must stay contiguous from zero, so a skipped program cannot consume a step
    # index. Track the recorded position separately from the database position.
    step = 0
    for index, program in enumerate(programs):
        public_metrics = dict(program.metrics or {})
        try:
            metrics = load_full_metrics(
                workdir / "trusted_full_metrics", program.code, public_metrics
            )
        except FileNotFoundError:
            # OpenEvolve keeps a program in its database even when its own evaluator timed out,
            # recording {"error": 0.0, "timeout": true} from upstream. No trusted evaluation ran,
            # so no sidecar exists. Those upstream metrics must never enter scoring, but one
            # timed-out candidate must not destroy the whole run either: on a slow task this was
            # 5 of 11 programs and it aborted the adapter outright.
            unevaluated += 1
            continue
        score, valid = metrics_score(metrics)
        oracle_calls += 1
        improved = valid and score > best_raw
        if improved:
            best_raw = score
        if program.parent_id is None and baseline_score is None:
            baseline_score = score
        parent = by_id.get(program.parent_id)
        upstream_iteration = int(getattr(program, "iteration_found", index) or 0)
        recorder.record(
            step=step,
            oracle_calls=oracle_calls,
            budget_units=step + 1,
            program=program.code,
            metrics=metrics,
            parent_sha256=sha256_text(parent.code) if parent is not None else None,
            wall_seconds=(time.monotonic() - started) / max(1, len(programs)),
            accepted=improved,
            algorithm_metadata={"upstream_iteration": upstream_iteration},
        )
        history.append(
            {"iter": upstream_iteration, "score": score,
             "best": best_raw, "accepted": improved}
        )
        step += 1
    if oracle_calls == 0:
        raise RuntimeError(
            "no OpenEvolve program carries a trusted evaluation (%d of %d timed out upstream)"
            % (unevaluated, len(programs))
        )
    if baseline_score is None:
        baseline_score = metrics_score(programs[0].metrics or {})[0]

    summary = recorder.summary(
        baseline_score=baseline_score,
        extra={
            "upstream": {
                "name": "openevolve",
                "version": OPENEVOLVE_VERSION,
                "commit": OPENEVOLVE_COMMIT,
            },
            "installed_distribution": distribution,
            "accounting_note": "OpenEvolve 0.2.26 does not expose provider token usage; candidate/oracle trajectory is complete.",
        },
    )
    summary["llm"] = (
        {"usage_available": "no_calls", "calls": 0, "input_tokens": 0,
         "output_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0}
        if budget == 0 else
        {"usage_available": False, "calls": None, "input_tokens": None,
         "output_tokens": None, "total_tokens": None, "estimated_cost_usd": None}
    )
    summary["upstream_unevaluated_programs"] = unevaluated
    os.replace(str(rebuild_path), str(trajectory_path))
    atomic_write_text(workdir / "best_program.py", best.code)
    write_summary(workdir, summary)
    log_fn("[%s] OpenEvolve best=%.6f programs=%d scored=%d upstream_unevaluated=%d"
           % (spec.task_id, float(best_raw), len(programs), oracle_calls, unevaluated))
    return EvolveResult(
        task_id=spec.task_id,
        best_score=float(best_raw),
        baseline_score=float(baseline_score),
        best_program=best.code,
        history=history,
        accepted=sum(bool(row["accepted"]) for row in history[1:]),
        evaluated=oracle_calls,
        algorithm="openevolve",
        seed=seed,
        summary=summary,
    )
