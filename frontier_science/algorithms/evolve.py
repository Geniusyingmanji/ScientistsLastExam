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
from typing import Any, Callable, Optional

from ..evaluate import evaluate_candidate, INVALID_SCORE
from ..llm import LLMClient
from ..metric_visibility import score_only_metrics, search_visible_metrics
from ..spec import TaskSpec
from ..protocol import TrajectoryEvent, append_event, load_trajectory, sha256_text, summarize_trajectory
from .common import (
    EvolveResult,
    atomic_write_text,
    ensure_run_manifest,
    feedback_scope,
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

GREEDY_FEEDBACK_MODES = {
    "normal",
    "none",
    "shuffled",
    "score_only",
    "delayed_replay",
    "selection_blind",
}


class LLMInfrastructureError(RuntimeError):
    """Provider/transport failure that must not become a candidate outcome."""


class EvaluatorInfrastructureError(RuntimeError):
    """Trusted evaluator failure that must not become a candidate outcome."""


def extract_code(text: str) -> Optional[str]:
    matches = _CODE_RE.findall(text or "")
    if matches:
        return max(matches, key=len).strip()
    stripped = (text or "").strip()
    # Fallback: looks like raw code (no prose) if it imports / defs early.
    if stripped and ("import " in stripped[:200] or "def " in stripped[:200]):
        return stripped
    return None


def _build_prompt(
    spec: TaskSpec,
    program: str,
    metrics: dict,
    *,
    proposal_slot: int | None = None,
    proposal_budget: int | None = None,
) -> str:
    shown = search_visible_metrics(metrics)
    slot = ""
    if proposal_slot is not None and proposal_budget is not None:
        slot = (
            "## Preregistered proposal slot\n"
            f"This is proposal {proposal_slot} of {proposal_budget}. Explore a concrete "
            "implementation improvement appropriate to this slot.\n\n"
        )
    return (
        f"{spec.agent_visible_text()}\n\n"
        f"{slot}"
        f"## Parent program (`{spec.candidate_destination}`)\n"
        f"```python\n{program}\n```\n\n"
        f"## Its measured metrics\n```json\n{json.dumps(shown, indent=2)}\n```\n\n"
        "Propose a complete program intended to increase `combined_score`. Return one complete "
        "```python``` file implementing the same entrypoint."
    )


def _validate_pending_proposal(
    pending: dict[str, Any], *, step: int, prompt: str,
    parent_sha256: str, prompt_source_step: int,
    feedback_released_through_step: int, prompt_metrics_rendered: str,
) -> tuple[Optional[str], dict[str, Any], float]:
    """Validate and return a write-ahead provider result for evaluator retry."""
    expected = {
        "schema_version": 1,
        "step": step,
        "parent_sha256": parent_sha256,
        "prompt_source_step": prompt_source_step,
        "feedback_released_through_step": feedback_released_through_step,
        "prompt_sha256": sha256_text(prompt),
        "prompt_metrics_sha256": sha256_text(prompt_metrics_rendered),
        "system_prompt_sha256": sha256_text(SYSTEM_PROMPT),
    }
    if not isinstance(pending, dict) or any(
        pending.get(key) != value for key, value in expected.items()
    ):
        raise ValueError("pending proposal lineage differs from reconstructed prompt")
    status = pending.get("parse_status")
    program = pending.get("program")
    candidate_sha = pending.get("candidate_sha256")
    if status == "parsed_code":
        if not (
            isinstance(program, str)
            and bool(program)
            and candidate_sha == sha256_text(program)
        ):
            raise ValueError("pending proposal source binding differs")
    elif status == "no_code":
        if program is not None or candidate_sha != "":
            raise ValueError("pending no-code proposal unexpectedly retains source")
    else:
        raise ValueError("pending proposal parse status is invalid")
    response_sha = pending.get("response_sha256")
    response_bytes = pending.get("response_utf8_bytes")
    response = pending.get("response")
    usage = pending.get("llm_usage")
    prefix_wall = pending.get("pre_evaluation_wall_seconds")
    if not (
        isinstance(response, str)
        and response_sha == sha256_text(response)
        and len(response_sha) == 64
        and all(character in "0123456789abcdef" for character in response_sha)
        and isinstance(response_bytes, int)
        and not isinstance(response_bytes, bool)
        and response_bytes >= 0
        and response_bytes == len(response.encode("utf-8"))
        and isinstance(usage, dict)
        and isinstance(prefix_wall, (int, float))
        and not isinstance(prefix_wall, bool)
        and float(prefix_wall) >= 0.0
    ):
        raise ValueError("pending proposal accounting is invalid")
    if extract_code(response) != program:
        raise ValueError("pending proposal parse result differs from response")
    return program, dict(usage), float(prefix_wall)


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
    if feedback_mode not in GREEDY_FEEDBACK_MODES:
        raise ValueError(
            "feedback_mode must be one of: %s" % ", ".join(sorted(GREEDY_FEEDBACK_MODES))
        )
    if budget < 0:
        raise ValueError("budget must be non-negative")
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    workdir = Path(workdir or (spec.task_dir / "runs" / time.strftime("%Y%m%d_%H%M%S"))).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    cand_path = workdir / Path(spec.candidate_destination).name
    trajectory_path = workdir / "trajectory.jsonl"
    checkpoint_path = workdir / "checkpoint.json"
    manifest_path = workdir / "run_manifest.json"
    if not resume and (trajectory_path.exists() or checkpoint_path.exists()):
        raise FileExistsError("workdir already contains a run; use --resume or a new --workdir")
    full_resume = bool(
        resume and checkpoint_path.is_file() and trajectory_path.is_file()
    )
    baseline_retry = bool(
        resume and manifest_path.is_file()
        and not checkpoint_path.exists() and not trajectory_path.exists()
    )
    ensure_run_manifest(
        workdir, spec=spec, llm=llm, algorithm="greedy_rewrite", seed=seed,
        feedback_mode=feedback_mode, resume=resume,
    )
    if resume and not (full_resume or baseline_retry):
        raise FileNotFoundError("--resume requires checkpoint.json and trajectory.jsonl")

    # Seed with the initial baseline program.
    start_iter = 1
    pending_proposal: dict[str, Any] | None = None
    if full_resume:
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint.get("task_id") != spec.task_id or int(checkpoint.get("seed", -1)) != seed:
            raise ValueError("checkpoint task/seed mismatch")
        baseline_src = spec.initial_program_path.read_text(encoding="utf-8")
        baseline_score = float(checkpoint["baseline_score"])
        baseline_metrics = search_visible_metrics(dict(
            checkpoint.get("baseline_metrics", checkpoint["best_metrics"])
        ))
        best_score = float(checkpoint["best_score"])
        best_program = str(checkpoint["best_program"])
        if sha256_text(best_program) != checkpoint.get("best_sha256"):
            raise ValueError("checkpoint best program hash mismatch")
        if "best_source_step" not in checkpoint:
            raise ValueError("checkpoint is missing best_source_step lineage")
        best_source_step = int(checkpoint["best_source_step"])
        # Checkpoints are search state and therefore contain only search-visible metrics.
        best_metrics = search_visible_metrics(dict(checkpoint["best_metrics"]))
        if feedback_mode in {"selection_blind", "delayed_replay"}:
            if "baseline_metrics" not in checkpoint:
                raise ValueError(
                    "%s checkpoint is missing frozen baseline metrics" % feedback_mode
                )
            if "evaluated_candidates" not in checkpoint:
                raise ValueError(
                    "%s checkpoint is missing evaluated candidate state" % feedback_mode
                )
        evaluated_candidates = list(checkpoint.get("evaluated_candidates") or [])
        pending_value = checkpoint.get("pending_proposal")
        if pending_value is not None and not isinstance(pending_value, dict):
            raise ValueError("checkpoint pending proposal is not an object")
        pending_proposal = pending_value
        if not evaluated_candidates:
            evaluated_candidates = [{
                "step": 0,
                "program": baseline_src,
                "sha256": sha256_text(baseline_src),
                "score": baseline_score,
                "valid": True,
                "metrics": baseline_metrics,
            }]
        start_iter = int(checkpoint["next_iter"])
        if budget + 1 < start_iter:
            raise ValueError("requested budget is smaller than the committed checkpoint")
        prior_events = restore_committed_trajectory(trajectory_path, start_iter)
        active_wall = float(prior_events[-1]["cumulative_wall_seconds"])
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
        if metrics.get("infrastructure_failure"):
            raise EvaluatorInfrastructureError(
                "baseline trusted evaluator infrastructure failure"
            )
        if float(metrics.get("valid", 0.0)) < 1.0:
            raise EvaluatorInfrastructureError(
                "frozen baseline is invalid under the trusted evaluator"
            )
        eval_wall = time.monotonic() - eval_started
        baseline_score = float(metrics.get("combined_score", INVALID_SCORE))
        best_score, best_program = baseline_score, baseline_src
        best_source_step = 0
        best_metrics = search_visible_metrics(metrics)
        baseline_metrics = dict(best_metrics)
        evaluated_candidates = [{
            "step": 0,
            "program": baseline_src,
            "sha256": sha256_text(baseline_src),
            "score": baseline_score,
            "valid": float(metrics.get("valid", 0.0)) >= 1.0,
            "metrics": baseline_metrics,
        }]
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
        active_wall = eval_wall

    def save_checkpoint(next_iter: int) -> None:
        atomic_write_text(checkpoint_path, json.dumps({
            "schema_version": 1, "algorithm": "greedy_rewrite", "task_id": spec.task_id,
            "seed": seed, "next_iter": next_iter, "baseline_score": baseline_score,
            "baseline_metrics": baseline_metrics,
            "best_score": best_score, "best_metrics": best_metrics,
            "best_program": best_program, "best_sha256": sha256_text(best_program),
            "best_source_step": best_source_step,
            "evaluated_candidates": evaluated_candidates,
            "pending_proposal": pending_proposal,
        }, indent=2, allow_nan=False) + "\n")
        atomic_write_text(workdir / "best_program.py", best_program)

    save_checkpoint(start_iter)

    for it in range(start_iter, budget + 1):
        step_started = time.monotonic()
        prompt_program = best_program
        prompt_metrics = best_metrics
        prompt_source_step = best_source_step
        feedback_released_through_step = it - 1
        if feedback_mode == "none":
            prompt_metrics = {}
        elif feedback_mode == "score_only":
            prompt_metrics = score_only_metrics(best_metrics)
        elif feedback_mode == "shuffled":
            shuffled = load_trajectory(trajectory_path)
            prior = [e.get("metrics", {}) for e in shuffled if int(e.get("step", 0)) < it]
            prompt_metrics = random.choice(prior) if prior else best_metrics
        elif feedback_mode == "delayed_replay":
            feedback_released_through_step = max(0, it - 2)
            eligible = [
                row for row in evaluated_candidates
                if int(row["step"]) <= feedback_released_through_step
                and bool(row.get("valid"))
            ]
            if not eligible:
                raise RuntimeError("delayed_replay has no valid released parent")
            released_best = max(
                eligible,
                key=lambda row: (float(row["score"]), -int(row["step"])),
            )
            prompt_program = str(released_best["program"])
            prompt_metrics = dict(released_best["metrics"])
            prompt_source_step = int(released_best["step"])
        elif feedback_mode == "selection_blind":
            prompt_program = baseline_src
            prompt_metrics = baseline_metrics
            prompt_source_step = 0
            feedback_released_through_step = 0
        parent_sha = sha256_text(prompt_program)
        prompt_metrics_rendered = json.dumps(
            search_visible_metrics(prompt_metrics), indent=2
        )
        prompt = _build_prompt(
            spec,
            prompt_program,
            prompt_metrics,
            proposal_slot=it,
            proposal_budget=budget,
        )
        if pending_proposal is None:
            try:
                reply = llm.complete(
                    prompt,
                    system=SYSTEM_PROMPT,
                )
                llm_usage = dict(getattr(llm, "last_usage", {}) or {})
            except Exception as exc:  # noqa: BLE001
                log_fn(
                    f"[{spec.task_id}] iter {it}: provider infrastructure failure"
                )
                # The provider client has already exhausted its transport retries.
                # Do not charge a proposal slot or append a scientific trajectory
                # event: the outer batch retains this infrastructure attempt and
                # --resume retries the same checkpoint-owned proposal index.
                raise LLMInfrastructureError(
                    "provider request failed after transport retries"
                ) from exc
            code = extract_code(reply)
            pending_proposal = {
                "schema_version": 1,
                "step": it,
                "parse_status": "parsed_code" if code else "no_code",
                "program": code,
                "candidate_sha256": sha256_text(code) if code else "",
                "response_sha256": sha256_text(reply),
                "response_utf8_bytes": len(reply.encode("utf-8")),
                "response": reply,
                "parent_sha256": parent_sha,
                "prompt_source_step": prompt_source_step,
                "feedback_released_through_step": (
                    feedback_released_through_step
                ),
                "prompt_sha256": sha256_text(prompt),
                "prompt_metrics_sha256": sha256_text(prompt_metrics_rendered),
                "system_prompt_sha256": sha256_text(SYSTEM_PROMPT),
                "llm_usage": llm_usage,
                "pre_evaluation_wall_seconds": time.monotonic() - step_started,
            }
            # Commit the provider draw before evaluating it. An evaluator
            # outage then replays this exact source/result instead of drawing a
            # replacement proposal from the model.
            save_checkpoint(it)
        code, llm_usage, pre_evaluation_wall = _validate_pending_proposal(
            pending_proposal,
            step=it,
            prompt=prompt,
            parent_sha256=parent_sha,
            prompt_source_step=prompt_source_step,
            feedback_released_through_step=feedback_released_through_step,
            prompt_metrics_rendered=prompt_metrics_rendered,
        )
        evaluation_started = time.monotonic()
        if not code:
            log_fn(f"[{spec.task_id}] iter {it}: no code block parsed")
            error = "no_code"
            m = {"combined_score": INVALID_SCORE, "valid": 0.0, "error_message": error}
            score, valid, accepted = INVALID_SCORE, False, False
            candidate_sha = ""
        else:
            cand_path.write_text(code, encoding="utf-8")
            m = evaluate_candidate(spec, cand_path, timeout_s=timeout_s)
            if m.get("infrastructure_failure"):
                raise EvaluatorInfrastructureError(
                    "candidate trusted evaluator infrastructure failure"
                )
            result.evaluated += 1
            score = float(m.get("combined_score", INVALID_SCORE))
            valid = float(m.get("valid", 0.0)) >= 1.0
            accepted = bool(valid and score > best_score)
            candidate_sha = sha256_text(code)
            error = m.get("error_message")
        # The provider result is now a terminal candidate outcome. Keep the
        # on-disk pending record until the event and next checkpoint commit.
        pending_proposal = None
        if code:
            evaluated_candidates.append({
                "step": it,
                "program": code,
                "sha256": candidate_sha,
                "score": score,
                "valid": valid,
                "metrics": search_visible_metrics(m),
            })
        if accepted:
            best_score, best_program = score, code
            best_source_step = it
            best_metrics = search_visible_metrics(m)
            result.best_score, result.best_program = best_score, best_program
            result.accepted += 1
        entry = {"iter": it, "score": score, "best": best_score, "accepted": accepted,
                 "metrics": {k: m.get(k) for k in ("combined_score", "valid", "raw_score", "error_message")}}
        result.history.append(entry)
        step_wall = pre_evaluation_wall + (time.monotonic() - evaluation_started)
        active_wall += step_wall
        append_event(trajectory_path, TrajectoryEvent(
            step=it, oracle_calls=result.evaluated, score=score, best_score=best_score,
            valid=valid, accepted=accepted, wall_seconds=step_wall,
            cumulative_wall_seconds=active_wall,
            candidate_sha256=candidate_sha, parent_sha256=parent_sha,
            budget_units=it + 1,
            metrics=m, llm=llm_usage,
            error=error,
            algorithm_metadata={
                "selection_policy": (
                    "offline_best_of_open_loop_batch"
                    if feedback_mode == "selection_blind"
                    else "delayed_online_parent_offline_final_best"
                    if feedback_mode == "delayed_replay"
                    else "online_incumbent"
                ),
                "accepted_semantics": (
                    "offline_best_update"
                    if feedback_mode == "selection_blind"
                    else "observer_best_update_not_immediate_parent_release"
                    if feedback_mode == "delayed_replay"
                    else "online_incumbent_update"
                ),
                "proposal_slot": it,
                "prompt_source_step": prompt_source_step,
                "feedback_released_through_step": feedback_released_through_step,
                "prompt_sha256": sha256_text(prompt),
                "prompt_utf8_bytes": len(prompt.encode("utf-8")),
                "prompt_program_utf8_bytes": len(prompt_program.encode("utf-8")),
                "prompt_metrics_sha256": sha256_text(prompt_metrics_rendered),
                "prompt_metrics_utf8_bytes": len(prompt_metrics_rendered.encode("utf-8")),
                "prompt_metric_keys": ",".join(sorted(search_visible_metrics(prompt_metrics))),
            },
        ))
        save_checkpoint(it + 1)
        log_fn(f"[{spec.task_id}] iter {it}: score={score:.6f} best={best_score:.6f} "
               f"{'ACCEPT' if accepted else 'reject'}")

    atomic_write_text(workdir / "best_program.py", best_program)
    result.summary = summarize_trajectory(load_trajectory(trajectory_path), budget=budget + 1)
    result.summary.update({"algorithm": "greedy_rewrite", "task_id": spec.task_id,
                           "seed": seed, "baseline_score": baseline_score,
                           "budget": budget, "feedback_mode": feedback_mode,
                           "feedback_scope": feedback_scope(feedback_mode),
                           "selection_policy": (
                               "offline_best_of_open_loop_batch"
                               if feedback_mode == "selection_blind"
                               else "delayed_online_parent_offline_final_best"
                               if feedback_mode == "delayed_replay"
                               else "online_incumbent"
                           )})
    atomic_write_text(
        workdir / "summary.json",
        json.dumps(result.summary, indent=2, allow_nan=False) + "\n",
    )
    log_fn(f"[{spec.task_id}] DONE baseline={baseline_score:.6f} -> best={best_score:.6f} "
           f"({result.accepted}/{budget} accepted)  out={workdir}")
    return result


# Backwards-compatible import; the public name no longer claims OpenEvolve semantics.
evolve = greedy_rewrite
