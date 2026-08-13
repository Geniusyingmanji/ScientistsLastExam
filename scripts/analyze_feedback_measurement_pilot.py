#!/usr/bin/env python3
"""Validate and summarize the four-condition feedback measurement pilot.

This analyzer is deliberately specific to the preregistered 16-cell pilot.  It
reconstructs every prompt/parent decision from the raw schema-v2 trajectories,
checks manifests and checkpoints, validates provider-token accounting, and
reports task-specific science axes at both proposal and common-token horizons.
The resulting contrasts are measurement-calibration diagnostics, not feedback-
causal or population-effect estimates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.algorithms.common import (  # noqa: E402
    feedback_scope,
    runtime_source_sha256,
    task_contract_sha256,
)
from sle.algorithms.evolve import (  # noqa: E402
    _build_prompt,
    SYSTEM_PROMPT,
)
from sle.metric_visibility import (  # noqa: E402
    score_only_metrics,
    search_visible_metrics,
)
from sle.protocol import (  # noqa: E402
    compact_trajectory_snapshot,
    load_trajectory,
    mean_confidence_interval,
    realized_token_curve,
    sha256_text,
    summarize_at_token_horizon,
    summarize_trajectory,
)
from sle.provenance import (  # noqa: E402
    SOURCE_SCOPE,
    finalize_report_trust,
    source_provenance,
)
from sle.registry import find_task  # noqa: E402


PREREGISTRATION = ".research/feedback_measurement_pilot_prereg_2026-07-26_v3.json"
PILOT_REPORT = "experiments/feedback_measurement_pilot_2026-07-26_v1.json"
EXPECTED_TASKS = (
    "DynamicalSystems/ActiveLawDiscovery",
    "Optics/DiffractionGratingDesign",
)
EXPECTED_MODES = (
    "normal", "score_only", "delayed_replay", "selection_blind",
)
EXPECTED_SEEDS = (0, 1)
EXPECTED_BUDGET = 3
EXPECTED_TIMEOUT = 300.0
EXPECTED_ALGORITHM = "greedy_rewrite"
EXPECTED_CELL_COUNT = 16
EXPECTED_LLM = {
    "wire": "responses",
    "model": "gpt-5.5",
    "max_output_tokens": 16000,
    "temperature": None,
    "reasoning_effort": "low",
    "server_side_seed_control": False,
}
TASK_SCIENCE_METRICS = {
    "DynamicalSystems/ActiveLawDiscovery": (
        "mechanism_score",
        "development_prediction_score",
        "validation_prediction_score",
        "robustness_score",
        "development_false_discoveries",
        "validation_false_discoveries",
        "development_correct_abstentions",
        "validation_correct_abstentions",
    ),
    "Optics/DiffractionGratingDesign": (
        "robustness_score",
        "heldout_policy_score",
        "heldout_robustness_score",
        "development_minimum_target_efficiency",
        "development_mean_target_efficiency",
        "heldout_minimum_target_efficiency",
        "heldout_mean_target_efficiency",
        "development_shift_geometry_feasibility",
        "heldout_shift_geometry_feasibility",
    ),
}
REQUIRED_FROZEN_FILES = (
    "scripts/batch_evolve.py",
    "scripts/analyze_feedback_measurement_pilot.py",
    "sle/algorithms/common.py",
    "sle/algorithms/evolve.py",
    "sle/metric_visibility.py",
    "sle/protocol.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: Any) -> str:
    rendered = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _git(args: list[str]) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL,
    ).rstrip("\r\n")


def _revision_is_source_equivalent(frozen: str, target: str) -> bool:
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", frozen, target],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0
    if not ancestor:
        return False
    changed = _git(["diff", "--name-only", frozen, target, "--", *SOURCE_SCOPE])
    return not bool(changed.strip())


def _git_file_sha256(revision: str, relative: str) -> str:
    payload = subprocess.check_output(
        ["git", "show", revision + ":" + relative], cwd=str(ROOT),
        stderr=subprocess.DEVNULL,
    )
    return hashlib.sha256(payload).hexdigest()


def _run_key(run: dict[str, Any]) -> str:
    return "%s|%s|%s|%d" % (
        run["task"], run["algorithm"], run["feedback_mode"], int(run["seed"]),
    )


def _latest_attempts(runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        latest[_run_key(run)] = run
    return latest


def _expected_keys() -> set[str]:
    return {
        "%s|%s|%s|%d" % (task, EXPECTED_ALGORITHM, mode, seed)
        for task in EXPECTED_TASKS
        for mode in EXPECTED_MODES
        for seed in EXPECTED_SEEDS
    }


def _observer_best_step(events: list[dict[str, Any]], through_step: int) -> int:
    """Return the first strict observer-side incumbent through ``through_step``."""

    if through_step < 0 or through_step >= len(events):
        raise ValueError("observer horizon is outside the trajectory")
    best_step = 0
    best_score = float(events[0]["score"])
    for event in events[1 : through_step + 1]:
        if bool(event["valid"]) and float(event["score"]) > best_score:
            best_step = int(event["step"])
            best_score = float(event["score"])
    return best_step


def _expected_prompt_state(
    events: list[dict[str, Any]], mode: str, step: int,
) -> tuple[int, int, dict[str, Any]]:
    if mode == "selection_blind":
        parent_step = 0
        released_through = 0
    elif mode == "delayed_replay":
        released_through = max(0, step - 2)
        parent_step = _observer_best_step(events, released_through)
    else:
        released_through = step - 1
        parent_step = _observer_best_step(events, step - 1)
    metrics = search_visible_metrics(events[parent_step].get("metrics") or {})
    if mode == "score_only":
        metrics = score_only_metrics(metrics)
    return parent_step, released_through, metrics


def _source_rows(
    events: list[dict[str, Any]], checkpoint: dict[str, Any], baseline_source: str,
) -> dict[int, str]:
    sources = {0: baseline_source}
    rows = checkpoint.get("evaluated_candidates") or []
    if len(rows) < 1 or int(rows[0].get("step", -1)) != 0:
        raise ValueError("checkpoint lacks the baseline evaluated-candidate row")
    seen_steps = set()
    for row in rows:
        step = int(row.get("step", -1))
        if step in seen_steps or step < 0 or step >= len(events):
            raise ValueError("checkpoint evaluated-candidate steps are invalid")
        seen_steps.add(step)
        source = str(row.get("program", ""))
        source_hash = sha256_text(source)
        if source_hash != row.get("sha256"):
            raise ValueError("checkpoint evaluated-candidate source hash differs")
        if source_hash != events[step].get("candidate_sha256"):
            raise ValueError("checkpoint source does not bind its trajectory event")
        if search_visible_metrics(events[step].get("metrics") or {}) != row.get("metrics"):
            raise ValueError("checkpoint search metrics differ from trajectory metrics")
        sources[step] = source
    if sources[0] != baseline_source:
        raise ValueError("checkpoint baseline source differs from task baseline")
    for event in events[1:]:
        step = int(event["step"])
        if event.get("candidate_sha256") and step not in sources:
            raise ValueError("parsed trajectory candidate source is not retained")
        if not event.get("candidate_sha256") and step in sources:
            raise ValueError("empty candidate event unexpectedly retains source")
    return sources


def _validate_lineage_and_prompts(
    events: list[dict[str, Any]], checkpoint: dict[str, Any], spec: Any,
    mode: str, budget: int,
) -> dict[str, Any]:
    """Reconstruct every parent, metric payload, and full prompt hash."""

    if mode not in EXPECTED_MODES:
        raise ValueError("unexpected feedback mode")
    baseline_source = spec.initial_program_path.read_text(encoding="utf-8")
    sources = _source_rows(events, checkpoint, baseline_source)
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if mode == "selection_blind"
        else "delayed_online_parent_offline_final_best"
        if mode == "delayed_replay"
        else "online_incumbent"
    )
    expected_semantics = (
        "offline_best_update"
        if mode == "selection_blind"
        else "observer_best_update_not_immediate_parent_release"
        if mode == "delayed_replay"
        else "online_incumbent_update"
    )
    prompt_records = []
    prior_best = float(events[0]["score"])
    for event in events[1:]:
        step = int(event["step"])
        parent_step, released_through, metrics = _expected_prompt_state(
            events, mode, step,
        )
        parent_source = sources[parent_step]
        metadata = event.get("algorithm_metadata") or {}
        metrics_rendered = json.dumps(metrics, indent=2)
        prompt = _build_prompt(
            spec, parent_source, metrics,
            proposal_slot=step, proposal_budget=budget,
        )
        expected = {
            "selection_policy": expected_policy,
            "accepted_semantics": expected_semantics,
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
            raise ValueError("trajectory prompt/lineage metadata differs at step %d" % step)
        if event.get("parent_sha256") != sha256_text(parent_source):
            raise ValueError("trajectory parent source hash differs at step %d" % step)
        expected_accepted = bool(
            event.get("valid") and float(event["score"]) > prior_best
        )
        if bool(event.get("accepted")) != expected_accepted:
            raise ValueError("trajectory accepted flag differs at step %d" % step)
        if expected_accepted:
            prior_best = float(event["score"])
        prompt_records.append({
            "step": step,
            "parent_step": parent_step,
            "parent_sha256": event["parent_sha256"],
            "released_through_step": released_through,
            "prompt_sha256": metadata["prompt_sha256"],
            "prompt_utf8_bytes": metadata["prompt_utf8_bytes"],
            "prompt_program_utf8_bytes": metadata["prompt_program_utf8_bytes"],
            "prompt_metrics_sha256": metadata["prompt_metrics_sha256"],
            "prompt_metrics_utf8_bytes": metadata["prompt_metrics_utf8_bytes"],
            "prompt_metric_keys": metadata["prompt_metric_keys"],
            "system_prompt_sha256": sha256_text(SYSTEM_PROMPT),
        })
    return {
        "selection_policy": expected_policy,
        "accepted_semantics": expected_semantics,
        "prompt_records": prompt_records,
        "sources": sources,
    }


def _selected_record(
    events: list[dict[str, Any]], through_step: int,
) -> dict[str, Any]:
    best_source_step = _observer_best_step(events, through_step)
    event = events[best_source_step]
    return {
        "completed_through_step": through_step,
        "best_source_step": best_source_step,
        "candidate_sha256": event["candidate_sha256"],
        "best_score": float(event["score"]),
        "science_metrics": dict(event.get("metrics") or {}),
    }


def _load_preregistration(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    design = document.get("design") or {}
    source = document.get("frozen_source") or {}
    model = document.get("model_condition") or {}
    tasks = design.get("tasks") or []
    task_ids = [row.get("task") for row in tasks]
    task_hashes = {row.get("task"): row.get("task_contract_sha256") for row in tasks}
    file_hashes = source.get("file_sha256") or {}
    if not (
        document.get("schema_version") == 1
        and document.get("preregistration_version") == 3
        and document.get("purpose") == "feedback_measurement_calibration_pilot"
        and document.get("claim_limit")
        == "descriptive_measurement_calibration_not_feedback_causal"
        and task_ids == list(EXPECTED_TASKS)
        and design.get("algorithm") == EXPECTED_ALGORITHM
        and design.get("feedback_modes") == list(EXPECTED_MODES)
        and design.get("replicate_identifiers") == list(EXPECTED_SEEDS)
        and design.get("proposal_budget") == EXPECTED_BUDGET
        and float(design.get("evaluator_timeout_seconds", -1)) == EXPECTED_TIMEOUT
        and design.get("scheduled_cell_count") == EXPECTED_CELL_COUNT
        and set(task_hashes) == set(EXPECTED_TASKS)
        and source.get("revision")
        and source.get("runtime_source_sha256")
        and set(REQUIRED_FROZEN_FILES).issubset(file_hashes)
        and all(model.get(key) == value for key, value in EXPECTED_LLM.items())
        and isinstance(model.get("llm_condition_sha256"), str)
        and len(model["llm_condition_sha256"]) == 64
    ):
        raise ValueError("feedback measurement preregistration contract differs")
    frozen_revision = source["revision"]
    if not all(
        _git_file_sha256(frozen_revision, relative) == file_hashes[relative]
        for relative in REQUIRED_FROZEN_FILES
    ):
        raise ValueError("preregistered frozen file hash differs from Git revision")
    for task in EXPECTED_TASKS:
        spec = find_task(task, include_uncertified=True)
        if task_contract_sha256(spec) != task_hashes[task]:
            raise ValueError("current task contract differs from preregistration")
    if runtime_source_sha256() != source["runtime_source_sha256"]:
        raise ValueError("current runtime source differs from preregistration")
    return document


def _validate_source_provenance(
    provenance: dict[str, Any], frozen_revision: str, label: str,
) -> str:
    revision = provenance.get("git_revision")
    if not (
        provenance.get("git_available") is True
        and isinstance(revision, str)
        and revision not in {"", "unknown"}
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and _revision_is_source_equivalent(frozen_revision, revision)
    ):
        raise ValueError("%s source provenance is not frozen-source equivalent" % label)
    return revision


def _preregistration_binding(config: dict[str, Any], path: Path) -> bool:
    bound = config.get("preregistration") or {}
    try:
        expected_path = str(path.resolve().relative_to(ROOT))
    except ValueError:
        expected_path = str(path.resolve())
    return bool(
        bound.get("path") == expected_path
        and bound.get("sha256") == _sha256(path)
        and bound.get("bytes") == len(path.read_bytes())
    )


def _validate_full_suite(
    preregistration: dict[str, Any], frozen_revision: str,
) -> dict[str, Any]:
    contract = (preregistration.get("prerequisites") or {}).get("full_test_suite") or {}
    path = ROOT / str(contract.get("path", ""))
    document = json.loads(path.read_text(encoding="utf-8"))
    revision = _validate_source_provenance(
        document.get("source_provenance") or {}, frozen_revision, "full suite",
    )
    if not (
        document.get("schema_version") == 1
        and document.get("trust_status") == "TRUSTED_FULL_TEST_SUITE"
        and document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and document.get("unittest_ok") is True
        and document.get("returncode") == 0
        and int(document.get("test_count", 0)) >= int(contract.get("minimum_test_count", 0))
    ):
        raise ValueError("preregistered full-suite prerequisite did not pass")
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": _sha256(path),
        "source_revision": revision,
        "test_count": int(document["test_count"]),
        "wall_seconds": float(document["wall_seconds"]),
    }


def _validate_smoke(
    preregistration: dict[str, Any], prereg_path: Path, frozen_revision: str,
) -> dict[str, Any]:
    contract = (preregistration.get("prerequisites") or {}).get("protocol_smoke") or {}
    path = ROOT / str(contract.get("path", ""))
    document = json.loads(path.read_text(encoding="utf-8"))
    revision = _validate_source_provenance(
        document.get("source_provenance") or {}, frozen_revision, "protocol smoke",
    )
    config = document.get("config") or {}
    latest = _latest_attempts(document.get("runs") or [])
    expected_smoke_keys = {
        "%s|%s|%s|%d" % (
            contract["task"], EXPECTED_ALGORITHM, mode, seed,
        )
        for mode in EXPECTED_MODES for seed in EXPECTED_SEEDS
    }
    if not (
        document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and config.get("tasks") == [contract["task"]]
        and config.get("algorithms") == [EXPECTED_ALGORITHM]
        and config.get("feedback_modes") == list(EXPECTED_MODES)
        and config.get("seeds") == list(EXPECTED_SEEDS)
        and config.get("budget") == 0
        and config.get("trajectory_snapshot_schema_version") == 2
        and config.get("llm_condition_sha256")
        == preregistration["model_condition"]["llm_condition_sha256"]
        and _preregistration_binding(config, prereg_path)
        and set(latest) == expected_smoke_keys
        and all(not run.get("error") for run in latest.values())
        and all(
            (run.get("trajectory_snapshot") or {}).get("schema_version") == 2
            and len((run.get("trajectory_snapshot") or {}).get("events") or []) == 1
            and (run.get("trajectory_snapshot") or {})["events"][0].get(
                "schema_version"
            ) == 2
            for run in latest.values()
        )
    ):
        raise ValueError("preregistered protocol smoke did not pass")
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": _sha256(path),
        "source_revision": revision,
        "successful_cells": len(latest),
    }


def _validate_pilot_config(
    document: dict[str, Any], preregistration: dict[str, Any], prereg_path: Path,
) -> tuple[dict[str, Any], str]:
    source = preregistration["frozen_source"]
    revision = _validate_source_provenance(
        document.get("source_provenance") or {}, source["revision"], "pilot",
    )
    config = document.get("config") or {}
    model = config.get("llm") or {}
    if not (
        document.get("schema_version") == 1
        and document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and config.get("tasks") == list(EXPECTED_TASKS)
        and config.get("algorithms") == [EXPECTED_ALGORITHM]
        and config.get("feedback_modes") == list(EXPECTED_MODES)
        and config.get("trajectory_snapshot_schema_version") == 2
        and config.get("condition_order")
        == "as_listed_for_even_seeds_reversed_for_odd_seeds"
        and config.get("seeds") == list(EXPECTED_SEEDS)
        and config.get("budget") == EXPECTED_BUDGET
        and float(config.get("timeout_s", -1)) == EXPECTED_TIMEOUT
        and config.get("llm_condition_sha256")
        == preregistration["model_condition"]["llm_condition_sha256"]
        and all(model.get(key) == value for key, value in EXPECTED_LLM.items())
        and _preregistration_binding(config, prereg_path)
    ):
        raise ValueError("pilot report configuration differs from preregistration")
    return config, revision


def _load_run(
    run: dict[str, Any], config: dict[str, Any], preregistration: dict[str, Any],
) -> dict[str, Any]:
    task = str(run["task"])
    mode = str(run["feedback_mode"])
    seed = int(run["seed"])
    spec = find_task(task, include_uncertified=True)
    workdir = Path(run["workdir"]).resolve()
    work_root = Path(config["work_root"]).resolve()
    expected_workdir = (
        work_root / task.replace("/", "__") / EXPECTED_ALGORITHM / mode
        / ("seed_%d" % seed)
    ).resolve()
    try:
        workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("pilot workdir is outside repository") from exc
    if workdir != expected_workdir:
        raise ValueError("pilot workdir differs from scheduled cell")
    paths = {
        name: workdir / name for name in (
            "trajectory.jsonl", "checkpoint.json", "summary.json",
            "run_manifest.json", "best_program.py", "solution.py",
        )
    }
    if not all(path.is_file() for path in paths.values()):
        raise ValueError("pilot run is missing a required retained artifact")
    events = load_trajectory(paths["trajectory.jsonl"])
    snapshot = compact_trajectory_snapshot(
        paths["trajectory.jsonl"], schema_version=2,
    )
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("raw and portable pilot trajectories differ")
    if len(events) != EXPECTED_BUDGET + 1:
        raise ValueError("pilot trajectory does not contain three proposal slots")
    checkpoint = json.loads(paths["checkpoint.json"].read_text(encoding="utf-8"))
    summary_file = json.loads(paths["summary.json"].read_text(encoding="utf-8"))
    manifest = json.loads(paths["run_manifest.json"].read_text(encoding="utf-8"))
    if summary_file != run.get("summary"):
        raise ValueError("retained summary differs from outer pilot report")
    expected_summary = summarize_trajectory(events, budget=EXPECTED_BUDGET + 1)
    if any(summary_file.get(key) != value for key, value in expected_summary.items()):
        raise ValueError("pilot summary accounting differs from trajectory")
    task_contracts = {
        row["task"]: row["task_contract_sha256"]
        for row in preregistration["design"]["tasks"]
    }
    if not (
        manifest.get("schema_version") == 1
        and manifest.get("algorithm") == EXPECTED_ALGORITHM
        and manifest.get("task_id") == task
        and manifest.get("task_contract_sha256") == task_contracts[task]
        and manifest.get("runtime_source_sha256")
        == preregistration["frozen_source"]["runtime_source_sha256"]
        and manifest.get("seed") == seed
        and manifest.get("feedback_mode") == mode
        and manifest.get("feedback_scope") == feedback_scope(mode)
        and manifest.get("llm_condition_sha256")
        == preregistration["model_condition"]["llm_condition_sha256"]
    ):
        raise ValueError("pilot run manifest differs from frozen condition")
    lineage = _validate_lineage_and_prompts(
        events, checkpoint, spec, mode, EXPECTED_BUDGET,
    )
    best_step = _observer_best_step(events, EXPECTED_BUDGET)
    best_source = lineage["sources"][best_step]
    terminal_step = max(lineage["sources"])
    terminal_source = lineage["sources"][terminal_step]
    if not (
        checkpoint.get("schema_version") == 1
        and checkpoint.get("task_id") == task
        and checkpoint.get("seed") == seed
        and checkpoint.get("next_iter") == EXPECTED_BUDGET + 1
        and checkpoint.get("best_source_step") == best_step
        and checkpoint.get("best_sha256") == sha256_text(best_source)
        and checkpoint.get("best_program") == best_source
        and paths["best_program.py"].read_text(encoding="utf-8") == best_source
        and paths["solution.py"].read_text(encoding="utf-8") == terminal_source
        and float(run["baseline"]) == float(events[0]["score"])
        and float(run["best"]) == float(events[best_step]["score"])
        and int(run["accepted"]) == sum(bool(row["accepted"]) for row in events[1:])
        and int(run["evaluated"]) == int(events[-1]["oracle_calls"])
        and summary_file.get("selection_policy") == lineage["selection_policy"]
    ):
        raise ValueError("pilot checkpoint/best-program binding differs")

    curve = realized_token_curve(events)
    total_tokens = int(curve[-1]["cumulative_tokens"])
    llm_summary = summary_file.get("llm") or {}
    if not (
        llm_summary.get("calls") == EXPECTED_BUDGET
        and llm_summary.get("provider_usage_records") == EXPECTED_BUDGET
        and llm_summary.get("total_tokens") == total_tokens
        and all(
            _finite_number((event.get("llm") or {}).get(key))
            for event in events[1:]
            for key in ("input_tokens", "output_tokens", "total_tokens")
        )
    ):
        raise ValueError("pilot provider token accounting is incomplete")
    selected = _selected_record(events, EXPECTED_BUDGET)
    missing = [
        metric for metric in TASK_SCIENCE_METRICS[task]
        if metric not in selected["science_metrics"]
        or not _finite_number(selected["science_metrics"][metric])
    ]
    if missing:
        raise ValueError("selected pilot event lacks science axes: %s" % ", ".join(missing))
    return {
        "task": task,
        "condition": mode,
        "replicate_id": seed,
        "algorithm": EXPECTED_ALGORITHM,
        "workdir": str(workdir.relative_to(ROOT)),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "manifest_sha256": _sha256(paths["run_manifest.json"]),
        "checkpoint_sha256": _sha256(paths["checkpoint.json"]),
        "summary_sha256": _sha256(paths["summary.json"]),
        "best_program_sha256": _sha256(paths["best_program.py"]),
        "terminal_program_sha256": _sha256(paths["solution.py"]),
        "terminal_source_step": terminal_step,
        "events": events,
        "prompt_records": lineage["prompt_records"],
        "proposal_count": EXPECTED_BUDGET,
        "valid_proposal_count": sum(bool(row["valid"]) for row in events[1:]),
        "invalid_proposal_count": sum(not bool(row["valid"]) for row in events[1:]),
        "oracle_calls": int(summary_file["oracle_calls"]),
        "best_so_far_auc": float(summary_file["best_so_far_auc"]),
        "input_tokens": int(llm_summary["input_tokens"]),
        "output_tokens": int(llm_summary["output_tokens"]),
        "total_tokens": total_tokens,
        "prompt_utf8_bytes": sum(
            int(row["prompt_utf8_bytes"]) for row in lineage["prompt_records"]
        ),
        "full_horizon": {
            **{key: value for key, value in selected.items() if key != "science_metrics"},
            "best_so_far_auc": float(summary_file["best_so_far_auc"]),
            "science_metrics": {
                metric: selected["science_metrics"][metric]
                for metric in TASK_SCIENCE_METRICS[task]
            },
        },
    }


def _token_horizon_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_pair: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for record in records:
        by_pair.setdefault(
            (record["task"], int(record["replicate_id"])), []
        ).append(record)
    output = []
    for (task, replicate_id), group in sorted(by_pair.items()):
        if {row["condition"] for row in group} != set(EXPECTED_MODES):
            raise ValueError("common-token group lacks one feedback condition")
        horizon = min(int(row["total_tokens"]) for row in group)
        cells = []
        for row in sorted(group, key=lambda item: EXPECTED_MODES.index(item["condition"])):
            summary = summarize_at_token_horizon(row["events"], horizon)
            completed_step = int(summary["selected_step"])
            selected = _selected_record(row["events"], completed_step)
            cells.append({
                "condition": row["condition"],
                **summary,
                "best_source_step": selected["best_source_step"],
                "candidate_sha256": selected["candidate_sha256"],
                "science_metrics": {
                    metric: selected["science_metrics"][metric]
                    for metric in TASK_SCIENCE_METRICS[task]
                },
            })
        output.append({
            "task": task,
            "replicate_id": replicate_id,
            "common_total_token_horizon": horizon,
            "cells": cells,
        })
    return output


def _difference(left: dict[str, Any], right: dict[str, Any], task: str) -> dict[str, float]:
    result = {
        "best_score": float(left["best_score"]) - float(right["best_score"]),
    }
    if "best_so_far_auc" in left and "best_so_far_auc" in right:
        result["best_so_far_auc"] = (
            float(left["best_so_far_auc"]) - float(right["best_so_far_auc"])
        )
    if "best_so_far_token_auc" in left and "best_so_far_token_auc" in right:
        result["best_so_far_token_auc"] = (
            float(left["best_so_far_token_auc"])
            - float(right["best_so_far_token_auc"])
        )
    result.update({
        metric: (
            float(left["science_metrics"][metric])
            - float(right["science_metrics"][metric])
        )
        for metric in TASK_SCIENCE_METRICS[task]
    })
    return result


def _contrasts(
    records: list[dict[str, Any]], token_records: list[dict[str, Any]],
) -> dict[str, Any]:
    full = {
        (row["task"], int(row["replicate_id"]), row["condition"]): row["full_horizon"]
        for row in records
    }
    token = {
        (group["task"], int(group["replicate_id"]), cell["condition"]): cell
        for group in token_records for cell in group["cells"]
    }
    rows = []
    for task in EXPECTED_TASKS:
        for seed in EXPECTED_SEEDS:
            for control in EXPECTED_MODES[1:]:
                rows.append({
                    "task": task,
                    "replicate_id": seed,
                    "contrast": "normal_minus_" + control,
                    "configured_proposal_horizon": _difference(
                        full[(task, seed, "normal")], full[(task, seed, control)], task,
                    ),
                    "common_total_token_horizon": _difference(
                        token[(task, seed, "normal")], token[(task, seed, control)], task,
                    ),
                })
    summaries: dict[str, Any] = {}
    for task in EXPECTED_TASKS:
        summaries[task] = {}
        for control in EXPECTED_MODES[1:]:
            selected = [
                row for row in rows
                if row["task"] == task and row["contrast"] == "normal_minus_" + control
            ]
            configured_fields = selected[0]["configured_proposal_horizon"]
            token_fields = selected[0]["common_total_token_horizon"]
            summaries[task]["normal_minus_" + control] = {
                "configured_proposal_horizon": {
                    field: mean_confidence_interval(
                        row["configured_proposal_horizon"][field] for row in selected
                    )
                    for field in configured_fields
                },
                "common_total_token_horizon": {
                    field: mean_confidence_interval(
                        row["common_total_token_horizon"][field] for row in selected
                    )
                    for field in token_fields
                },
            }
    return {"paired_descriptive_contrasts": rows, "diagnostic_summaries": summaries}


def analyze(
    pilot_path: Path = ROOT / PILOT_REPORT,
    preregistration_path: Path = ROOT / PREREGISTRATION,
) -> dict[str, Any]:
    preregistration_path = preregistration_path.resolve()
    pilot_path = pilot_path.resolve()
    preregistration = _load_preregistration(preregistration_path)
    frozen_revision = preregistration["frozen_source"]["revision"]
    full_suite = _validate_full_suite(preregistration, frozen_revision)
    smoke = _validate_smoke(
        preregistration, preregistration_path, frozen_revision,
    )
    document = json.loads(pilot_path.read_text(encoding="utf-8"))
    config, pilot_revision = _validate_pilot_config(
        document, preregistration, preregistration_path,
    )
    runs = document.get("runs") or []
    latest = _latest_attempts(runs)
    if set(latest) != _expected_keys() or any(run.get("error") for run in latest.values()):
        raise ValueError("pilot latest-attempt risk set is incomplete")
    records = [_load_run(latest[key], config, preregistration) for key in sorted(latest)]
    token_records = _token_horizon_records(records)
    contrasts = _contrasts(records, token_records)
    task_ranges = {}
    for task in EXPECTED_TASKS:
        scores = [
            float(row["full_horizon"]["best_score"])
            for row in records if row["task"] == task
        ]
        task_ranges[task] = {
            "minimum": min(scores),
            "maximum": max(scores),
            "range": max(scores) - min(scores),
            "has_interior_score": any(0.01 < score < 0.99 for score in scores),
            "passes_non_saturated_variation_gate": bool(
                max(scores) - min(scores)
                >= float(preregistration["analysis"]["minimum_score_range"])
                and any(0.01 < score < 0.99 for score in scores)
            ),
        }
    failed_attempt_count = sum(bool(run.get("error")) for run in runs)
    recovered_cells = sum(
        not latest[key].get("error")
        and any(
            attempt.get("error") for attempt in runs if _run_key(attempt) == key
        )
        for key in latest
    )
    gate = {
        "scheduled_cell_count": EXPECTED_CELL_COUNT,
        "successful_terminal_cell_count": len(records),
        "terminal_failed_cell_count": 0,
        "attempt_count": len(runs),
        "failed_attempt_count": failed_attempt_count,
        "recovered_cell_count": recovered_cells,
        "all_lineage_and_prompt_contracts_passed": True,
        "all_provider_usage_complete": True,
        "task_score_ranges": task_ranges,
        "at_least_one_task_has_non_saturated_variation": any(
            row["passes_non_saturated_variation_gate"]
            for row in task_ranges.values()
        ),
    }
    gate["may_design_later_track_f_study"] = bool(
        gate["successful_terminal_cell_count"] == EXPECTED_CELL_COUNT
        and gate["terminal_failed_cell_count"] == 0
        and gate["all_lineage_and_prompt_contracts_passed"]
        and gate["all_provider_usage_complete"]
        and gate["at_least_one_task_has_non_saturated_variation"]
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "SIXTEEN_CELL_FEEDBACK_MEASUREMENT_CALIBRATION_PILOT_"
            "DESCRIPTIVE_NOT_FEEDBACK_CAUSAL_POPULATION_MODEL_RANKING_"
            "OR_AUTONOMOUS_SCIENTIFIC_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "preregistration": {
            "path": str(preregistration_path.relative_to(ROOT)),
            "sha256": _sha256(preregistration_path),
            "frozen_source_revision": frozen_revision,
        },
        "prerequisites": {
            "full_test_suite": full_suite,
            "protocol_smoke": smoke,
        },
        "input": {
            "path": str(pilot_path.relative_to(ROOT)),
            "sha256": _sha256(pilot_path),
            "source_revision": pilot_revision,
            "attempt_count": len(runs),
        },
        "design": preregistration["design"],
        "cell_records": [
            {key: value for key, value in row.items() if key != "events"}
            for row in records
        ],
        "common_total_token_horizons": token_records,
        **contrasts,
        "pilot_gate": gate,
        "claims": {
            "measurement_pipeline_calibrated": True,
            "feedback_causal_effect_identified": False,
            "population_effect_estimated": False,
            "cross_task_science_score_defined": False,
            "model_ranking_supported": False,
            "autonomous_scientific_discovery_demonstrated": False,
        },
        "limitations": [
            "Each task-condition cell has only two local replicate identifiers.",
            "The Azure endpoint exposes no server-side generation seed, so equal local identifiers do not pair model randomness.",
            "Prompt lengths, generated tokens and wall time are measured rather than assumed matched.",
            "Task-specific science axes are kept separate and are not averaged into one cross-task discovery score.",
            "The tasks use public finite or simulated worlds and do not provide prospective independent scientific validation.",
            "Any later feedback claim requires a separately preregistered repeated cohort with at least ten independent runs per condition, fresh or server-held worlds, and independent scientific validation.",
        ],
    }
    finalize_report_trust(report, True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", type=Path, default=ROOT / PILOT_REPORT)
    parser.add_argument(
        "--preregistration", type=Path, default=ROOT / PREREGISTRATION,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.pilot, args.preregistration)
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(json.dumps({
        "execution_passed": report["execution_passed"],
        "trusted_evidence": report["trusted_evidence"],
        "scheduled_cells": report["pilot_gate"]["scheduled_cell_count"],
        "successful_cells": report["pilot_gate"]["successful_terminal_cell_count"],
        "may_design_later_track_f_study": report["pilot_gate"][
            "may_design_later_track_f_study"
        ],
    }, indent=2))
    print("Report: %s" % args.output.resolve())
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
