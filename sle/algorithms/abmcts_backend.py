"""Official TreeQuest AB-MCTS-A adapter.

TreeQuest owns parent selection and tree updates.  Frontier-Science owns prompting,
secure oracle evaluation, trajectory accounting, and reproducible artifacts.
"""

from __future__ import annotations

import json
import os
import pickle
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from ..evaluate import INVALID_SCORE, evaluate_candidate, resolve_trusted_runtime
from ..llm import LLMClient
from ..metric_visibility import search_visible_metrics
from ..protocol import sha256_text
from ..spec import TaskSpec
from .common import (
    EvolveResult,
    TrajectoryRecorder,
    atomic_write_text,
    ensure_run_manifest,
    metrics_score,
    require_distribution,
    restore_committed_trajectory,
    validate_feedback_mode,
    write_summary,
)
from .evolve import SYSTEM_PROMPT, _build_prompt, extract_code

TREEQUEST_VERSION = "0.3.2"
TREEQUEST_COMMIT = "96047d712d66bbbf4dcc86dcd3e2eaab98c35f83"


@dataclass(frozen=True)
class ProgramState:
    code: str
    metrics: dict[str, Any]
    combined_score: float


def _load_treequest():
    try:
        import treequest as tq
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "AB-MCTS requires the official TreeQuest package (commit %s; Python >=3.11). "
            "Install it with `python3.11 -m pip install treequest==0.3.2`." % TREEQUEST_COMMIT[:12]
        ) from exc
    distribution = require_distribution("treequest", TREEQUEST_VERSION)
    return tq, distribution


def _bounded_reward(score: float, valid: bool) -> float:
    if not valid:
        return 0.0
    # Certified clipped tasks already use [0,1].  This transform also keeps
    # uncapped flagship scores admissible to TreeQuest without changing raw ranking.
    if 0.0 <= score <= 1.0:
        return score
    return 0.5 + 0.5 * score / (1.0 + abs(score))


def abmcts(
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
    validate_feedback_mode(feedback_mode, ("normal", "none", "shuffled"))
    if budget < 0:
        raise ValueError("budget must be non-negative")
    tq, distribution = _load_treequest()
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)

    workdir = Path(
        workdir or spec.task_dir / "runs" / ("abmcts_%s" % time.strftime("%Y%m%d_%H%M%S"))
    ).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    trusted_runtime = resolve_trusted_runtime(spec.task_dir)
    ensure_run_manifest(
        workdir, spec=spec, llm=llm, algorithm="abmcts", seed=seed,
        feedback_mode=feedback_mode, resume=resume,
        upstream={"name": "treequest", "version": TREEQUEST_VERSION,
                  "commit": TREEQUEST_COMMIT},
        trusted_runtime=trusted_runtime,
    )
    candidate_path = workdir / Path(spec.candidate_destination).name
    checkpoint_path = workdir / "checkpoint.pkl"
    trajectory_path = workdir / "trajectory.jsonl"
    if not resume and (trajectory_path.exists() or checkpoint_path.exists()):
        raise FileExistsError("workdir already contains a run; use --resume or a new --workdir")
    if resume and not (checkpoint_path.is_file() and trajectory_path.is_file()):
        raise FileNotFoundError("--resume requires checkpoint.pkl and trajectory.jsonl")
    baseline_code = spec.initial_program_path.read_text(encoding="utf-8")

    if resume and checkpoint_path.is_file():
        with checkpoint_path.open("rb") as handle:
            checkpoint = pickle.load(handle)
        metadata = checkpoint["metadata"]
        if metadata.get("task_id") != spec.task_id or int(metadata.get("seed", -1)) != seed:
            raise ValueError("checkpoint task/seed mismatch")
        algo = checkpoint["algorithm"]
        search_tree = checkpoint["search_tree"]
        states: list[ProgramState] = checkpoint["states"]
        start_step = int(metadata["next_step"])
        committed_events = restore_committed_trajectory(trajectory_path, start_step)
        baseline_score = float(metadata["baseline_score"])
        oracle_calls = int(metadata["oracle_calls"])
        best_state = max(states, key=lambda state: state.combined_score)
        log_fn("[%s] resume AB-MCTS at step=%d" % (spec.task_id, start_step))
    else:
        committed_events = []

    recorder = TrajectoryRecorder(
        trajectory_path,
        algorithm="abmcts",
        task_id=spec.task_id,
        seed=seed,
        budget=budget,
        feedback_mode=feedback_mode,
        resume=resume,
    )
    if resume:
        recorder.events = committed_events
        recorder.cumulative_offset = float(committed_events[-1]["cumulative_wall_seconds"])

    if not resume:
        candidate_path.write_text(baseline_code, encoding="utf-8")
        started = time.monotonic()
        baseline_metrics = evaluate_candidate(
            spec, candidate_path, timeout_s=timeout_s,
            trusted_runtime=trusted_runtime,
        )
        baseline_score, baseline_valid = metrics_score(baseline_metrics)
        # TreeQuest search state must never contain evaluator-only science metrics.
        baseline_state = ProgramState(
            baseline_code, search_visible_metrics(baseline_metrics), baseline_score
        )
        best_state = baseline_state
        states = [baseline_state]
        oracle_calls = 1
        recorder.record(
            step=0,
            oracle_calls=oracle_calls,
            program=baseline_code,
            metrics=baseline_metrics,
            parent_sha256=None,
            budget_units=1,
            wall_seconds=time.monotonic() - started,
            accepted=baseline_valid,
        )
        algo = tq.ABMCTSA()
        search_tree = algo.init_tree()
        # TreeQuest represents the search root as an unscored sentinel.  Tell it
        # the evaluated baseline once so every later trial has a real parent.
        search_tree, baseline_trial = algo.ask(search_tree, ["baseline"])
        search_tree = algo.tell(
            search_tree,
            baseline_trial.trial_id,
            (baseline_state, _bounded_reward(baseline_score, baseline_valid)),
        )
        start_step = 1
        log_fn(
            "[%s] AB-MCTS baseline combined_score=%.6f valid=%s"
            % (spec.task_id, baseline_score, baseline_valid)
        )

    def save_checkpoint(next_step: int) -> None:
        metadata = {
            "schema_version": 1,
            "algorithm": "abmcts",
            "upstream": {"name": "treequest", "version": TREEQUEST_VERSION,
                         "commit": TREEQUEST_COMMIT},
            "task_id": spec.task_id,
            "seed": seed,
            "next_step": next_step,
            "oracle_calls": oracle_calls,
            "baseline_score": baseline_score,
        }
        temporary_checkpoint = checkpoint_path.with_name(".%s.tmp" % checkpoint_path.name)
        with temporary_checkpoint.open("wb") as handle:
            pickle.dump({
                "algorithm": algo,
                "search_tree": search_tree,
                "states": states,
                "metadata": metadata,
            }, handle)
        os.replace(str(temporary_checkpoint), str(checkpoint_path))
        # Human-readable mirror; recovery trusts only the atomic pickle above.
        atomic_write_text(
            workdir / "checkpoint.json", json.dumps(metadata, indent=2) + "\n"
        )

    save_checkpoint(start_step)
    history: list[dict[str, Any]] = []
    accepted = sum(bool(e.get("accepted")) for e in recorder.events[1:])

    for step in range(start_step, budget + 1):
        step_started = time.monotonic()
        search_tree, trial = algo.ask(search_tree, ["rewrite"])
        parent_state = trial.parent_state or states[0]
        parent_metrics = parent_state.metrics
        if feedback_mode == "none":
            parent_metrics = {}
        elif feedback_mode == "shuffled":
            parent_metrics = random.choice(states).metrics

        error: Optional[str] = None
        code = ""
        llm_usage: dict[str, Any] = {}
        try:
            reply = llm.complete(
                _build_prompt(spec, parent_state.code, parent_metrics), system=SYSTEM_PROMPT
            )
            llm_usage = dict(getattr(llm, "last_usage", {}) or {})
            code = extract_code(reply) or ""
            if not code:
                error = "no_code"
        except Exception as exc:  # noqa: BLE001
            error = "LLM error: %s" % exc

        if code:
            candidate_path.write_text(code, encoding="utf-8")
            metrics = evaluate_candidate(
                spec, candidate_path, timeout_s=timeout_s,
                trusted_runtime=trusted_runtime,
            )
            oracle_calls += 1
        else:
            code = parent_state.code
            metrics = {
                "combined_score": INVALID_SCORE,
                "valid": 0.0,
                "error_message": error or "no_code",
            }
        score, valid = metrics_score(metrics)
        child = ProgramState(code, search_visible_metrics(metrics), score)
        search_tree = algo.tell(
            search_tree,
            trial.trial_id,
            (child, _bounded_reward(score, valid)),
        )
        states.append(child)
        improved = bool(valid and score > best_state.combined_score)
        if improved:
            best_state = child
            accepted += 1
        recorder.record(
            step=step,
            oracle_calls=oracle_calls,
            program=code,
            metrics=metrics,
            parent_sha256=sha256_text(parent_state.code),
            wall_seconds=time.monotonic() - step_started,
            budget_units=step + 1,
            accepted=improved,
            llm=llm_usage,
            error=error,
        )
        history.append(
            {"iter": step, "score": score, "best": best_state.combined_score, "accepted": improved}
        )
        save_checkpoint(step + 1)
        log_fn(
            "[%s] AB-MCTS step %d: score=%.6f best=%.6f"
            % (spec.task_id, step, score, best_state.combined_score)
        )

    atomic_write_text(workdir / "best_program.py", best_state.code)
    summary = recorder.summary(
        baseline_score=baseline_score,
        extra={
            "upstream": {"name": "treequest", "version": TREEQUEST_VERSION,
                         "commit": TREEQUEST_COMMIT},
            "installed_distribution": distribution,
        },
    )
    write_summary(workdir, summary)
    return EvolveResult(
        task_id=spec.task_id,
        best_score=best_state.combined_score,
        baseline_score=baseline_score,
        best_program=best_state.code,
        history=history,
        accepted=accepted,
        evaluated=oracle_calls,
        algorithm="abmcts",
        seed=seed,
        summary=summary,
    )
