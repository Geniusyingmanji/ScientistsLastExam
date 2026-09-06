"""Fail-closed verification for completed search-run artifacts."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from .evaluation_ledger import EvaluationLedger, RunLease
from .metric_visibility import (
    score_only_metrics,
    search_visible_metrics,
    shuffled_feedback_metrics,
)
from .protocol import load_trajectory, sha256_text, summarize_trajectory
from .runtime_identity import validate_runtime_descriptor

INVALID_SCORE = -1.0e18

_HASH = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
FRONTIER_IDENTITY_FIELDS = (
    "task_family_id",
    "wave_id",
    "wave_manifest_sha256",
)
GREEDY_FEEDBACK_MODES = {
    "normal",
    "none",
    "shuffled",
    "score_only",
    "delayed_replay",
    "selection_blind",
}

_MODE_POLICIES = {
    "selection_blind": (
        "offline_best_of_open_loop_batch",
        "offline_best_update",
    ),
    "delayed_replay": (
        "delayed_online_parent_offline_final_best",
        "observer_best_update_not_immediate_parent_release",
    ),
}


IDENTITY_FIELDS = (
    "task_id",
    "algorithm",
    "feedback_mode",
    "seed",
    "llm_condition_sha256",
    "llm_condition",
    "task_contract_sha256",
    "task_package_sha256",
    "runtime_source_sha256",
    "task_family_id",
    "wave_id",
    "wave_manifest_sha256",
)


def _identifier(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or not _IDENTIFIER.fullmatch(value)
    ):
        raise ValueError("run manifest %s is not a canonical identifier" % label)
    return value


def _hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ValueError("run manifest %s must be a lowercase SHA-256" % label)
    return value


def _manifest_identity(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") != 1:
        raise ValueError("run manifest schema_version must be 1")
    task_id = _identifier(manifest.get("task_id"), "task_id")
    algorithm = manifest.get("algorithm")
    if not isinstance(algorithm, str) or not algorithm:
        raise ValueError("run manifest algorithm must be a nonempty string")
    seed = manifest.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("run manifest seed must be an integer")
    feedback_mode = manifest.get("feedback_mode")
    if feedback_mode not in GREEDY_FEEDBACK_MODES:
        raise ValueError("run manifest feedback_mode is unsupported")
    llm_condition = manifest.get("llm_condition")
    if not isinstance(llm_condition, dict) or not llm_condition:
        raise ValueError("run manifest llm_condition must be a nonempty object")
    identity = {
        "task_id": task_id,
        "algorithm": algorithm,
        "feedback_mode": feedback_mode,
        "seed": seed,
        "llm_condition_sha256": _hash(
            manifest.get("llm_condition_sha256"), "llm_condition_sha256"
        ),
        "llm_condition": llm_condition,
        "task_contract_sha256": _hash(
            manifest.get("task_contract_sha256"), "task_contract_sha256"
        ),
        "task_package_sha256": _hash(
            manifest.get("task_package_sha256"), "task_package_sha256"
        ),
        "runtime_source_sha256": _hash(
            manifest.get("runtime_source_sha256"), "runtime_source_sha256"
        ),
    }
    present_frontier = {key for key in FRONTIER_IDENTITY_FIELDS if key in manifest}
    if present_frontier and present_frontier != set(FRONTIER_IDENTITY_FIELDS):
        raise ValueError("run manifest frontier binding must be complete or absent")
    if present_frontier:
        identity.update({
            "task_family_id": _identifier(
                manifest.get("task_family_id"), "task_family_id"
            ),
            "wave_id": _identifier(manifest.get("wave_id"), "wave_id"),
            "wave_manifest_sha256": _hash(
                manifest.get("wave_manifest_sha256"), "wave_manifest_sha256"
            ),
        })
    else:
        identity.update({key: None for key in FRONTIER_IDENTITY_FIELDS})
    return identity


def _document(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("run lacks a valid %s" % label) from exc
    if not isinstance(value, dict):
        raise ValueError("run %s must be an object" % label)
    return value


def _verify_run_unlocked(
    root: Path,
    *,
    expected_budget: int | None = None,
    expected_trusted_runtime_sha256: str | None = None,
) -> dict[str, Any]:
    manifest = _document(root / "run_manifest.json", "run_manifest.json")
    identity = _manifest_identity(manifest)
    trusted_runtime = validate_runtime_descriptor(
        manifest.get("trusted_evaluator_runtime")
    )
    trusted_runtime_sha256 = str(trusted_runtime["fingerprint_sha256"])
    if expected_trusted_runtime_sha256 is not None:
        if (
            not isinstance(expected_trusted_runtime_sha256, str)
            or len(expected_trusted_runtime_sha256) != 64
            or expected_trusted_runtime_sha256 != trusted_runtime_sha256
        ):
            raise ValueError(
                "run trusted runtime differs from the externally expected trusted runtime"
            )
    if manifest.get("algorithm") != "greedy_rewrite":
        raise ValueError(
            "trusted run verification requires greedy_rewrite durable "
            "per-evaluation receipts"
        )
    summary = _document(root / "summary.json", "summary.json")
    try:
        events = load_trajectory(root / "trajectory.jsonl")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("run lacks a valid trajectory.jsonl") from exc
    if not events:
        raise ValueError("completed run trajectory must contain a baseline event")
    budget = summary.get("budget")
    if (
        isinstance(budget, bool)
        or not isinstance(budget, int)
        or budget < 0
        or budget < max(int(event["step"]) for event in events)
    ):
        raise ValueError("run summary budget is smaller than its trajectory")
    if expected_budget is not None and (
        isinstance(expected_budget, bool)
        or not isinstance(expected_budget, int)
        or expected_budget < 0
        or budget != expected_budget
    ):
        raise ValueError("run summary budget differs from the externally expected budget")
    final_budget_units = int(events[-1].get("budget_units", -1))
    if final_budget_units < budget + 1:
        raise ValueError(
            "early termination is not a verified completed budget contract"
        )
    if final_budget_units > budget + 1:
        raise ValueError("trajectory exceeds the completed budget contract")
    rebuilt = summarize_trajectory(events, budget=budget + 1)
    if any(summary.get(key) != value for key, value in rebuilt.items()):
        raise ValueError("run summary accounting differs from trajectory")
    for key in ("task_id", "algorithm", "seed", "feedback_mode"):
        if summary.get(key) != manifest.get(key):
            raise ValueError("run summary %s differs from manifest" % key)

    if manifest.get("algorithm") == "greedy_rewrite":
        ledger = EvaluationLedger(root)
        verified_request_ids = []
        verified_receipts = {}
        expected_oracle_calls = 0
        incumbent_hash = None
        incumbent_step = None
        incumbent_score = INVALID_SCORE
        incumbent_metrics: dict[str, Any] = {}
        candidate_history: list[dict[str, Any]] = []
        horizon = (manifest.get("protocol") or {}).get("active_wall_horizon_s")
        baseline_receipt_score = None
        for event in events:
            step = int(event["step"])
            trajectory_metrics = event.get("metrics") or {}
            if "trusted_evaluator_runtime_sha256" in trajectory_metrics:
                raise ValueError(
                    "science metrics contain internal trusted runtime fingerprint"
                )
            metadata = event.get("algorithm_metadata") or {}
            if step > 0:
                expected_policy, expected_accepted_semantics = _MODE_POLICIES.get(
                    identity["feedback_mode"],
                    ("online_incumbent", "online_incumbent_update"),
                )
                if identity["feedback_mode"] == "selection_blind":
                    expected_source = candidate_history[0]
                    expected_released_step = 0
                elif identity["feedback_mode"] == "delayed_replay":
                    expected_released_step = max(0, step - 2)
                    eligible = [
                        row for row in candidate_history
                        if row["step"] <= expected_released_step and row["valid"]
                    ]
                    expected_source = max(
                        eligible, key=lambda row: (row["score"], -row["step"])
                    )
                else:
                    expected_released_step = step - 1
                    expected_source = {
                        "candidate_sha256": incumbent_hash,
                        "step": incumbent_step,
                        "metrics": incumbent_metrics,
                    }
                if identity["feedback_mode"] == "none":
                    expected_prompt_metrics: dict[str, Any] = {}
                elif identity["feedback_mode"] == "score_only":
                    expected_prompt_metrics = score_only_metrics(incumbent_metrics)
                elif identity["feedback_mode"] == "shuffled":
                    expected_prompt_metrics = shuffled_feedback_metrics(
                        [prior.get("metrics") or {} for prior in events[:step]],
                        seed=identity["seed"], proposal_step=step,
                    )
                else:
                    expected_prompt_metrics = expected_source["metrics"]
                visible_prompt_metrics = search_visible_metrics(
                    expected_prompt_metrics
                )
                rendered_prompt_metrics = json.dumps(
                    visible_prompt_metrics, indent=2
                )
                if not (
                    event.get("parent_sha256")
                    == expected_source["candidate_sha256"]
                    and metadata.get("selection_policy") == expected_policy
                    and metadata.get("accepted_semantics")
                    == expected_accepted_semantics
                    and metadata.get("proposal_slot") == step
                    and metadata.get("prompt_source_step")
                    == expected_source["step"]
                    and metadata.get("feedback_released_through_step")
                    == expected_released_step
                    and metadata.get("prompt_metrics_sha256")
                    == sha256_text(rendered_prompt_metrics)
                    and metadata.get("prompt_metrics_utf8_bytes")
                    == len(rendered_prompt_metrics.encode("utf-8"))
                    and metadata.get("prompt_metric_keys")
                    == ",".join(sorted(visible_prompt_metrics))
                ):
                    raise ValueError(
                        "trajectory feedback mode semantics differ from manifest"
                    )
            request_id = metadata.get("evaluation_request_id")
            if not event.get("candidate_sha256"):
                if request_id is not None:
                    raise ValueError("no-code event unexpectedly has an evaluation receipt")
                expected_score, expected_valid = INVALID_SCORE, False
            else:
                bound = ledger.require_bound_record(request_id)
                request = bound["request"]
                receipt = bound["receipt"]
                if (
                    request.get("trusted_evaluator_runtime_sha256")
                    != trusted_runtime_sha256
                ):
                    raise ValueError(
                        "evaluation request trusted runtime differs from manifest"
                    )
                expected_oracle_calls += 1
                verified_request_ids.append(str(request_id))
                verified_receipts[str(request_id)] = str(receipt["metrics_sha256"])
                expected_request_identity = {
                    key: identity[key]
                    for key in IDENTITY_FIELDS
                    if identity.get(key) is not None
                }
                expected_request_identity["proposal_budget"] = budget
                for key, value in expected_request_identity.items():
                    if request.get(key) != value:
                        raise ValueError("evaluation receipt %s differs from manifest" % key)
                request_frontier = {
                    key for key in FRONTIER_IDENTITY_FIELDS if key in request
                }
                expected_frontier = {
                    key for key in FRONTIER_IDENTITY_FIELDS
                    if identity.get(key) is not None
                }
                if request_frontier != expected_frontier:
                    raise ValueError(
                        "evaluation receipt frontier binding differs from manifest"
                    )
                expected_kind = "baseline" if step == 0 else "proposal"
                event_metrics = receipt.get("metrics") or {}
                if "trusted_evaluator_runtime_sha256" in event_metrics:
                    raise ValueError(
                        "science metrics contain internal trusted runtime fingerprint"
                    )
                try:
                    expected_score = float(
                        event_metrics.get("combined_score", INVALID_SCORE)
                    )
                    expected_valid = float(event_metrics.get("valid", 0.0)) >= 1.0
                except (TypeError, ValueError) as exc:
                    raise ValueError("evaluation receipt has invalid score metrics") from exc
                if not math.isfinite(expected_score):
                    expected_score, expected_valid = INVALID_SCORE, False
                if not (
                    request.get("kind") == expected_kind
                    and request.get("step") == step
                    and request.get("candidate_sha256") == event["candidate_sha256"]
                    and request.get("parent_sha256") == event.get("parent_sha256")
                    and (
                        step == 0
                        or request.get("prompt_sha256") == metadata.get("prompt_sha256")
                    )
                    and event_metrics == (event.get("metrics") or {})
                ):
                    raise ValueError("evaluation receipt differs from trajectory event")
            if not (
                int(event.get("oracle_calls", -1)) == expected_oracle_calls
                and int(event.get("budget_units", -1)) == step + 1
                and float(event.get("score")) == expected_score
                and bool(event.get("valid")) == expected_valid
            ):
                raise ValueError("trajectory accounting differs from evaluation receipts")
            if event.get("candidate_sha256"):
                candidate_history.append({
                    "step": step,
                    "candidate_sha256": str(event["candidate_sha256"]),
                    "score": expected_score,
                    "valid": expected_valid,
                    "metrics": search_visible_metrics(event_metrics),
                })
            if step == 0:
                if not expected_valid:
                    raise ValueError("completed run has an invalid baseline receipt")
                expected_accepted = True
                incumbent_hash = str(event["candidate_sha256"])
                incumbent_step = 0
                incumbent_score = expected_score
                incumbent_metrics = search_visible_metrics(event_metrics)
                baseline_receipt_score = expected_score
            else:
                after_horizon = bool(
                    horizon is not None
                    and float(event["cumulative_wall_seconds"]) > float(horizon)
                )
                if bool(metadata.get("completed_after_active_wall_horizon")) != after_horizon:
                    raise ValueError("trajectory cutoff state differs from frozen protocol")
                expected_accepted = bool(
                    expected_valid
                    and expected_score > incumbent_score
                    and not after_horizon
                )
                if expected_accepted:
                    incumbent_hash = str(event["candidate_sha256"])
                    incumbent_step = step
                    incumbent_score = expected_score
                    incumbent_metrics = search_visible_metrics(event_metrics)
            if not (
                bool(event.get("accepted")) == expected_accepted
                and float(event.get("best_score")) == incumbent_score
            ):
                raise ValueError("trajectory incumbent state differs from receipt replay")
        ledger_snapshot = ledger.snapshot()
        expected_ids = sorted(verified_request_ids)
        if not (
            ledger_snapshot.get("request_ids") == expected_ids
            and ledger_snapshot.get("receipt_ids") == expected_ids
            and ledger_snapshot.get("open_request_ids") == []
        ):
            raise ValueError("evaluation ledger contains requests outside the trajectory")
        if summary.get("evaluation_ledger_snapshot") != ledger_snapshot:
            raise ValueError("evaluation ledger snapshot differs from summary")
        if float(summary.get("baseline_score")) != baseline_receipt_score:
            raise ValueError("summary baseline score differs from baseline receipt")
        expected_summary_policy = _MODE_POLICIES.get(
            identity["feedback_mode"], ("online_incumbent", None)
        )[0]
        if summary.get("selection_policy") != expected_summary_policy:
            raise ValueError("run summary feedback mode semantics differ from manifest")
    else:
        verified_request_ids = []
        verified_receipts = {}
        incumbent_hash = None

    best_path = root / "best_program.py"
    try:
        best_hash = sha256_text(best_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError("run lacks best_program.py") from exc
    best_score = float(summary.get("best_score"))
    if manifest.get("algorithm") == "greedy_rewrite" and best_hash != incumbent_hash:
        raise ValueError("best program differs from replayed incumbent")
    if manifest.get("algorithm") != "greedy_rewrite" and not any(
        event.get("candidate_sha256") == best_hash and bool(event.get("valid"))
        and float(event.get("score")) == best_score for event in events
    ):
        raise ValueError("best program is not bound to a best-scoring trajectory event")
    return {
        "verified": True,
        **identity,
        "budget": budget,
        "event_count": len(events),
        "best_program_sha256": best_hash,
        "verified_request_ids": sorted(verified_request_ids),
        "verified_receipt_metrics_sha256": dict(sorted(verified_receipts.items())),
        "trusted_evaluator_runtime": trusted_runtime,
        "trusted_evaluator_runtime_sha256": trusted_runtime_sha256,
    }


def verify_run(
    workdir: Path,
    *,
    acquire_lease: bool = True,
    expected_budget: int | None = None,
    expected_trusted_runtime_sha256: str | None = None,
) -> dict[str, Any]:
    """Rebuild a run and verify summary, receipt, counter, and incumbent state."""

    root = Path(workdir).resolve()
    if not acquire_lease:
        return _verify_run_unlocked(
            root,
            expected_budget=expected_budget,
            expected_trusted_runtime_sha256=expected_trusted_runtime_sha256,
        )
    with RunLease(root):
        return _verify_run_unlocked(
            root,
            expected_budget=expected_budget,
            expected_trusted_runtime_sha256=expected_trusted_runtime_sha256,
        )
