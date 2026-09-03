"""Greedy single-incumbent full-file rewrite baseline.

Faithful to the Frontier-Engineering paradigm: keep the best runnable program, ask the
LLM to propose an improved full rewrite of the editable file, evaluate it with the frozen
oracle, accept on strict improvement of ``combined_score`` among valid candidates. The
agent only ever sees the task text, the current best program, and the returned metrics.
"""

from __future__ import annotations

import json
import math
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Callable, Optional

from ..evaluate import evaluate_candidate, INVALID_SCORE
from ..evaluation_ledger import EvaluationLedger, RunLease
from ..llm import LLMClient
from ..metric_visibility import score_only_metrics, search_visible_metrics
from ..spec import TaskSpec
from ..protocol import TrajectoryEvent, append_event, load_trajectory, sha256_text, summarize_trajectory
from ..sentinels import SentinelLedger
from .common import (
    EvolveResult,
    atomic_write_text,
    ensure_run_manifest,
    feedback_scope,
    restore_committed_trajectory,
    runtime_source_sha256,
    task_contract_sha256,
    task_package_sha256,
)

SYSTEM_PROMPT = (
    "You are an expert computational scientist improving a Python program that solves a "
    "scientific optimization problem. You will be given the task, the current best program, "
    "and its measured metrics. Return ONE improved, complete, self-contained Python file. "
    "Keep the required entrypoint/signature and output contract intact. Optimize the reported "
    "combined_score. Respond with exactly one fenced ```python code block and nothing else."
)
SIGNED_SYSTEM_PROMPT = (
    "You are an expert computational scientist improving a Python program that solves a "
    "scientific optimization problem. You will be given the task, the current best program, "
    "its measured metrics, and the remaining active-time horizon. Return ONE improved, "
    "complete, self-contained Python file followed by ONE signed decision JSON block. Keep "
    "the required entrypoint/signature and output contract intact. Do not include prose "
    "outside the two required fenced blocks."
)

_CODE_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
# A stream that hits max_output_tokens often opens the fence and never closes it.
_UNCLOSED_CODE_RE = re.compile(r"```(?:python|py)?\s*\n(.*)\Z", re.DOTALL | re.IGNORECASE)
_REPLY_RETAIN_BYTES = 512_000
_DECISION_RE = re.compile(r"```decision\s*\n(.*?)```", re.DOTALL)
_SIGNED_RESPONSE_RE = re.compile(
    r"\A\s*```(?:python)?\s*\n(.*?)```\s*"
    r"```decision\s*\n(.*?)```\s*\Z",
    re.DOTALL,
)
SIGNED_DECISIONS = {"continue", "commit", "abstain"}

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
    unclosed = _UNCLOSED_CODE_RE.search(text or "")
    if unclosed:
        body = unclosed.group(1).strip()
        if body and ("import " in body[:400] or "def " in body[:4000]):
            return body
    stripped = (text or "").strip()
    # Fallback: looks like raw code (no prose) if it imports / defs early.
    if stripped and ("import " in stripped[:200] or "def " in stripped[:200]):
        return stripped
    return None


def extract_signed_decision(text: str) -> Optional[dict[str, Any]]:
    matches = _DECISION_RE.findall(text or "")
    if len(matches) != 1:
        return None
    try:
        value = json.loads(matches[0])
    except ValueError:
        return None
    if not isinstance(value, dict) or set(value) != {"action", "rationale"}:
        return None
    action = value.get("action")
    rationale = value.get("rationale")
    if action not in SIGNED_DECISIONS or not isinstance(rationale, str):
        return None
    if not rationale.strip() or len(rationale.encode("utf-8")) > 4096:
        return None
    return {"action": action, "rationale": rationale.strip()}


def extract_signed_submission(
    text: str,
) -> Optional[tuple[str, dict[str, Any]]]:
    match = _SIGNED_RESPONSE_RE.fullmatch(text or "")
    if match is None:
        return None
    code = match.group(1).strip()
    if not code or "```" in code:
        return None
    decision = extract_signed_decision(
        "```decision\n%s\n```" % match.group(2)
    )
    if decision is None:
        return None
    return code, decision



# How many rejected candidates a run keeps for diagnosis. Small on purpose: this exists so a
# task that rejects everything can be looked at, not to archive a run.
RETAINED_REJECTIONS = 5


def _retain_rejected(workdir, step, code, metrics, valid, *, response=None, parse_status=None):
    """Keep the first few rejected candidates on disk so a rejection can be diagnosed later.

    The evaluation ledger records a candidate by hash and never stores its source, and the
    trajectory records a label-blind failure kind. Both are deliberate. The consequence is that a
    task rejecting every proposal leaves nothing to look at: `CalorimeterDesign` rejected 36 of 36
    with `candidate_runtime_error`, its shipped baseline evaluates fine, and there was no way to
    see what the proposals had done differently - `best_program.py` is still the baseline, because
    nothing was ever accepted.

    A `no_code` draw is the same gap with a worse symptom: there is no candidate source at all.
    hy3-ioa on this host has hit max_output_tokens with an unclosed fence; without the raw reply
    on disk, the debug loop cannot tell a parser miss from a truncated stream.

    This writes to disk only. Nothing here is read back into the search loop, so the label-blind
    guarantee about what a searcher may see is untouched.
    """
    if valid:
        return
    try:
        directory = Path(workdir) / "rejected"
        directory.mkdir(exist_ok=True)
        kept = list(directory.glob("step_*.json"))
        if len(kept) >= RETAINED_REJECTIONS:
            return
        payload = {k: v for k, v in metrics.items()
                   if k in ("candidate_failure_kind", "error_message", "valid",
                            "combined_score")}
        if parse_status:
            payload["parse_status"] = parse_status
        if code:
            (directory / ("step_%03d.py" % int(step))).write_text(code, encoding="utf-8")
        if response is not None and not code:
            encoded = response.encode("utf-8")
            (directory / ("step_%03d.reply.txt" % int(step))).write_bytes(
                encoded[:_REPLY_RETAIN_BYTES])
            payload["response_utf8_bytes"] = len(encoded)
            payload["response_truncated"] = len(encoded) > _REPLY_RETAIN_BYTES
        (directory / ("step_%03d.json" % int(step))).write_text(
            json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        # Diagnostics must never be able to fail a run.
        pass


def _build_prompt(
    spec: TaskSpec,
    program: str,
    metrics: dict,
    *,
    proposal_slot: int | None = None,
    proposal_budget: int | None = None,
    active_wall_horizon_s: float | None = None,
    active_wall_elapsed_s: float | None = None,
    signed_decisions: bool = False,
) -> str:
    shown = search_visible_metrics(metrics)
    slot = ""
    if proposal_slot is not None and proposal_budget is not None:
        if active_wall_horizon_s is None:
            slot = (
                "## Preregistered proposal slot\n"
                f"This is proposal {proposal_slot} of {proposal_budget}. Explore a concrete "
                "implementation improvement appropriate to this slot.\n\n"
            )
        else:
            slot = (
                "## Current fixed-duration attempt\n"
                f"This is proposal {proposal_slot} in a fixed-duration run. The configured "
                "proposal ceiling is an operational safety bound, not an intended iteration "
                "count. Plan only against the active-time horizon below.\n\n"
            )
    horizon = ""
    if active_wall_horizon_s is not None and active_wall_elapsed_s is not None:
        remaining = max(0.0, active_wall_horizon_s - active_wall_elapsed_s)
        horizon = (
            "## Preregistered active-time horizon\n"
            f"This run stops at {active_wall_horizon_s:.3f} active wall seconds. "
            f"At prompt construction, {active_wall_elapsed_s:.3f} seconds have "
            f"elapsed and approximately {remaining:.3f} seconds remain. A response "
            "or evaluation completing after the cutoff cannot update the in-horizon "
            "incumbent.\n\n"
        )
    response_contract = (
        "Return exactly one complete ```python``` file followed by one "
        "```decision``` JSON object with exactly two fields: "
        '`{"action":"continue|commit|abstain","rationale":"..."}`. '
        "Use commit only when you would defend this submitted artifact now; "
        "use abstain when no artifact should be defended; otherwise continue."
        if signed_decisions else
        "Return one complete ```python``` file implementing the same entrypoint."
    )
    return (
        f"{spec.agent_visible_text()}\n\n"
        f"{slot}"
        f"{horizon}"
        f"## Parent program (`{spec.candidate_destination}`)\n"
        f"```python\n{program}\n```\n\n"
        f"## Its measured metrics\n```json\n{json.dumps(shown, indent=2)}\n```\n\n"
        "Propose a complete program intended to increase `combined_score`. "
        + response_contract
    )


def _validate_pending_proposal(
    pending: dict[str, Any], *, step: int, prompt: str,
    parent_sha256: str, prompt_source_step: int,
    feedback_released_through_step: int, prompt_metrics_rendered: str,
    system_prompt: str = SYSTEM_PROMPT,
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
        "system_prompt_sha256": sha256_text(system_prompt),
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
    elif status in {"no_code", "contract_invalid"}:
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
    published = pending.get("proposal_published_wall_seconds")
    if published is not None and (
        not isinstance(published, (int, float))
        or isinstance(published, bool)
        or not math.isfinite(float(published))
        or float(published) < float(prefix_wall)
    ):
        raise ValueError("pending proposal publication time is invalid")
    parsed_code = extract_code(response)
    if status == "parsed_code" and parsed_code != program:
        raise ValueError("pending proposal parse result differs from response")
    if status == "no_code" and parsed_code is not None:
        raise ValueError("pending proposal parse result differs from response")
    return program, dict(usage), float(prefix_wall)


def _greedy_rewrite_impl(
    spec: TaskSpec,
    llm: LLMClient,
    budget: int = 10,
    timeout_s: float = 300.0,
    workdir: Optional[Path] = None,
    log_fn: Callable[[str], None] = print,
    seed: int = 0,
    resume: bool = False,
    feedback_mode: str = "normal",
    active_wall_horizon_s: float | None = None,
    sentinel_interval_s: float | None = None,
    signed_decisions: bool = False,
    signed_decision_policy: str = "record_only",
) -> EvolveResult:
    if feedback_mode not in GREEDY_FEEDBACK_MODES:
        raise ValueError(
            "feedback_mode must be one of: %s" % ", ".join(sorted(GREEDY_FEEDBACK_MODES))
        )
    if budget < 0:
        raise ValueError("budget must be non-negative")
    if active_wall_horizon_s is not None and active_wall_horizon_s <= 0:
        raise ValueError("active_wall_horizon_s must be positive")
    if sentinel_interval_s is not None and sentinel_interval_s <= 0:
        raise ValueError("sentinel_interval_s must be positive")
    if sentinel_interval_s is not None and active_wall_horizon_s is None:
        raise ValueError("sentinel_interval_s requires active_wall_horizon_s")
    if signed_decision_policy not in {"record_only", "honor_stop"}:
        raise ValueError("signed_decision_policy must be record_only or honor_stop")
    if signed_decisions and active_wall_horizon_s is None:
        raise ValueError("signed_decisions requires active_wall_horizon_s")
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
    baseline_commit_recovery = bool(
        resume and manifest_path.is_file()
        and not checkpoint_path.exists() and trajectory_path.is_file()
    )
    ensure_run_manifest(
        workdir, spec=spec, llm=llm, algorithm="greedy_rewrite", seed=seed,
        feedback_mode=feedback_mode, resume=resume,
        protocol={
            "evaluator_timeout_seconds": float(timeout_s),
            "evaluation_ledger": True,
            **({
                "active_wall_horizon_s": active_wall_horizon_s,
                "sentinel_interval_s": sentinel_interval_s,
                "boundary_sentinels": True,
                "cutoff_policy": (
                    "artifact_published_by_cutoff; late results cannot update "
                    "in-horizon incumbent"
                ),
                "signed_decisions": signed_decisions,
                "signed_decision_policy": signed_decision_policy,
            } if active_wall_horizon_s is not None else {}),
        },
    )
    if resume and not (full_resume or baseline_retry or baseline_commit_recovery):
        raise FileNotFoundError("--resume requires checkpoint.json and trajectory.jsonl")

    sentinel_path = workdir / "sentinels" / "sentinel_events.jsonl"
    sentinel_resume = bool(
        full_resume or (baseline_commit_recovery and sentinel_path.is_file())
    )
    sentinel_ledger = (
        SentinelLedger(workdir, resume=sentinel_resume)
        if active_wall_horizon_s is not None else None
    )
    evaluation_ledger = EvaluationLedger(workdir)
    frozen_task_contract = task_contract_sha256(spec)
    frozen_task_package = task_package_sha256(spec)
    frozen_runtime_source = runtime_source_sha256()

    def validate_committed_evaluation_receipts(
        events: list[dict[str, Any]],
    ) -> None:
        for event in events:
            metadata = event.get("algorithm_metadata") or {}
            request_id = metadata.get("evaluation_request_id")
            # No-code contract failures have no evaluator request or receipt.
            if not event.get("candidate_sha256"):
                if request_id is not None:
                    raise ValueError("no-code trajectory event has an evaluation request")
                continue
            bound = evaluation_ledger.require_bound_record(request_id)
            receipt = bound["receipt"]
            request = bound["request"]
            if not (
                request.get("task_id") == spec.task_id
                and request.get("task_contract_sha256") == frozen_task_contract
                and request.get("task_package_sha256") == frozen_task_package
                and request.get("runtime_source_sha256") == frozen_runtime_source
                and request.get("step") == int(event["step"])
                and request.get("candidate_sha256") == event["candidate_sha256"]
                and receipt["metrics"] == (event.get("metrics") or {})
            ):
                raise ValueError("trajectory evaluation receipt binding differs")
    system_prompt = SIGNED_SYSTEM_PROMPT if signed_decisions else SYSTEM_PROMPT
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
        best_published_wall = float(
            checkpoint.get("best_published_wall_seconds", 0.0)
        )
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
        validate_committed_evaluation_receipts(prior_events)
        active_wall = float(prior_events[-1]["cumulative_wall_seconds"])
        result = EvolveResult(spec.task_id, best_score, baseline_score, best_program,
                              algorithm="greedy_rewrite", seed=seed)
        result.evaluated = int(prior_events[-1]["oracle_calls"])
        result.accepted = sum(bool(e.get("accepted")) for e in prior_events[1:])
        log_fn(f"[{spec.task_id}] resume at iter={start_iter} best={best_score:.6f}")
    elif baseline_commit_recovery:
        prior_events = load_trajectory(trajectory_path)
        if len(prior_events) != 1 or int(prior_events[0].get("step", -1)) != 0:
            raise ValueError(
                "checkpoint-free trajectory must contain exactly the baseline event"
            )
        validate_committed_evaluation_receipts(prior_events)
        baseline_src = spec.initial_program_path.read_text(encoding="utf-8")
        baseline_event = prior_events[0]
        if baseline_event.get("candidate_sha256") != sha256_text(baseline_src):
            raise ValueError("checkpoint-free baseline source binding differs")
        metrics = dict(baseline_event.get("metrics") or {})
        if metrics.get("infrastructure_failure") or float(metrics.get("valid", 0.0)) < 1.0:
            raise ValueError("checkpoint-free baseline event is not a valid receipt")
        baseline_score = float(metrics.get("combined_score", INVALID_SCORE))
        best_score, best_program = baseline_score, baseline_src
        best_source_step = 0
        best_published_wall = 0.0
        best_metrics = search_visible_metrics(metrics)
        baseline_metrics = dict(best_metrics)
        evaluated_candidates = [{
            "step": 0,
            "program": baseline_src,
            "sha256": sha256_text(baseline_src),
            "score": baseline_score,
            "valid": True,
            "metrics": baseline_metrics,
            "published_wall_seconds": 0.0,
        }]
        pending_proposal = None
        start_iter = 1
        active_wall = float(baseline_event["cumulative_wall_seconds"])
        result = EvolveResult(
            spec.task_id, baseline_score, baseline_score, baseline_src,
            algorithm="greedy_rewrite", seed=seed,
        )
        result.evaluated = int(baseline_event["oracle_calls"])
        result.accepted = 0
        if sentinel_ledger is not None and not sentinel_ledger.has_type("t0"):
            baseline_late = active_wall > float(active_wall_horizon_s)
            sentinel_ledger.capture(
                "t0",
                source=baseline_src,
                source_step=0,
                artifact_published_elapsed_seconds=0.0,
                recorded_elapsed_seconds=active_wall,
                selection_policy="baseline",
                evaluation=metrics,
                evaluation_status=(
                    "completed_after_schedule" if baseline_late else "completed"
                ),
                evaluation_completed_elapsed_seconds=active_wall,
                feedback_visible=not baseline_late,
                idempotency_key="t0",
            )
        log_fn(
            f"[{spec.task_id}] recover committed baseline before checkpoint "
            f"score={baseline_score:.6f}"
        )
    else:
        baseline_src = spec.initial_program_path.read_text(encoding="utf-8")
        cand_path.write_text(baseline_src, encoding="utf-8")
        baseline_receipt = evaluation_ledger.evaluate_once(
            {
                "kind": "baseline",
                "task_id": spec.task_id,
                "task_contract_sha256": frozen_task_contract,
                "task_package_sha256": frozen_task_package,
                "runtime_source_sha256": frozen_runtime_source,
                "step": 0,
                "candidate_sha256": sha256_text(baseline_src),
                "evaluator_timeout_seconds": float(timeout_s),
            },
            lambda: evaluate_candidate(spec, cand_path, timeout_s=timeout_s),
            clock=time.monotonic,
        )
        metrics = dict(baseline_receipt["metrics"])
        if metrics.get("infrastructure_failure"):
            raise EvaluatorInfrastructureError(
                "baseline trusted evaluator infrastructure failure: %s"
                % (metrics.get("error_message") or "no detail")
            )
        if float(metrics.get("valid", 0.0)) < 1.0:
            raise EvaluatorInfrastructureError(
                "frozen baseline is invalid under the trusted evaluator"
            )
        eval_wall = float(baseline_receipt["evaluation_wall_seconds"])
        baseline_score = float(metrics.get("combined_score", INVALID_SCORE))
        best_score, best_program = baseline_score, baseline_src
        best_source_step = 0
        best_published_wall = 0.0
        best_metrics = search_visible_metrics(metrics)
        baseline_metrics = dict(best_metrics)
        evaluated_candidates = [{
            "step": 0,
            "program": baseline_src,
            "sha256": sha256_text(baseline_src),
            "score": baseline_score,
            "valid": float(metrics.get("valid", 0.0)) >= 1.0,
            "metrics": baseline_metrics,
            "published_wall_seconds": 0.0,
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
            algorithm_metadata={
                "evaluation_request_id": baseline_receipt["request_id"],
                "evaluation_receipt_reused": bool(
                    baseline_receipt["receipt_reused"]
                ),
                "evaluation_receipt_committed": bool(
                    baseline_receipt.get("receipt_committed", True)
                ),
            },
        ))
        active_wall = eval_wall
        if sentinel_ledger is not None:
            baseline_late = active_wall > float(active_wall_horizon_s)
            sentinel_ledger.capture(
                "t0",
                source=baseline_src,
                source_step=0,
                artifact_published_elapsed_seconds=0.0,
                recorded_elapsed_seconds=active_wall,
                selection_policy="baseline",
                evaluation=metrics,
                evaluation_status=(
                    "completed_after_schedule" if baseline_late else "completed"
                ),
                evaluation_completed_elapsed_seconds=active_wall,
                feedback_visible=not baseline_late,
                idempotency_key="t0",
            )

    def save_checkpoint(next_iter: int) -> None:
        atomic_write_text(checkpoint_path, json.dumps({
            "schema_version": 1, "algorithm": "greedy_rewrite", "task_id": spec.task_id,
            "seed": seed, "next_iter": next_iter, "baseline_score": baseline_score,
            "baseline_metrics": baseline_metrics,
            "best_score": best_score, "best_metrics": best_metrics,
            "best_program": best_program, "best_sha256": sha256_text(best_program),
            "best_source_step": best_source_step,
            "best_published_wall_seconds": best_published_wall,
            "evaluated_candidates": evaluated_candidates,
            "pending_proposal": pending_proposal,
        }, indent=2, allow_nan=False) + "\n")
        atomic_write_text(workdir / "best_program.py", best_program)

    save_checkpoint(start_iter)

    horizon_reached = bool(
        active_wall_horizon_s is not None
        and active_wall >= active_wall_horizon_s
    )
    baseline_crossed_horizon = bool(
        active_wall_horizon_s is not None
        and len(load_trajectory(trajectory_path)) == 1
        and float(load_trajectory(trajectory_path)[0]["cumulative_wall_seconds"])
        > active_wall_horizon_s
    )
    existing_grid_times = [
        float(row["scheduled_elapsed_seconds"])
        for row in (sentinel_ledger.events if sentinel_ledger is not None else [])
        if row["sentinel_type"] == "fixed_grid"
    ]
    next_grid = (
        float(sentinel_interval_s)
        if sentinel_ledger is not None and sentinel_interval_s is not None
        else None
    )
    if next_grid is not None and existing_grid_times:
        next_grid = max(existing_grid_times) + float(sentinel_interval_s)

    def artifact_at_elapsed(
        grid: float,
    ) -> tuple[str, int, float, dict[str, Any], float]:
        source_by_step = {
            int(row["step"]): str(row["program"])
            for row in evaluated_candidates
            if row.get("program") is not None
        }
        source = baseline_src
        source_step = 0
        published = 0.0
        events = load_trajectory(trajectory_path)
        evaluation = dict(events[0].get("metrics") or {})
        completed = float(events[0]["cumulative_wall_seconds"])
        for event in events[1:]:
            step = int(event["step"])
            event_published = float(
                (event.get("algorithm_metadata") or {}).get(
                    "proposal_published_wall_seconds",
                    event["cumulative_wall_seconds"],
                )
            )
            if event_published <= grid and step in source_by_step:
                source = source_by_step[step]
                source_step = step
                published = event_published
                evaluation = dict(event.get("metrics") or {})
                completed = float(event["cumulative_wall_seconds"])
        return source, source_step, published, evaluation, completed

    def capture_due_grid(now: float) -> None:
        nonlocal next_grid
        if sentinel_ledger is None or next_grid is None:
            return
        horizon = float(active_wall_horizon_s)
        while next_grid <= min(now, horizon):
            source, source_step, published, evaluation, completed = (
                artifact_at_elapsed(next_grid)
            )
            sentinel_ledger.capture(
                "fixed_grid",
                source=source,
                source_step=source_step,
                scheduled_elapsed_seconds=next_grid,
                artifact_published_elapsed_seconds=published,
                recorded_elapsed_seconds=now,
                selection_policy="workspace_incumbent_at_grid",
                evaluation=evaluation,
                evaluation_status=(
                    "reused_deterministic"
                    if completed <= next_grid else "completed_after_schedule"
                ),
                evaluation_completed_elapsed_seconds=completed,
                feedback_visible=False,
                capture_method="post_call_capture_of_stable_incumbent",
                reason="deterministic evaluation reused; capture may lag a blocking call",
                idempotency_key="grid:%.9f" % next_grid,
            )
            next_grid += float(sentinel_interval_s)

    capture_due_grid(active_wall)

    prior_signed_actions = [
        row["sentinel_type"]
        for row in (sentinel_ledger.events if sentinel_ledger is not None else [])
        if row["sentinel_type"] in {"commit", "abstain"}
    ]
    honored_signed_stop_action = (
        prior_signed_actions[-1]
        if signed_decisions
        and signed_decision_policy == "honor_stop"
        and prior_signed_actions
        else None
    )

    for it in range(start_iter, budget + 1):
        if honored_signed_stop_action is not None:
            break
        if active_wall_horizon_s is not None and active_wall >= active_wall_horizon_s:
            horizon_reached = True
            break
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
            active_wall_horizon_s=active_wall_horizon_s,
            active_wall_elapsed_s=active_wall,
            signed_decisions=signed_decisions,
        )
        if pending_proposal is None:
            try:
                reply = llm.complete(
                    prompt,
                    system=system_prompt,
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
            if signed_decisions:
                signed_submission = extract_signed_submission(reply)
                if signed_submission is None:
                    code = None
                    signed_decision = None
                    parse_status = "contract_invalid"
                else:
                    code, signed_decision = signed_submission
                    parse_status = "parsed_code"
            else:
                code = extract_code(reply)
                signed_decision = None
                parse_status = "parsed_code" if code else "no_code"
            proposal_published_wall = active_wall + (time.monotonic() - step_started)
            pending_proposal = {
                "schema_version": 1,
                "step": it,
                "parse_status": parse_status,
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
                "system_prompt_sha256": sha256_text(system_prompt),
                "llm_usage": llm_usage,
                "pre_evaluation_wall_seconds": time.monotonic() - step_started,
                "proposal_published_wall_seconds": proposal_published_wall,
                "signed_decision": signed_decision,
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
            system_prompt=system_prompt,
        )
        proposal_published_wall = float(
            pending_proposal.get(
                "proposal_published_wall_seconds",
                active_wall + pre_evaluation_wall,
            )
        )
        pending_record = dict(pending_proposal)
        signed_decision = pending_record.get("signed_decision")
        signed_contract_invalid = bool(
            signed_decisions and pending_record.get("parse_status") == "contract_invalid"
        )
        if sentinel_ledger is not None:
            sentinel_ledger.capture(
                "submission",
                source=code,
                source_step=it,
                artifact_published_elapsed_seconds=proposal_published_wall,
                recorded_elapsed_seconds=proposal_published_wall,
                selection_policy="agent_submission_before_evaluation",
                evaluation_status="not_evaluated" if code else "not_applicable",
                feedback_visible=False,
                reason=(
                    None if code
                    else "provider response violated code or signed-decision contract"
                ),
                metadata={
                    "signed_decision": signed_decision,
                    "response_sha256": pending_record.get("response_sha256"),
                    "decision_made_before_evaluation": True,
                },
                provider_response=pending_record.get("response"),
                idempotency_key="submission:%d" % it,
            )
            if (
                isinstance(signed_decision, dict)
                and signed_decision.get("action") in {"commit", "abstain"}
            ):
                decision_action = str(signed_decision["action"])
                sentinel_ledger.capture(
                    decision_action,
                    source=code if decision_action == "commit" else None,
                    source_step=it if decision_action == "commit" else None,
                    artifact_published_elapsed_seconds=proposal_published_wall,
                    recorded_elapsed_seconds=proposal_published_wall,
                    selection_policy="signed_agent_%s_before_evaluation" % decision_action,
                    evaluation_status=(
                        "not_evaluated"
                        if decision_action == "commit" and code
                        else "not_applicable"
                    ),
                    feedback_visible=False,
                    metadata={
                        "rationale": signed_decision["rationale"],
                        "response_sha256": pending_record.get("response_sha256"),
                        "decision_policy": signed_decision_policy,
                        "decision_made_before_evaluation": True,
                        "evaluation_not_visible_when_deciding": True,
                        "evaluation_result_bound_by_trajectory_step": it,
                    },
                    provider_response=pending_record.get("response"),
                    idempotency_key="decision:%d" % it,
                )
        evaluation_started = None
        evaluation_receipt = None
        if not code:
            evaluation_started = time.monotonic()
            log_fn(f"[{spec.task_id}] iter {it}: no code block parsed")
            error = "signed_decision_contract_invalid" if signed_contract_invalid else "no_code"
            m = {"combined_score": INVALID_SCORE, "valid": 0.0, "error_message": error}
            score, valid, accepted = INVALID_SCORE, False, False
            candidate_sha = ""
            _retain_rejected(
                workdir, it, "", m, valid=False,
                response=pending_record.get("response"),
                parse_status=pending_record.get("parse_status"),
            )
        else:
            cand_path.write_text(code, encoding="utf-8")
            evaluation_receipt = evaluation_ledger.evaluate_once(
                {
                    "kind": "proposal",
                    "task_id": spec.task_id,
                    "task_contract_sha256": frozen_task_contract,
                    "task_package_sha256": frozen_task_package,
                    "runtime_source_sha256": frozen_runtime_source,
                    "step": int(it),
                    "candidate_sha256": sha256_text(code),
                    "parent_sha256": parent_sha,
                    "prompt_sha256": sha256_text(prompt),
                    "evaluator_timeout_seconds": float(timeout_s),
                },
                lambda: evaluate_candidate(spec, cand_path, timeout_s=timeout_s),
                clock=time.monotonic,
            )
            m = dict(evaluation_receipt["metrics"])
            if m.get("infrastructure_failure"):
                raise EvaluatorInfrastructureError(
                    "candidate trusted evaluator infrastructure failure: %s"
                    % (m.get("error_message") or "no detail"))
            result.evaluated += 1
            score = float(m.get("combined_score", INVALID_SCORE))
            valid = float(m.get("valid", 0.0)) >= 1.0
            accepted = bool(valid and score > best_score)
            candidate_sha = sha256_text(code)
            error = m.get("error_message")
            _retain_rejected(workdir, it, code, m, valid)
        # The provider result is now a terminal candidate outcome. Keep the
        # on-disk pending record until the event and next checkpoint commit.
        pending_proposal = None
        evaluation_wall = (
            float(evaluation_receipt["evaluation_wall_seconds"])
            if evaluation_receipt is not None
            else time.monotonic() - float(evaluation_started)
        )
        step_wall = pre_evaluation_wall + evaluation_wall
        active_wall += step_wall
        completed_after_horizon = bool(
            active_wall_horizon_s is not None
            and active_wall > active_wall_horizon_s
        )
        if code:
            evaluated_candidates.append({
                "step": it,
                "program": code,
                "sha256": candidate_sha,
                "score": score,
                "valid": valid,
                "metrics": search_visible_metrics(m),
                "published_wall_seconds": proposal_published_wall,
            })
        # A result can be scientifically retained after cutoff, but it cannot
        # become the in-horizon incumbent or visible feedback.
        accepted = bool(accepted and not completed_after_horizon)
        if accepted:
            best_score, best_program = score, code
            best_source_step = it
            best_published_wall = proposal_published_wall
            best_metrics = search_visible_metrics(m)
            result.best_score, result.best_program = best_score, best_program
            result.accepted += 1
        entry = {"iter": it, "score": score, "best": best_score, "accepted": accepted,
                 "metrics": {k: m.get(k) for k in ("combined_score", "valid", "raw_score", "error_message")}}
        result.history.append(entry)
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
                "proposal_published_wall_seconds": proposal_published_wall,
                "completed_after_active_wall_horizon": completed_after_horizon,
                "signed_decision_action": (
                    signed_decision.get("action")
                    if isinstance(signed_decision, dict) else None
                ),
                "evaluation_request_id": (
                    evaluation_receipt.get("request_id")
                    if evaluation_receipt is not None else None
                ),
                "evaluation_receipt_reused": bool(
                    evaluation_receipt.get("receipt_reused")
                ) if evaluation_receipt is not None else False,
                "evaluation_receipt_committed": bool(
                    evaluation_receipt.get("receipt_committed", True)
                ) if evaluation_receipt is not None else False,
            },
        ))
        if sentinel_ledger is not None and valid and not sentinel_ledger.has_type("first_valid"):
            sentinel_ledger.capture(
                "first_valid",
                source=code,
                source_step=it,
                artifact_published_elapsed_seconds=proposal_published_wall,
                recorded_elapsed_seconds=active_wall,
                selection_policy="first_valid",
                evaluation=m,
                evaluation_status=(
                    "completed_after_schedule" if completed_after_horizon else "completed"
                ),
                evaluation_completed_elapsed_seconds=active_wall,
                feedback_visible=not completed_after_horizon,
                idempotency_key="first_valid",
            )
        capture_due_grid(active_wall)
        save_checkpoint(it + 1)
        log_fn(f"[{spec.task_id}] iter {it}: score={score:.6f} best={best_score:.6f} "
               f"{'ACCEPT' if accepted else 'reject'}")
        if completed_after_horizon:
            horizon_reached = True
            break
        if (
            signed_decisions
            and signed_decision_policy == "honor_stop"
            and isinstance(signed_decision, dict)
            and signed_decision.get("action") in {"commit", "abstain"}
            and proposal_published_wall <= float(active_wall_horizon_s)
        ):
            honored_signed_stop_action = str(signed_decision["action"])
            break

    if active_wall_horizon_s is not None and active_wall >= active_wall_horizon_s:
        horizon_reached = True
    if sentinel_ledger is not None and not sentinel_ledger.has_type("terminal"):
        terminal_recorded = active_wall
        capture_due_grid(terminal_recorded)
        (
            terminal_program,
            terminal_source_step,
            terminal_published_wall,
            terminal_evaluation,
            terminal_evaluation_completed,
        ) = artifact_at_elapsed(float(active_wall_horizon_s))
        sentinel_ledger.capture(
            "terminal",
            source=terminal_program,
            source_step=terminal_source_step,
            scheduled_elapsed_seconds=float(active_wall_horizon_s),
            artifact_published_elapsed_seconds=terminal_published_wall,
            recorded_elapsed_seconds=terminal_recorded,
            selection_policy="terminal_workspace_artifact",
            evaluation=terminal_evaluation,
            evaluation_status=(
                (
                    "reused_deterministic"
                    if terminal_evaluation_completed <= float(active_wall_horizon_s)
                    else "completed_after_schedule"
                ) if terminal_evaluation is not None
                else "not_evaluated"
            ),
            evaluation_completed_elapsed_seconds=(
                terminal_evaluation_completed
            ),
            feedback_visible=False,
            reason=(
                "baseline_evaluation_completed_after_active_wall_horizon"
                if baseline_crossed_horizon
                else "signed_%s_honored_before_horizon" % honored_signed_stop_action
                if honored_signed_stop_action is not None
                else "active_wall_horizon_reached"
                if horizon_reached
                else "proposal_budget_exhausted_before_active_wall_horizon"
            ),
            idempotency_key="terminal",
        )

    atomic_write_text(workdir / "best_program.py", best_program)
    result.summary = summarize_trajectory(load_trajectory(trajectory_path), budget=budget + 1)
    result.summary.update({"algorithm": "greedy_rewrite", "task_id": spec.task_id,
                           "seed": seed, "baseline_score": baseline_score,
                           "budget": budget, "feedback_mode": feedback_mode,
                           "active_wall_horizon_s": active_wall_horizon_s,
                           "sentinel_interval_s": sentinel_interval_s,
                           "horizon_reached": horizon_reached,
                           "baseline_crossed_horizon": baseline_crossed_horizon,
                           "signed_decisions": signed_decisions,
                           "signed_decision_policy": signed_decision_policy,
                           "latest_signed_endpoint_action": next(
                               (
                                   row["sentinel_type"]
                                   for row in reversed(sentinel_ledger.events)
                                   if row["sentinel_type"] in {"commit", "abstain"}
                               ),
                               None,
                           ) if sentinel_ledger is not None else None,
                           "honored_signed_stop_action": honored_signed_stop_action,
                           "sentinel_snapshot": (
                               sentinel_ledger.snapshot() if sentinel_ledger is not None else None
                           ),
                           "evaluation_ledger_snapshot": evaluation_ledger.snapshot(),
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
    active_wall_horizon_s: float | None = None,
    sentinel_interval_s: float | None = None,
    signed_decisions: bool = False,
    signed_decision_policy: str = "record_only",
) -> EvolveResult:
    resolved = Path(
        workdir
        or (spec.task_dir / "runs" / time.strftime("%Y%m%d_%H%M%S"))
    ).resolve()
    with RunLease(resolved):
        return _greedy_rewrite_impl(
            spec,
            llm,
            budget=budget,
            timeout_s=timeout_s,
            workdir=resolved,
            log_fn=log_fn,
            seed=seed,
            resume=resume,
            feedback_mode=feedback_mode,
            active_wall_horizon_s=active_wall_horizon_s,
            sentinel_interval_s=sentinel_interval_s,
            signed_decisions=signed_decisions,
            signed_decision_policy=signed_decision_policy,
        )


# Backwards-compatible import; the public name no longer claims OpenEvolve semantics.
evolve = greedy_rewrite
