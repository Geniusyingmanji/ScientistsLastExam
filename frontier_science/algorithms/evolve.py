"""Greedy single-incumbent full-file rewrite baseline.

Faithful to the Frontier-Engineering paradigm: keep the best runnable program, ask the
LLM to propose an improved full rewrite of the editable file, evaluate it with the frozen
oracle, accept on strict improvement of ``combined_score`` among valid candidates. The
agent only ever sees the task text, the current best program, and the returned metrics.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
from pathlib import Path
from typing import Callable, Optional

from ..evaluate import evaluate_candidate, INVALID_SCORE
from ..llm import LLMClient
from ..spec import TaskSpec
from ..protocol import TrajectoryEvent, append_event, load_trajectory, sha256_text, summarize_trajectory
from .common import (
    EvolveResult,
    PROMPT_FEEDBACK_SCOPE,
    atomic_write_text,
    ensure_run_manifest,
    restore_committed_trajectory,
)

SYSTEM_PROMPT = (
    "You are an expert computational scientist improving a Python program that solves a "
    "scientific optimization problem. You will be given the task, the current best program, "
    "and its measured metrics. Return ONE improved, complete, self-contained Python file. "
    "Keep the required entrypoint/signature and output contract intact. Optimize the reported "
    "combined_score. Respond with exactly one fenced ```python code block and nothing else."
)

_CODE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> Optional[str]:
    matches = _CODE_RE.findall(text or "")
    if matches:
        return max(matches, key=len).strip()
    stripped = (text or "").strip()
    # Fallback: looks like raw code (no prose) if it imports / defs early.
    if stripped and ("import " in stripped[:200] or "def " in stripped[:200]):
        return stripped
    return None


def _build_prompt(spec: TaskSpec, program: str, metrics: dict) -> str:
    shown = {k: metrics[k] for k in (
        "combined_score", "valid", "feasibility_rate", "constraint_violations",
        "raw_score", "error_message") if k in metrics}
    return (
        f"{spec.agent_visible_text()}\n\n"
        f"## Current best program (`{spec.candidate_destination}`)\n"
        f"```python\n{program}\n```\n\n"
        f"## Its measured metrics\n```json\n{json.dumps(shown, indent=2)}\n```\n\n"
        "Improve the program to increase `combined_score`. Return one complete "
        "```python``` file implementing the same entrypoint."
    )


def greedy_rewrite(
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
    if feedback_mode not in {"normal", "none", "shuffled"}:
        raise ValueError("feedback_mode must be normal, none, or shuffled")
    if budget < 0:
        raise ValueError("budget must be non-negative")
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    workdir = Path(workdir or (spec.task_dir / "runs" / time.strftime("%Y%m%d_%H%M%S"))).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    cand_path = workdir / Path(spec.candidate_destination).name
    trajectory_path = workdir / "trajectory.jsonl"
    checkpoint_path = workdir / "checkpoint.json"
    if not resume and (trajectory_path.exists() or checkpoint_path.exists()):
        raise FileExistsError("workdir already contains a run; use --resume or a new --workdir")
    ensure_run_manifest(
        workdir, spec=spec, llm=llm, algorithm="greedy_rewrite", seed=seed,
        feedback_mode=feedback_mode, resume=resume,
    )
    if resume and not (checkpoint_path.is_file() and trajectory_path.is_file()):
        raise FileNotFoundError("--resume requires checkpoint.json and trajectory.jsonl")

    # Seed with the initial baseline program.
    start_iter = 1
    run_started = time.monotonic()
    if resume and checkpoint_path.is_file() and trajectory_path.is_file():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint.get("task_id") != spec.task_id or int(checkpoint.get("seed", -1)) != seed:
            raise ValueError("checkpoint task/seed mismatch")
        baseline_src = spec.initial_program_path.read_text(encoding="utf-8")
        baseline_score = float(checkpoint["baseline_score"])
        best_score = float(checkpoint["best_score"])
        best_program = str(checkpoint["best_program"])
        if sha256_text(best_program) != checkpoint.get("best_sha256"):
            raise ValueError("checkpoint best program hash mismatch")
        best_metrics = dict(checkpoint["best_metrics"])
        start_iter = int(checkpoint["next_iter"])
        if budget + 1 < start_iter:
            raise ValueError("requested budget is smaller than the committed checkpoint")
        prior_events = restore_committed_trajectory(trajectory_path, start_iter)
        cumulative_offset = float(prior_events[-1]["cumulative_wall_seconds"])
        result = EvolveResult(spec.task_id, best_score, baseline_score, best_program,
                              algorithm="greedy_rewrite", seed=seed)
        result.evaluated = int(prior_events[-1]["oracle_calls"])
        result.accepted = sum(bool(e.get("accepted")) for e in prior_events[1:])
        log_fn(f"[{spec.task_id}] resume at iter={start_iter} best={best_score:.6f}")
    else:
        baseline_src = spec.initial_program_path.read_text(encoding="utf-8")
        cand_path.write_text(baseline_src, encoding="utf-8")
        eval_started = time.monotonic()
        metrics = evaluate_candidate(spec, cand_path, timeout_s=timeout_s)
        eval_wall = time.monotonic() - eval_started
        baseline_score = float(metrics.get("combined_score", INVALID_SCORE))
        best_score, best_program, best_metrics = baseline_score, baseline_src, metrics
        log_fn(f"[{spec.task_id}] baseline combined_score={baseline_score:.6f} valid={metrics.get('valid')}")
        result = EvolveResult(spec.task_id, best_score, baseline_score, best_program,
                              algorithm="greedy_rewrite", seed=seed)
        result.evaluated = 1
        append_event(trajectory_path, TrajectoryEvent(
            step=0, oracle_calls=1, score=baseline_score, best_score=baseline_score,
            valid=float(metrics.get("valid", 0.0)) >= 1.0, accepted=True,
            wall_seconds=eval_wall, cumulative_wall_seconds=eval_wall,
            candidate_sha256=sha256_text(baseline_src), parent_sha256=None,
            budget_units=1,
            metrics=metrics,
        ))
        cumulative_offset = 0.0

    def save_checkpoint(next_iter: int) -> None:
        atomic_write_text(checkpoint_path, json.dumps({
            "schema_version": 1, "algorithm": "greedy_rewrite", "task_id": spec.task_id,
            "seed": seed, "next_iter": next_iter, "baseline_score": baseline_score,
            "best_score": best_score, "best_metrics": best_metrics,
            "best_program": best_program, "best_sha256": sha256_text(best_program),
        }, indent=2, allow_nan=False) + "\n")
        atomic_write_text(workdir / "best_program.py", best_program)

    save_checkpoint(start_iter)

    for it in range(start_iter, budget + 1):
        step_started = time.monotonic()
        parent_sha = sha256_text(best_program)
        prompt_metrics = best_metrics
        if feedback_mode == "none":
            prompt_metrics = {}
        elif feedback_mode == "shuffled":
            shuffled = load_trajectory(trajectory_path)
            prior = [e.get("metrics", {}) for e in shuffled if int(e.get("step", 0)) < it]
            prompt_metrics = random.choice(prior) if prior else best_metrics
        try:
            reply = llm.complete(_build_prompt(spec, best_program, prompt_metrics), system=SYSTEM_PROMPT)
            llm_usage = dict(getattr(llm, "last_usage", {}) or {})
            llm_error = None
        except Exception as exc:  # noqa: BLE001
            log_fn(f"[{spec.task_id}] iter {it}: LLM error: {exc}")
            reply = ""
            llm_usage = {}
            llm_error = "LLM error: %s" % exc
        code = extract_code(reply)
        if not code:
            log_fn(f"[{spec.task_id}] iter {it}: no code block parsed")
            error = llm_error or "no_code"
            m = {"combined_score": INVALID_SCORE, "valid": 0.0, "error_message": error}
            score, valid, accepted = INVALID_SCORE, False, False
            candidate_sha = ""
        else:
            cand_path.write_text(code, encoding="utf-8")
            m = evaluate_candidate(spec, cand_path, timeout_s=timeout_s)
            result.evaluated += 1
            score = float(m.get("combined_score", INVALID_SCORE))
            valid = float(m.get("valid", 0.0)) >= 1.0
            accepted = bool(valid and score > best_score)
            candidate_sha = sha256_text(code)
            error = m.get("error_message")
        if accepted:
            best_score, best_program, best_metrics = score, code, m
            result.best_score, result.best_program = best_score, best_program
            result.accepted += 1
        entry = {"iter": it, "score": score, "best": best_score, "accepted": accepted,
                 "metrics": {k: m.get(k) for k in ("combined_score", "valid", "raw_score", "error_message")}}
        result.history.append(entry)
        step_wall = time.monotonic() - step_started
        append_event(trajectory_path, TrajectoryEvent(
            step=it, oracle_calls=result.evaluated, score=score, best_score=best_score,
            valid=valid, accepted=accepted, wall_seconds=step_wall,
            cumulative_wall_seconds=cumulative_offset + (time.monotonic() - run_started),
            candidate_sha256=candidate_sha, parent_sha256=parent_sha,
            budget_units=it + 1,
            metrics=m, llm=llm_usage,
            error=error,
        ))
        save_checkpoint(it + 1)
        log_fn(f"[{spec.task_id}] iter {it}: score={score:.6f} best={best_score:.6f} "
               f"{'ACCEPT' if accepted else 'reject'}")

    atomic_write_text(workdir / "best_program.py", best_program)
    result.summary = summarize_trajectory(load_trajectory(trajectory_path), budget=budget + 1)
    result.summary.update({"algorithm": "greedy_rewrite", "task_id": spec.task_id,
                           "seed": seed, "baseline_score": baseline_score,
                           "budget": budget, "feedback_mode": feedback_mode,
                           "feedback_scope": PROMPT_FEEDBACK_SCOPE})
    atomic_write_text(
        workdir / "summary.json",
        json.dumps(result.summary, indent=2, allow_nan=False) + "\n",
    )
    log_fn(f"[{spec.task_id}] DONE baseline={baseline_score:.6f} -> best={best_score:.6f} "
           f"({result.accepted}/{budget} accepted)  out={workdir}")
    return result


# Backwards-compatible import; the public name no longer claims OpenEvolve semantics.
evolve = greedy_rewrite
