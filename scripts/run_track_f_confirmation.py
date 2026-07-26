#!/usr/bin/env python3
"""Confirm frozen Track F artifacts only after the complete search cohort closes.

This process is intentionally separate from ``batch_evolve.py``.  It validates the
entire preregistered search risk set before reading the private confirmation contexts,
audits every fresh panel before evaluating any model artifact, selects full-proposal and
common-realized-token artifacts from retained trajectories, and replays each unique
artifact twice per task/replicate panel.  Infrastructure failures are retained as attempts
and may be retried explicitly with ``--resume``; candidate invalidity is a terminal
scientific outcome and replay disagreement quarantines a stochastic artifact.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import hmac
import importlib.util
import json
import math
import multiprocessing
import platform
import random
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.algorithms.common import (  # noqa: E402
    atomic_write_text,
    feedback_scope,
    runtime_source_sha256,
    task_contract_sha256,
)
from frontier_science.algorithms.evolve import (  # noqa: E402
    SYSTEM_PROMPT,
    _build_prompt,
)
from frontier_science.evaluate import (  # noqa: E402
    canonical_trusted_context,
    evaluate_candidate,
)
from frontier_science.protocol import (  # noqa: E402
    compact_trajectory_snapshot,
    load_trajectory,
    realized_token_curve,
    sha256_text,
    summarize_at_token_horizon,
    summarize_trajectory,
)
from frontier_science.metric_visibility import (  # noqa: E402
    score_only_metrics,
    search_visible_metrics,
)
from frontier_science.provenance import (  # noqa: E402
    SOURCE_SCOPE,
    finalize_report_trust,
    source_provenance,
)
from frontier_science.registry import find_task  # noqa: E402


EXPECTED_ALGORITHM = "greedy_rewrite"
EXPECTED_MODES = (
    "normal", "score_only", "delayed_replay", "selection_blind",
)
WILLIAMS_ROWS = (
    (0, 1, 3, 2),
    (1, 2, 0, 3),
    (2, 3, 1, 0),
    (3, 0, 2, 1),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _run_key(run: dict[str, Any]) -> str:
    return "%s|%s|%s|%d" % (
        run["task"], run["algorithm"], run["feedback_mode"], int(run["seed"])
    )


def _latest_runs(runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest = {}
    for run in runs:
        latest[_run_key(run)] = run
    return latest


def _git_scope_changes(left: str, right: str) -> list[str]:
    try:
        output = subprocess.check_output(
            ["git", "diff", "--name-only", left, right, "--", *SOURCE_SCOPE],
            cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("cannot compare frozen source revisions") from exc
    return [line for line in output.splitlines() if line.strip()]


def _source_equivalent(left: str, right: str) -> bool:
    return left == right or not _git_scope_changes(left, right)


def _reconstruct_condition_schedule(
    replicates: list[int], randomization_seed: int,
) -> list[dict[str, Any]]:
    """Rebuild the frozen four-row Williams schedule from first principles.

    The search report and preregistration are two copies of the same proposed
    schedule, so equality between them is not an independent randomization
    check.  Reconstructing the rows here catches a jointly mistyped or edited
    schedule before any private confirmation context is read.
    """
    if (
        not replicates
        or len(set(replicates)) != len(replicates)
        or not isinstance(randomization_seed, int)
        or isinstance(randomization_seed, bool)
    ):
        raise ValueError("invalid Williams schedule inputs")
    row_indices = [index % len(WILLIAMS_ROWS) for index in range(len(replicates))]
    random.Random(randomization_seed).shuffle(row_indices)
    return [
        {
            "replicate_identifier": replicate,
            "feedback_modes": [EXPECTED_MODES[position] for position in WILLIAMS_ROWS[row]],
        }
        for replicate, row in zip(replicates, row_indices)
    ]


def _observer_best_step(events: list[dict[str, Any]], through_step: int) -> int:
    if through_step < 0 or through_step >= len(events):
        raise ValueError("observer horizon is outside trajectory")
    best_step = 0
    best_score = float(events[0]["score"])
    for event in events[1 : through_step + 1]:
        if bool(event["valid"]) and float(event["score"]) > best_score:
            best_step = int(event["step"])
            best_score = float(event["score"])
    return best_step


def _source_rows(
    events: list[dict[str, Any]], checkpoint: dict[str, Any], baseline: str,
) -> dict[int, str]:
    if checkpoint.get("pending_proposal") is not None:
        raise ValueError("completed search checkpoint retains a pending proposal")
    rows = checkpoint.get("evaluated_candidates") or []
    if not rows:
        raise ValueError("checkpoint has no retained evaluated candidates")
    sources = {}
    for row in rows:
        step = int(row.get("step", -1))
        if step in sources or step < 0 or step >= len(events):
            raise ValueError("checkpoint candidate steps are invalid")
        source = str(row.get("program", ""))
        digest = sha256_text(source)
        if (
            digest != row.get("sha256")
            or digest != events[step].get("candidate_sha256")
            or bool(row.get("valid")) != bool(events[step].get("valid"))
            or float(row.get("score")) != float(events[step].get("score"))
            or row.get("metrics")
            != search_visible_metrics(events[step].get("metrics") or {})
        ):
            raise ValueError("checkpoint candidate source does not bind trajectory")
        sources[step] = source
    if sources.get(0) != baseline:
        raise ValueError("checkpoint baseline source differs from task baseline")
    for event in events:
        step = int(event["step"])
        if bool(event.get("candidate_sha256")) != (step in sources):
            raise ValueError("trajectory/source retention differs")
    return sources


def _validate_treatment_lineage(
    events: list[dict[str, Any]], sources: dict[int, str], spec: Any,
    mode: str, budget: int,
) -> dict[str, Any]:
    if mode not in EXPECTED_MODES:
        raise ValueError("unexpected Track F feedback mode")
    policy = (
        "offline_best_of_open_loop_batch"
        if mode == "selection_blind"
        else "delayed_online_parent_offline_final_best"
        if mode == "delayed_replay"
        else "online_incumbent"
    )
    semantics = (
        "offline_best_update"
        if mode == "selection_blind"
        else "observer_best_update_not_immediate_parent_release"
        if mode == "delayed_replay"
        else "online_incumbent_update"
    )
    if float(events[0]["best_score"]) != float(events[0]["score"]):
        raise ValueError("baseline best score differs from baseline score")
    prior_best = float(events[0]["score"])
    records = []
    for event in events[1:]:
        step = int(event["step"])
        if mode == "selection_blind":
            parent_step, released_through = 0, 0
        elif mode == "delayed_replay":
            released_through = max(0, step - 2)
            parent_step = _observer_best_step(events, released_through)
        else:
            released_through = step - 1
            parent_step = _observer_best_step(events, step - 1)
        metrics = search_visible_metrics(events[parent_step].get("metrics") or {})
        if mode == "score_only":
            metrics = score_only_metrics(metrics)
        parent_source = sources[parent_step]
        metrics_rendered = json.dumps(metrics, indent=2)
        prompt = _build_prompt(
            spec,
            parent_source,
            metrics,
            proposal_slot=step,
            proposal_budget=budget,
        )
        metadata = event.get("algorithm_metadata") or {}
        expected = {
            "selection_policy": policy,
            "accepted_semantics": semantics,
            "proposal_slot": step,
            "prompt_source_step": parent_step,
            "feedback_released_through_step": released_through,
            "prompt_sha256": sha256_text(prompt),
            "prompt_utf8_bytes": len(prompt.encode("utf-8")),
            "prompt_program_utf8_bytes": len(parent_source.encode("utf-8")),
            "prompt_metrics_sha256": sha256_text(metrics_rendered),
            "prompt_metrics_utf8_bytes": len(metrics_rendered.encode("utf-8")),
            "prompt_metric_keys": ",".join(sorted(metrics)),
        }
        if any(metadata.get(key) != value for key, value in expected.items()):
            raise ValueError("search treatment prompt/lineage differs at step %d" % step)
        if event.get("parent_sha256") != sha256_text(parent_source):
            raise ValueError("search treatment parent hash differs at step %d" % step)
        accepted = bool(event["valid"] and float(event["score"]) > prior_best)
        if bool(event.get("accepted")) != accepted:
            raise ValueError("search treatment accepted flag differs at step %d" % step)
        if accepted:
            prior_best = float(event["score"])
        if float(event["best_score"]) != prior_best:
            raise ValueError("search treatment best score differs at step %d" % step)
        records.append({
            "step": step,
            "parent_step": parent_step,
            "released_through_step": released_through,
            "prompt_sha256": expected["prompt_sha256"],
            "system_prompt_sha256": sha256_text(SYSTEM_PROMPT),
        })
    return {"selection_policy": policy, "records": records}


def _load_cell(
    run: dict[str, Any], config: dict[str, Any], source_binding: dict[str, Any],
    budget: int,
) -> dict[str, Any]:
    task = str(run["task"])
    mode = str(run["feedback_mode"])
    replicate_id = int(run["seed"])
    spec = find_task(task, include_uncertified=True)
    workdir = Path(run["workdir"]).resolve()
    expected = (
        Path(config["work_root"]).resolve()
        / task.replace("/", "__") / EXPECTED_ALGORITHM / mode
        / ("seed_%d" % replicate_id)
    )
    if workdir != expected:
        raise ValueError("search cell workdir differs from configured layout")
    paths = {
        name: workdir / name for name in (
            "trajectory.jsonl", "checkpoint.json", "summary.json",
            "run_manifest.json", "best_program.py", "solution.py",
        )
    }
    if not all(path.is_file() for path in paths.values()):
        raise ValueError("search cell is missing a retained artifact")
    events = load_trajectory(paths["trajectory.jsonl"])
    if len(events) != budget + 1:
        raise ValueError("search trajectory differs from proposal budget")
    snapshot = compact_trajectory_snapshot(
        paths["trajectory.jsonl"], schema_version=2
    )
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("search raw trajectory differs from outer report")
    checkpoint = json.loads(paths["checkpoint.json"].read_text(encoding="utf-8"))
    summary = json.loads(paths["summary.json"].read_text(encoding="utf-8"))
    manifest = json.loads(paths["run_manifest.json"].read_text(encoding="utf-8"))
    if summary != run.get("summary"):
        raise ValueError("search summary differs from outer report")
    expected_summary = summarize_trajectory(events, budget=budget + 1)
    if any(summary.get(key) != value for key, value in expected_summary.items()):
        raise ValueError("search summary accounting differs from trajectory")
    task_bindings = {
        row["task"]: row for row in source_binding["tasks"]
    }
    binding = task_bindings[task]
    if not (
        manifest.get("schema_version") == 1
        and manifest.get("algorithm") == EXPECTED_ALGORITHM
        and manifest.get("task_id") == task
        and manifest.get("task_contract_sha256")
        == binding["task_contract_sha256"]
        and manifest.get("runtime_source_sha256")
        == source_binding["runtime_source_sha256"]
        and manifest.get("seed") == replicate_id
        and manifest.get("feedback_mode") == mode
        and manifest.get("feedback_scope") == feedback_scope(mode)
        and manifest.get("llm_condition_sha256") == config.get("llm_condition_sha256")
    ):
        raise ValueError("search run manifest differs from frozen source/condition")
    baseline = spec.initial_program_path.read_text(encoding="utf-8")
    sources = _source_rows(events, checkpoint, baseline)
    treatment = _validate_treatment_lineage(
        events, sources, spec, mode, budget
    )
    full_best_step = _observer_best_step(events, budget)
    terminal_source_step = max(sources)
    if not (
        checkpoint.get("schema_version") == 1
        and checkpoint.get("task_id") == task
        and checkpoint.get("seed") == replicate_id
        and checkpoint.get("next_iter") == budget + 1
        and checkpoint.get("best_source_step") == full_best_step
        and checkpoint.get("best_sha256") == sha256_text(sources[full_best_step])
        and checkpoint.get("best_program") == sources[full_best_step]
        and paths["best_program.py"].read_text(encoding="utf-8")
        == sources[full_best_step]
        and paths["solution.py"].read_text(encoding="utf-8")
        == sources[terminal_source_step]
        and float(run["best"]) == float(events[full_best_step]["score"])
        and float(run["baseline"]) == float(events[0]["score"])
        and int(run["accepted"])
        == sum(bool(event["accepted"]) for event in events[1:])
        and int(run["evaluated"]) == int(events[-1]["oracle_calls"])
        and summary.get("selection_policy") == treatment["selection_policy"]
        and run.get("execution_block_index") is not None
        and run.get("within_block_position") is not None
    ):
        raise ValueError("search checkpoint/full-horizon selection differs")
    curve = realized_token_curve(events)
    return {
        "task": task,
        "condition": mode,
        "replicate_id": replicate_id,
        "workdir": str(workdir),
        "events": events,
        "sources": sources,
        "total_tokens": int(curve[-1]["cumulative_tokens"]),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "checkpoint_sha256": _sha256(paths["checkpoint.json"]),
        "run_manifest_sha256": _sha256(paths["run_manifest.json"]),
        "treatment_lineage": treatment,
    }


def _load_oracle_auditor(task: str):
    spec = find_task(task, include_uncertified=True)
    path = spec.task_dir / "verification" / "evaluator.py"
    module_spec = importlib.util.spec_from_file_location(
        "track_f_confirmation_audit_" + task.replace("/", "_"), path
    )
    if module_spec is None or module_spec.loader is None:
        raise ImportError("cannot load task oracle for confirmation audit")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    auditor = getattr(module, "audit_confirmation_context", None)
    if not callable(auditor):
        raise TypeError("task lacks audit_confirmation_context: %s" % task)
    return auditor


def _derive_master_seed(root_entropy_hex: str, task: str, replicate_id: int) -> int:
    message = (
        "frontier-science-track-f-confirmation-v1\0%s\0%d"
        % (task, int(replicate_id))
    ).encode("utf-8")
    digest = hmac.new(
        bytes.fromhex(root_entropy_hex), message, hashlib.sha256
    ).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


def _validate_context_artifacts(
    private_path: Path, public_path: Path, preregistration: dict[str, Any],
    tasks: list[str], replicates: list[int], expected_source_binding: dict[str, Any],
) -> tuple[dict[tuple[str, int], dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    if private_path.stat().st_mode & 0o077:
        raise ValueError("private confirmation manifest permissions are too broad")
    private_payload = private_path.read_bytes()
    private = json.loads(private_payload)
    public = json.loads(public_path.read_text(encoding="utf-8"))
    commitment = preregistration.get("confirmation_commitment") or {}
    if not (
        public.get("schema_version") == 1
        and public.get("commitment_version") == 1
        and public.get("purpose") == "track_f_fresh_confirmation_context_commitment"
        and commitment.get("sha256") == _sha256(public_path)
        and commitment.get("private_manifest_sha256")
        == hashlib.sha256(private_payload).hexdigest()
        == public.get("private_manifest_sha256")
        and commitment.get("block_count") == public.get("block_count")
        and private.get("schema_version") == 1
        and private.get("purpose") == "track_f_private_fresh_confirmation_contexts"
        and private.get("cohort_id") == public.get("cohort_id")
        and private.get("source_binding") == public.get("source_binding")
    ):
        raise ValueError("private confirmation manifest/public commitment differs")
    public_source_binding = public["source_binding"]
    if not (
        public_source_binding.get("runtime_source_sha256")
        == expected_source_binding["runtime_source_sha256"]
        and public_source_binding.get("tasks") == expected_source_binding["tasks"]
        and _source_equivalent(
            public_source_binding.get("git_revision"),
            expected_source_binding["git_revision"],
        )
    ):
        raise ValueError("confirmation commitment source binding differs from preregistration")
    root_entropy = private.get("root_entropy_hex")
    if (
        not isinstance(root_entropy, str)
        or len(root_entropy) != 64
        or any(character not in "0123456789abcdef" for character in root_entropy)
    ):
        raise ValueError("private confirmation root entropy is invalid")
    private_rows = private.get("blocks") or []
    public_rows = public.get("blocks") or []
    private_blocks = {
        (row.get("task"), int(row.get("replicate_id", -1))): row
        for row in private_rows
    }
    public_blocks = {
        (row.get("task"), int(row.get("replicate_id", -1))): row
        for row in public_rows
    }
    expected_keys = {(task, replicate) for task in tasks for replicate in replicates}
    if (
        set(private_blocks) != expected_keys
        or set(public_blocks) != expected_keys
        or len(private_blocks) != len(private_rows)
        or len(public_blocks) != len(public_rows)
        or public.get("block_count") != len(expected_keys)
    ):
        raise ValueError("confirmation block risk set differs from search design")
    contexts = {}
    audits = []
    for key in sorted(expected_keys):
        task, replicate_id = key
        private_block = private_blocks[key]
        public_block = public_blocks[key]
        context = private_block.get("context")
        payload = canonical_trusted_context(context)
        digest = hashlib.sha256(payload).hexdigest()
        if not (
            private_block.get("context_sha256") == digest
            and public_block.get("context_sha256") == digest
            and public_block.get("context_utf8_bytes") == len(payload)
            and context.get("task_id") == task
            and context.get("panel_id") == public_block.get("panel_id")
            and context.get("generator") == public_block.get("generator")
            and context.get("world_count") == public_block.get("world_count")
            and context.get("master_seed")
            == _derive_master_seed(root_entropy, task, replicate_id)
        ):
            raise ValueError("private confirmation context binding differs")
        audit = _load_oracle_auditor(task)(context)
        if audit.get("passed") is not True:
            raise ValueError("task confirmation context audit did not pass")
        contexts[key] = context
        audits.append({
            "task": task,
            "replicate_id": replicate_id,
            "context_sha256": digest,
            "audit": audit,
        })
    return contexts, public, audits


def _load_bound_json(path_value: Any, label: str) -> tuple[Path, dict[str, Any]]:
    if not isinstance(path_value, str) or not path_value:
        raise ValueError("%s path is missing" % label)
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("cannot load %s" % label) from exc
    if not isinstance(document, dict):
        raise ValueError("%s must be a JSON object" % label)
    return path, document


def _validate_presearch_prerequisites(
    preregistration: dict[str, Any], preregistration_path: Path,
    frozen_revision: str, model_condition_sha256: str,
) -> list[dict[str, Any]]:
    """Validate all frozen prerequisites before any private context is read."""
    prerequisites = preregistration.get("prerequisites") or {}
    records = []
    for key in ("full_test_suite", "security_audit", "certification_audit"):
        binding = prerequisites.get(key) or {}
        path, report = _load_bound_json(binding.get("path"), key)
        provenance = report.get("source_provenance") or {}
        if not (
            binding.get("sha256") == _sha256(path)
            and binding.get("bytes") == len(path.read_bytes())
            and report.get("schema_version") == 1
            and report.get("execution_passed") is True
            and report.get("trusted_evidence") is True
            and report.get("passed") is True
            and provenance.get("source_tree_dirty") is False
            and _source_equivalent(
                frozen_revision, provenance.get("git_revision")
            )
        ):
            raise ValueError("%s prerequisite differs from preregistration" % key)
        if key == "full_test_suite" and not (
            report.get("unittest_ok") is True
            and int(report.get("test_count", 0)) > 0
        ):
            raise ValueError("full test suite prerequisite did not pass")
        if key == "security_audit" and int(report.get("test_count", 0)) <= 0:
            raise ValueError("security audit prerequisite has no tests")
        if key == "certification_audit" and not (
            report.get("inventory_count") == 59
            and report.get("status_counts")
            == {"certified": 7, "candidate": 43, "quarantined": 9}
        ):
            raise ValueError("certification prerequisite inventory differs")
        records.append({
            "name": key,
            "path": str(path),
            "sha256": binding["sha256"],
            "source_revision": provenance["git_revision"],
        })
    precision_binding = preregistration.get("precision_plan") or {}
    precision_path, precision = _load_bound_json(
        precision_binding.get("path"), "precision plan"
    )
    precision_provenance = precision.get("source_provenance") or {}
    design = preregistration.get("design") or {}
    if not (
        precision_binding.get("sha256") == _sha256(precision_path)
        and precision_binding.get("bytes") == len(precision_path.read_bytes())
        and precision.get("execution_passed") is True
        and precision.get("trusted_evidence") is True
        and precision.get("passed") is True
        and precision_provenance.get("source_tree_dirty") is False
        and _source_equivalent(
            frozen_revision, precision_provenance.get("git_revision")
        )
        and precision.get("fixed_balanced_blocks_per_condition")
        == design.get("fixed_blocks_per_condition")
        and precision.get("scheduled_search_cells")
        == design.get("scheduled_cell_count")
        and precision.get("scheduled_model_proposals")
        == design.get("scheduled_model_proposals")
    ):
        raise ValueError("precision plan prerequisite differs from preregistration")
    records.append({
        "name": "precision_plan",
        "path": str(precision_path),
        "sha256": precision_binding["sha256"],
        "source_revision": precision_provenance["git_revision"],
    })
    smoke_binding = prerequisites.get("protocol_smoke") or {}
    smoke_path, smoke = _load_bound_json(
        smoke_binding.get("path"), "protocol smoke"
    )
    smoke_provenance = smoke.get("source_provenance") or {}
    config = smoke.get("config") or {}
    aggregate = smoke.get("aggregate") or {}
    expected_replicates = list(smoke_binding.get("replicate_identifiers") or [])
    expected_modes = list(smoke_binding.get("feedback_modes") or [])
    smoke_randomization_seed = smoke_binding.get(
        "condition_order_randomization_seed"
    )
    expected_schedule = smoke_binding.get("condition_order_schedule")
    reconstructed_schedule = _reconstruct_condition_schedule(
        expected_replicates, smoke_randomization_seed
    )
    expected_cells = int(smoke_binding.get("scheduled_cell_count", -1))
    expected_block_workers = smoke_binding.get("block_workers")
    exact_binding = config.get("preregistration") or {}
    latest = _latest_runs(smoke.get("runs") or [])
    expected_keys = {
        "%s|%s|%s|%d" % (
            smoke_binding.get("task"), EXPECTED_ALGORITHM, mode, replicate
        )
        for mode in expected_modes for replicate in expected_replicates
    }
    if not (
        smoke.get("schema_version") == 1
        and smoke.get("execution_passed") is True
        and smoke.get("trusted_evidence") is True
        and smoke.get("passed") is True
        and smoke_provenance.get("source_tree_dirty") is False
        and _source_equivalent(frozen_revision, smoke_provenance.get("git_revision"))
        and config.get("tasks") == [smoke_binding.get("task")]
        and config.get("algorithms") == [EXPECTED_ALGORITHM]
        and config.get("feedback_modes") == expected_modes == list(EXPECTED_MODES)
        and config.get("seeds") == expected_replicates
        and smoke_binding.get("condition_order") == "balanced_williams"
        and config.get("condition_order") == "balanced_williams"
        and config.get("condition_order_randomization_seed")
        == smoke_randomization_seed
        and expected_schedule == reconstructed_schedule
        and config.get("condition_order_schedule") == expected_schedule
        and config.get("block_workers") == expected_block_workers
        and (config.get("block_parallelism") or {}).get(
            "maximum_concurrent_blocks"
        ) == expected_block_workers
        and (config.get("block_parallelism") or {}).get(
            "within_block_conditions"
        ) == "serial_in_condition_order_schedule"
        and config.get("budget") == smoke_binding.get("budget") == 0
        and config.get("trajectory_snapshot_schema_version") == 2
        and config.get("llm_condition_sha256") == model_condition_sha256
        and exact_binding.get("sha256") == _sha256(preregistration_path)
        and exact_binding.get("bytes") == len(preregistration_path.read_bytes())
        and expected_cells == len(expected_keys)
        and set(latest) == expected_keys
        and all(not run.get("error") for run in latest.values())
        and aggregate.get("successful_runs") == expected_cells
        and aggregate.get("failed_runs") == 0
    ):
        raise ValueError("protocol smoke prerequisite differs from preregistration")
    for replicate_index, replicate in enumerate(expected_replicates):
        modes = expected_schedule[replicate_index]["feedback_modes"]
        for position, mode in enumerate(modes, 1):
            key = "%s|%s|%s|%d" % (
                smoke_binding["task"], EXPECTED_ALGORITHM, mode, replicate
            )
            run = latest[key]
            if not (
                run.get("execution_block_index") == replicate_index + 1
                and run.get("within_block_position") == position
            ):
                raise ValueError("protocol smoke block execution order differs")
    records.append({
        "name": "protocol_smoke",
        "path": str(smoke_path),
        "sha256": _sha256(smoke_path),
        "source_revision": smoke_provenance["git_revision"],
        "exact_preregistration_binding": True,
        "scheduled_cell_count": expected_cells,
    })
    return records


def _validate_preregistration_and_search(
    preregistration_path: Path,
    search_report_path: Path,
    public_commitment_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    preregistration = json.loads(preregistration_path.read_text(encoding="utf-8"))
    search = json.loads(search_report_path.read_text(encoding="utf-8"))
    design = preregistration.get("design") or {}
    frozen = preregistration.get("frozen_source") or {}
    config = search.get("config") or {}
    binding = config.get("preregistration") or {}
    tasks = [row.get("task") for row in design.get("tasks") or []]
    task_hashes = {row.get("task"): row.get("task_contract_sha256")
                   for row in design.get("tasks") or []}
    replicates = [int(value) for value in design.get("replicate_identifiers") or []]
    modes = list(design.get("feedback_modes") or [])
    budget = int(design.get("proposal_budget", -1))
    timeout = float(design.get("evaluator_timeout_seconds", -1))
    public_commitment = preregistration.get("confirmation_commitment") or {}
    confirmation_replays = int(
        design.get("confirmation_replays_per_artifact", -1)
    )
    search_block_workers = design.get("search_block_workers")
    confirmation_workers = design.get("confirmation_workers")
    condition_randomization_seed = design.get(
        "condition_order_randomization_seed"
    )
    expected_schedule = design.get("condition_order_schedule")
    reconstructed_schedule = _reconstruct_condition_schedule(
        replicates, condition_randomization_seed
    )
    model_condition = preregistration.get("model_condition") or {}
    if not (
        preregistration.get("schema_version") == 1
        and preregistration.get("preregistration_version") == 1
        and preregistration.get("purpose") == "track_f_feedback_confirmatory_study"
        and tasks
        and len(set(tasks)) == len(tasks)
        and replicates
        and len(set(replicates)) == len(replicates)
        and modes == list(EXPECTED_MODES)
        and design.get("algorithm") == EXPECTED_ALGORITHM
        and design.get("condition_order") == "balanced_williams"
        and isinstance(condition_randomization_seed, int)
        and not isinstance(condition_randomization_seed, bool)
        and isinstance(expected_schedule, list)
        and len(expected_schedule) == len(replicates)
        and expected_schedule == reconstructed_schedule
        and confirmation_replays == 2
        and isinstance(search_block_workers, int)
        and not isinstance(search_block_workers, bool)
        and search_block_workers > 0
        and isinstance(confirmation_workers, int)
        and not isinstance(confirmation_workers, bool)
        and confirmation_workers > 0
        and design.get("search_parallelism_unit")
        == "task_algorithm_replicate"
        and design.get("search_within_block_conditions")
        == "serial_in_condition_order_schedule"
        and design.get("confirmation_worker_isolation") == "spawn_process"
        and design.get("confirmation_look_assignment")
        == "planned_order_before_dispatch"
        and isinstance(design.get("confirmation_randomization_seed"), int)
        and not isinstance(design.get("confirmation_randomization_seed"), bool)
        and budget > 0
        and timeout > 0
        and design.get("scheduled_cell_count")
        == len(tasks) * len(EXPECTED_MODES) * len(replicates)
        and design.get("fixed_blocks_per_condition") == len(replicates)
        and public_commitment.get("sha256") == _sha256(public_commitment_path)
        and frozen.get("runtime_source_sha256") == runtime_source_sha256()
        and all(
            task_contract_sha256(find_task(task, include_uncertified=True))
            == task_hashes[task]
            for task in tasks
        )
        and search.get("schema_version") == 1
        and search.get("execution_passed") is True
        and search.get("trusted_evidence") is True
        and search.get("passed") is True
        and config.get("tasks") == tasks
        and config.get("algorithms") == [EXPECTED_ALGORITHM]
        and config.get("feedback_modes") == list(EXPECTED_MODES)
        and config.get("condition_order") == design.get("condition_order")
        and config.get("condition_order_randomization_seed")
        == condition_randomization_seed
        and config.get("condition_order_schedule") == expected_schedule
        and config.get("seeds") == replicates
        and config.get("budget") == budget
        and float(config.get("timeout_s", -1)) == timeout
        and config.get("block_workers") == search_block_workers
        and (config.get("block_parallelism") or {}).get("unit")
        == "task_algorithm_replicate"
        and (config.get("block_parallelism") or {}).get(
            "within_block_conditions"
        ) == "serial_in_condition_order_schedule"
        and (config.get("block_parallelism") or {}).get(
            "cross_block_scheduling"
        ) == "fixed_submission_order_nonadaptive"
        and (config.get("block_parallelism") or {}).get(
            "maximum_concurrent_blocks"
        ) == search_block_workers
        and model_condition.get("llm_condition_sha256")
        == config.get("llm_condition_sha256")
        and model_condition.get("server_side_seed_control") is False
        and (config.get("llm") or {}).get("server_side_seed_control") is False
        and config.get("trajectory_snapshot_schema_version") == 2
        and binding.get("sha256") == _sha256(preregistration_path)
        and int(binding.get("bytes", -1)) == len(preregistration_path.read_bytes())
    ):
        raise ValueError("preregistration/search configuration differs")
    current = source_provenance(ROOT)
    source_revision = (search.get("source_provenance") or {}).get("git_revision")
    if not (
        current.get("git_available") is True
        and current.get("source_tree_dirty") is False
        and (search.get("source_provenance") or {}).get("source_tree_dirty") is False
        and _source_equivalent(frozen.get("revision"), current["git_revision"])
        and _source_equivalent(frozen.get("revision"), source_revision)
    ):
        raise ValueError("confirmation/search source differs from frozen source")
    prerequisite_audits = _validate_presearch_prerequisites(
        preregistration,
        preregistration_path,
        frozen["revision"],
        model_condition["llm_condition_sha256"],
    )
    source_binding = {
        "git_revision": frozen["revision"],
        "runtime_source_sha256": frozen["runtime_source_sha256"],
        "tasks": [
            {
                "task": task,
                "task_contract_sha256": task_hashes[task],
                "generator": row.get("confirmation_generator"),
                "world_count": row.get("confirmation_world_count"),
            }
            for task, row in (
                (row["task"], row) for row in design["tasks"]
            )
        ],
    }
    latest = _latest_runs(search.get("runs") or [])
    expected_keys = {
        "%s|%s|%s|%d" % (task, EXPECTED_ALGORITHM, mode, replicate)
        for task in tasks for mode in EXPECTED_MODES for replicate in replicates
    }
    if set(latest) != expected_keys or any(run.get("error") for run in latest.values()):
        raise ValueError("complete search risk set is not available")
    for task_index, task in enumerate(tasks):
        for replicate_index, replicate in enumerate(replicates):
            block_index = task_index * len(replicates) + replicate_index + 1
            schedule = expected_schedule[replicate_index]["feedback_modes"]
            for position, mode in enumerate(schedule, 1):
                key = "%s|%s|%s|%d" % (
                    task, EXPECTED_ALGORITHM, mode, replicate
                )
                run = latest[key]
                if not (
                    run.get("execution_block_index") == block_index
                    and run.get("within_block_position") == position
                ):
                    raise ValueError("search block execution order differs")
    cells = [
        _load_cell(latest[key], config, source_binding, budget)
        for key in sorted(latest)
    ]
    return preregistration, search, cells, {
        "tasks": tasks,
        "replicates": replicates,
        "budget": budget,
        "timeout": timeout,
        "confirmation_replays": confirmation_replays,
        "confirmation_randomization_seed": design[
            "confirmation_randomization_seed"
        ],
        "confirmation_workers": confirmation_workers,
        "source_binding": source_binding,
        "current_provenance": current,
        "prerequisite_audits": prerequisite_audits,
    }


def _build_endpoint_plan(
    cells: list[dict[str, Any]],
    contexts: dict[tuple[str, int], dict[str, Any]],
    budget: int,
    confirmation_replays: int,
    confirmation_randomization_seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    groups = {}
    for cell in cells:
        groups.setdefault((cell["task"], cell["replicate_id"]), []).append(cell)
    endpoints = []
    source_by_evaluation = {}
    artifact_rows = {}
    for key in sorted(groups):
        group = groups[key]
        if {cell["condition"] for cell in group} != set(EXPECTED_MODES):
            raise ValueError("search block lacks one feedback condition")
        horizon = min(cell["total_tokens"] for cell in group)
        context_sha = hashlib.sha256(
            canonical_trusted_context(contexts[key])
        ).hexdigest()
        for cell in sorted(group, key=lambda row: EXPECTED_MODES.index(row["condition"])):
            token_summary = summarize_at_token_horizon(cell["events"], horizon)
            endpoint_specs = (
                ("full_proposal_horizon", budget, cell["total_tokens"]),
                (
                    "common_total_token_horizon",
                    int(token_summary["selected_step"]),
                    int(token_summary["tokens_spent_by_selected_step"]),
                ),
            )
            for endpoint_name, completed_step, tokens_spent in endpoint_specs:
                best_step = _observer_best_step(cell["events"], completed_step)
                source = cell["sources"][best_step]
                candidate_sha = sha256_text(source)
                artifact_id = hashlib.sha256(
                    ("%s\0%d\0%s\0%s" % (
                        cell["task"], cell["replicate_id"],
                        context_sha, candidate_sha,
                    )).encode("utf-8")
                ).hexdigest()
                endpoint_id = "%s|%d|%s|%s" % (
                    cell["task"], cell["replicate_id"],
                    cell["condition"], endpoint_name,
                )
                endpoints.append({
                    "endpoint_id": endpoint_id,
                    "task": cell["task"],
                    "replicate_id": cell["replicate_id"],
                    "condition": cell["condition"],
                    "endpoint": endpoint_name,
                    "common_total_token_horizon": horizon,
                    "completed_through_step": completed_step,
                    "tokens_spent_by_completed_step": tokens_spent,
                    "best_source_step": best_step,
                    "search_score": float(cell["events"][best_step]["score"]),
                    "candidate_sha256": candidate_sha,
                    "context_sha256": context_sha,
                    "artifact_id": artifact_id,
                })
                existing = artifact_rows.get(artifact_id)
                row = {
                    "artifact_id": artifact_id,
                    "task": cell["task"],
                    "replicate_id": cell["replicate_id"],
                    "context_sha256": context_sha,
                    "candidate_sha256": candidate_sha,
                }
                if existing is not None and existing != row:
                    raise ValueError("confirmation artifact id collision")
                artifact_rows[artifact_id] = row
                prior_source = source_by_evaluation.get(artifact_id)
                if prior_source is not None and prior_source != source:
                    raise ValueError("same confirmation artifact hash has different source")
                source_by_evaluation[artifact_id] = source
    artifact_ids = sorted(artifact_rows)
    random.Random(int(confirmation_randomization_seed)).shuffle(artifact_ids)
    evaluations = []
    # Interleave replay rounds so a systematic service-time shift does not place
    # both replays for one artifact next to each other.
    for replay_index in range(confirmation_replays):
        for artifact_id in artifact_ids:
            artifact = artifact_rows[artifact_id]
            evaluation_id = hashlib.sha256(
                ("%s\0replay\0%d" % (artifact_id, replay_index)).encode("utf-8")
            ).hexdigest()
            evaluations.append({
                "evaluation_id": evaluation_id,
                "artifact_id": artifact_id,
                "replay_index": replay_index,
                **{key: value for key, value in artifact.items() if key != "artifact_id"},
            })
    return endpoints, evaluations, source_by_evaluation


def _latest_evaluation_attempts(
    attempts: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    latest = {}
    for attempt in attempts:
        latest[attempt["evaluation_id"]] = attempt
    return latest


def _terminal_evaluation(attempt: dict[str, Any] | None) -> bool:
    if not attempt:
        return False
    if attempt.get("status") != "completed":
        return False
    metrics = attempt.get("metrics") or {}
    return not bool(metrics.get("infrastructure_failure"))


def _evaluate_confirmation_worker(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one frozen artifact/context pair in an isolated worker."""
    started = time.monotonic()
    evaluation_id = str(payload["evaluation_id"])
    expected_candidate_sha = str(payload["candidate_sha256"])
    expected_context_sha = str(payload["context_sha256"])
    source = str(payload["source"])
    if sha256_text(source) != expected_candidate_sha:
        return {
            "evaluation_id": evaluation_id,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "wall_seconds": time.monotonic() - started,
            "metrics": {
                "combined_score": -1.0e18,
                "valid": 0.0,
                "error_message": "planned confirmation candidate binding mismatch",
                "infrastructure_failure": 1.0,
            },
        }
    try:
        with tempfile.TemporaryDirectory(
            prefix="fs_track_f_confirmation_"
        ) as temporary:
            candidate = Path(temporary) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(
                find_task(str(payload["task"]), include_uncertified=True),
                candidate,
                timeout_s=float(payload["timeout"]),
                trusted_context=payload["context"],
            )
    except Exception:  # noqa: BLE001 - fixed infrastructure record, no leakage
        metrics = {
            "combined_score": -1.0e18,
            "valid": 0.0,
            "error_message": "confirmation worker infrastructure failure",
            "infrastructure_failure": 1.0,
        }
    if metrics.get("trusted_context_sha256") != expected_context_sha:
        metrics = {
            "combined_score": -1.0e18,
            "valid": 0.0,
            "error_message": "trusted context binding mismatch after confirmation",
            "infrastructure_failure": 1.0,
        }
    return {
        "evaluation_id": evaluation_id,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "wall_seconds": time.monotonic() - started,
        "metrics": metrics,
    }


def _validate_attempt_ledger(
    document: dict[str, Any], evaluations: list[dict[str, Any]],
) -> None:
    """Fail closed on edits to the write-ahead confirmation look ledger."""
    planned = {row["evaluation_id"]: row for row in evaluations}
    if len(planned) != len(evaluations):
        raise ValueError("confirmation plan has duplicate evaluation ids")
    attempts = document.get("attempts")
    if not isinstance(attempts, list):
        raise ValueError("confirmation attempt ledger is not a list")
    counts: dict[str, int] = {}
    terminal_seen: set[str] = set()
    immutable_keys = (
        "artifact_id", "replay_index", "task", "replicate_id",
        "candidate_sha256", "context_sha256",
    )
    for look_index, attempt in enumerate(attempts, 1):
        if not isinstance(attempt, dict):
            raise ValueError("confirmation attempt ledger row is not an object")
        evaluation_id = attempt.get("evaluation_id")
        evaluation = planned.get(evaluation_id)
        if evaluation is None:
            raise ValueError("confirmation attempt is outside the planned risk set")
        if evaluation_id in terminal_seen:
            raise ValueError("confirmation attempt follows a terminal scientific outcome")
        counts[evaluation_id] = counts.get(evaluation_id, 0) + 1
        if not (
            attempt.get("attempt_index") == counts[evaluation_id]
            and attempt.get("confirmation_look_index") == look_index
            and all(attempt.get(key) == evaluation.get(key) for key in immutable_keys)
            and isinstance(attempt.get("started_at"), str)
            and bool(attempt.get("started_at"))
        ):
            raise ValueError("confirmation attempt lineage or ordering differs")
        status = attempt.get("status")
        if status == "started":
            if not (
                attempt.get("completed_at") is None
                and attempt.get("wall_seconds") is None
                and attempt.get("metrics") is None
            ):
                raise ValueError("started confirmation attempt contains outcome data")
            continue
        if status != "completed":
            raise ValueError("confirmation attempt status is invalid")
        metrics = attempt.get("metrics")
        wall_seconds = attempt.get("wall_seconds")
        if not (
            isinstance(attempt.get("completed_at"), str)
            and bool(attempt.get("completed_at"))
            and isinstance(wall_seconds, (int, float))
            and not isinstance(wall_seconds, bool)
            and math.isfinite(float(wall_seconds))
            and float(wall_seconds) >= 0.0
            and isinstance(metrics, dict)
        ):
            raise ValueError("completed confirmation attempt is malformed")
        try:
            json.dumps(metrics, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("confirmation attempt metrics are not finite JSON") from exc
        context_sha = metrics.get("trusted_context_sha256")
        if context_sha is not None and context_sha != evaluation["context_sha256"]:
            raise ValueError("confirmation attempt context binding differs")
        if not bool(metrics.get("infrastructure_failure")):
            if context_sha != evaluation["context_sha256"]:
                raise ValueError("terminal confirmation attempt lacks context binding")
            terminal_seen.add(evaluation_id)


def _render_results(
    document: dict[str, Any], endpoints: list[dict[str, Any]],
) -> None:
    latest = _latest_evaluation_attempts(document.get("attempts") or [])
    by_artifact = {}
    for evaluation in document["planned_evaluations"]:
        by_artifact.setdefault(evaluation["artifact_id"], []).append(evaluation)
    artifact_results = []
    for artifact_id, evaluations in sorted(by_artifact.items()):
        attempts = [latest.get(row["evaluation_id"]) for row in evaluations]
        terminal = all(_terminal_evaluation(attempt) for attempt in attempts)
        metrics = [attempt["metrics"] for attempt in attempts] if terminal else []
        deterministic = terminal and all(value == metrics[0] for value in metrics[1:])
        artifact_results.append({
            "artifact_id": artifact_id,
            "candidate_sha256": evaluations[0]["candidate_sha256"],
            "context_sha256": evaluations[0]["context_sha256"],
            "task": evaluations[0]["task"],
            "replicate_id": evaluations[0]["replicate_id"],
            "replay_evaluation_ids": [row["evaluation_id"] for row in evaluations],
            "terminal_replay_count": sum(
                _terminal_evaluation(attempt) for attempt in attempts
            ),
            "deterministic": deterministic if terminal else None,
            "stochastic_artifact": terminal and not deterministic,
            "confirmation_metrics": metrics[0] if deterministic else None,
            "replay_metrics": metrics if terminal else [
                attempt.get("metrics") if attempt else None for attempt in attempts
            ],
        })
    artifact_index = {row["artifact_id"]: row for row in artifact_results}
    document["artifact_results"] = artifact_results
    document["endpoint_results"] = [
        {
            **endpoint,
            "deduplicated_evaluation": sum(
                other["artifact_id"] == endpoint["artifact_id"]
                for other in endpoints
            ) > 1,
            "deterministic": artifact_index[endpoint["artifact_id"]]["deterministic"],
            "stochastic_artifact": artifact_index[endpoint["artifact_id"]][
                "stochastic_artifact"
            ],
            "metrics": artifact_index[endpoint["artifact_id"]][
                "confirmation_metrics"
            ],
        }
        for endpoint in endpoints
    ]
    terminal = {
        evaluation["evaluation_id"]: _terminal_evaluation(
            latest.get(evaluation["evaluation_id"])
        )
        for evaluation in document["planned_evaluations"]
    }
    stochastic_artifact_count = sum(
        row["stochastic_artifact"] for row in artifact_results
    )
    replay_cohort_complete = bool(terminal) and all(terminal.values())
    execution_passed = replay_cohort_complete and not stochastic_artifact_count
    document["completion"] = {
        "planned_unique_evaluations": len(terminal),
        "planned_unique_artifacts": len(by_artifact),
        "terminal_unique_evaluations": sum(terminal.values()),
        "incomplete_or_infrastructure_failed_evaluations": sum(
            not value for value in terminal.values()
        ),
        "attempt_count": len(document.get("attempts") or []),
        "deterministic_artifacts": sum(
            row["deterministic"] is True for row in artifact_results
        ),
        "stochastic_artifacts": stochastic_artifact_count,
        "candidate_invalid_deterministic_artifacts": sum(
            row["deterministic"] is True
            and float((row["confirmation_metrics"] or {}).get("valid", 0.0)) < 1.0
            for row in artifact_results
        ),
    }
    finalize_report_trust(document, execution_passed)
    document["analysis_gate"] = {
        "complete_failure_inclusive_endpoint_table": replay_cohort_complete,
        "all_unique_artifacts_deterministic": (
            replay_cohort_complete and stochastic_artifact_count == 0
        ),
        "candidate_invalidity_retained_as_scientific_outcome": True,
        "infrastructure_failures_require_resume": not replay_cohort_complete,
        "eligible_for_separate_preregistered_analysis": bool(
            document["trusted_evidence"]
        ),
        "runner_performs_hypothesis_test": False,
    }
    # Completion of fresh replay is a data-quality gate, not the primary
    # normal-versus-selection-blind hypothesis test.  Keep the scientific claim
    # boundary machine-readable so a green runner cannot be cited as an effect,
    # population, physical-validation or autonomous-discovery result.
    document["claims"] = {
        "fresh_confirmation_replay_cohort_complete": replay_cohort_complete,
        "preregistered_primary_hypothesis_test_completed": False,
        "feedback_causal_effect_identified": False,
        "population_effect_estimated": False,
        "independent_laboratory_or_physical_validation_completed": False,
        "autonomous_scientific_discovery_demonstrated": False,
    }


def run_confirmation(
    *,
    preregistration_path: Path,
    search_report_path: Path,
    private_contexts_path: Path,
    public_commitment_path: Path,
    output_path: Path,
    resume: bool,
    workers: int | None = None,
    command: list[str] | None = None,
) -> dict[str, Any]:
    preregistration, search, cells, design = _validate_preregistration_and_search(
        preregistration_path, search_report_path, public_commitment_path
    )
    contexts, public, panel_audits = _validate_context_artifacts(
        private_contexts_path, public_commitment_path, preregistration,
        design["tasks"], design["replicates"], design["source_binding"],
    )
    endpoints, evaluations, sources = _build_endpoint_plan(
        cells,
        contexts,
        design["budget"],
        design["confirmation_replays"],
        design["confirmation_randomization_seed"],
    )
    preregistered_workers = int(design.get("confirmation_workers", 1))
    effective_workers = preregistered_workers if workers is None else int(workers)
    if effective_workers < 1 or effective_workers != preregistered_workers:
        raise ValueError("confirmation worker count differs from preregistration")
    input_binding = {
        "preregistration": {
            "path": str(preregistration_path.resolve()),
            "sha256": _sha256(preregistration_path),
        },
        "search_report": {
            "path": str(search_report_path.resolve()),
            "sha256": _sha256(search_report_path),
        },
        "public_commitment": {
            "path": str(public_commitment_path.resolve()),
            "sha256": _sha256(public_commitment_path),
        },
        "private_manifest_sha256": hashlib.sha256(
            private_contexts_path.read_bytes()
        ).hexdigest(),
    }
    current_environment = {"python": sys.version, "platform": platform.platform()}
    parallelism = {
        "workers": effective_workers,
        "worker_isolation": "spawn_process",
        "submission_order": "planned_evaluations",
        "look_indices_assigned_before_dispatch": True,
        "completion_order_affects_analysis": False,
    }
    if resume:
        if not output_path.is_file():
            raise ValueError("--resume requires an existing confirmation report")
        document = json.loads(output_path.read_text(encoding="utf-8"))
        if not (
            document.get("input") == input_binding
            and document.get("environment") == current_environment
            and document.get("planned_endpoints") == endpoints
            and document.get("planned_evaluations") == evaluations
            and document.get("panel_audits") == panel_audits
            and document.get("confirmation_parallelism") == parallelism
        ):
            raise ValueError("confirmation resume inputs or plan differ")
    else:
        if output_path.exists():
            raise ValueError("refusing to overwrite confirmation report without --resume")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "schema_version": 1,
            "trust_status": "TRUSTED_SECURE_EVAL / FRESH_CONFIRMATION",
            "evidence_scope": (
                "PREREGISTERED_POST_SEARCH_FRESH_CONFIRMATION_NOT_BY_ITSELF_"
                "FEEDBACK_CAUSAL_POPULATION_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
            ),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_provenance": source_provenance(ROOT, command=command),
            "environment": current_environment,
            "input": input_binding,
            "search_gate": {
                "passed_before_private_context_read": True,
                "scheduled_cell_count": len(cells),
                "successful_cell_count": len(cells),
                "search_report_trusted": True,
                "search_report_execution_passed": True,
                "search_source_revision": (
                    search.get("source_provenance") or {}
                ).get("git_revision"),
                "presearch_prerequisites": design["prerequisite_audits"],
            },
            "private_reveal_gate": {
                "public_block_count": public["block_count"],
                "audited_block_count": len(panel_audits),
                "all_panels_audited_before_model_evaluation": True,
            },
            "panel_audits": panel_audits,
            "confirmation_parallelism": parallelism,
            "planned_endpoints": endpoints,
            "planned_evaluations": evaluations,
            "attempts": [],
        }
        _render_results(document, endpoints)
        atomic_write_text(
            output_path, json.dumps(document, indent=2, allow_nan=False) + "\n"
        )
    _validate_attempt_ledger(document, evaluations)
    latest = _latest_evaluation_attempts(document.get("attempts") or [])
    pending = []
    attempt_by_evaluation = {}
    for evaluation in evaluations:
        evaluation_id = evaluation["evaluation_id"]
        if _terminal_evaluation(latest.get(evaluation_id)):
            continue
        source = sources[evaluation["artifact_id"]]
        if sha256_text(source) != evaluation["candidate_sha256"]:
            raise ValueError("planned confirmation candidate source hash differs")
        started_at = datetime.now(timezone.utc).isoformat()
        prior_attempts = sum(
            attempt["evaluation_id"] == evaluation_id
            for attempt in document.get("attempts") or []
        )
        attempt = {
            "evaluation_id": evaluation_id,
            "attempt_index": prior_attempts + 1,
            "confirmation_look_index": len(document.get("attempts") or []) + 1,
            "artifact_id": evaluation["artifact_id"],
            "replay_index": evaluation["replay_index"],
            "task": evaluation["task"],
            "replicate_id": int(evaluation["replicate_id"]),
            "candidate_sha256": evaluation["candidate_sha256"],
            "context_sha256": evaluation["context_sha256"],
            "status": "started",
            "started_at": started_at,
            "completed_at": None,
            "wall_seconds": None,
            "metrics": None,
        }
        document.setdefault("attempts", []).append(attempt)
        latest[evaluation_id] = attempt
        attempt_by_evaluation[evaluation_id] = attempt
        pending.append({
            **evaluation,
            "source": source,
            "timeout": design["timeout"],
            "context": contexts[
                (evaluation["task"], int(evaluation["replicate_id"]))
            ],
        })

    # Write all attempt/look assignments before dispatching any worker.  If the
    # parent or host fails, resume retains those incomplete attempts and adds
    # explicit retry rows instead of silently replacing them.
    _render_results(document, endpoints)
    atomic_write_text(
        output_path, json.dumps(document, indent=2, allow_nan=False) + "\n"
    )

    def retain_result(result: dict[str, Any]) -> None:
        evaluation_id = result["evaluation_id"]
        attempt = attempt_by_evaluation[evaluation_id]
        attempt.update({
            "status": "completed",
            "completed_at": result["completed_at"],
            "wall_seconds": result["wall_seconds"],
            "metrics": result["metrics"],
        })
        _render_results(document, endpoints)
        atomic_write_text(
            output_path, json.dumps(document, indent=2, allow_nan=False) + "\n"
        )

    if effective_workers == 1:
        for payload in pending:
            retain_result(_evaluate_confirmation_worker(payload))
    elif pending:
        context = multiprocessing.get_context("spawn")
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=effective_workers, mp_context=context,
        ) as executor:
            future_payload = {
                executor.submit(_evaluate_confirmation_worker, payload): payload
                for payload in pending
            }
            for future in concurrent.futures.as_completed(future_payload):
                payload = future_payload[future]
                try:
                    result = future.result()
                except Exception:  # noqa: BLE001 - fixed infrastructure record
                    result = {
                        "evaluation_id": payload["evaluation_id"],
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "wall_seconds": 0.0,
                        "metrics": {
                            "combined_score": -1.0e18,
                            "valid": 0.0,
                            "error_message": (
                                "confirmation worker process failure"
                            ),
                            "infrastructure_failure": 1.0,
                        },
                    }
                retain_result(result)
    document["completed_at"] = datetime.now(timezone.utc).isoformat()
    _render_results(document, endpoints)
    atomic_write_text(
        output_path, json.dumps(document, indent=2, allow_nan=False) + "\n"
    )
    return document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--search-report", type=Path, required=True)
    parser.add_argument("--private-contexts", type=Path, required=True)
    parser.add_argument("--public-commitment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--workers", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(raw_argv)
    try:
        document = run_confirmation(
            preregistration_path=args.preregistration.expanduser().resolve(),
            search_report_path=args.search_report.expanduser().resolve(),
            private_contexts_path=args.private_contexts.expanduser().resolve(),
            public_commitment_path=args.public_commitment.expanduser().resolve(),
            output_path=args.output.expanduser().resolve(),
            resume=args.resume,
            workers=args.workers,
            command=[sys.executable, str(Path(__file__).resolve()), *raw_argv],
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps({
        "output": str(args.output.expanduser().resolve()),
        "execution_passed": document["execution_passed"],
        "trusted_evidence": document["trusted_evidence"],
        **document["completion"],
    }, indent=2))
    return 0 if document["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
