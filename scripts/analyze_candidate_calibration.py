#!/usr/bin/env python3
"""Analyze preregistered budget-prefix candidate calibrations.

The first attempt is the primary intent-to-evaluate analysis.  A separate
latest-attempt view shows transparent infrastructure recovery without erasing
the originally observed failures or blocked cells.
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

from sle.protocol import compact_trajectory_snapshot  # noqa: E402
from sle.provenance import (  # noqa: E402
    SOURCE_SCOPE,
    finalize_report_trust,
    source_provenance,
)
from sle.run_verification import verify_run  # noqa: E402
from sle.runtime_identity import validate_runtime_descriptor  # noqa: E402
from scripts.batch_evolve import (  # noqa: E402
    _csv,
    _execution_preregistration_is_committed,
    _safe_batch_cell_paths,
    build_parser,
)


REQUIRED_TASK_BINDING_FIELDS = (
    "task_contract_sha256",
    "task_package_sha256",
    "task_card_sha256",
    "runtime_source_sha256",
    "task_family_id",
    "wave_id",
    "wave_manifest_sha256",
    "trusted_evaluator_runtime",
    "trusted_evaluator_runtime_sha256",
)

REQUIRED_READABLE_MODEL_FIELDS = {
    "wire",
    "endpoint_sha256",
    "model",
    "max_output_tokens",
    "temperature",
    "reasoning_effort",
    "provider_request_timeout_seconds",
    "stream",
    "chat_max_tokens_field",
    "chat_reasoning_fallback",
    "server_side_seed_control",
}

CANDIDATE_CALIBRATION_CLAIM_LIMIT = (
    "candidate_calibration_only_not_hardness_certification_or_model_ranking_"
    "or_causal_feedback_evidence"
)

SCIENCE_METRIC_VALUE_TYPES = {"numeric", "boolean"}
SCIENCE_METRIC_DIRECTIONS = {
    "higher_is_better",
    "lower_is_better",
    "descriptive",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_key(run: dict[str, Any]) -> tuple[str, str, str, int]:
    seed = run.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("run cell identity is invalid")
    if not all(
        isinstance(run.get(field), str) and run.get(field)
        for field in ("task", "algorithm", "feedback_mode")
    ):
        raise ValueError("run cell identity is invalid")
    return (
        run["task"],
        run["algorithm"],
        run["feedback_mode"],
        seed,
    )


def _recorded_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def _is_sha256(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_cohort_semantics(
    cohort: dict[str, Any],
    source_cohort: dict[str, Any],
    task_rows: list[dict[str, Any]],
    analysis_role: str,
) -> None:
    if cohort.get("schema_version") != 1:
        raise ValueError("preregistered cohort schema is unsupported")
    if analysis_role != "candidate_calibration":
        raise ValueError("preregistered analysis role is not candidate calibration")
    if not (
        cohort.get("analysis_role") == analysis_role
        and source_cohort.get("analysis_role") == analysis_role
    ):
        raise ValueError("preregistered cohort analysis role differs")
    claim_limit = source_cohort.get("claim_limit")
    if claim_limit != CANDIDATE_CALIBRATION_CLAIM_LIMIT or (
        cohort.get("claim_limit") != CANDIDATE_CALIBRATION_CLAIM_LIMIT
    ):
        raise ValueError("preregistered cohort claim limit differs")
    selection = cohort.get("selection")
    if not isinstance(selection, dict) or (
        selection.get("confirmatory_reuse_permitted") is not False
    ):
        raise ValueError("preregistered cohort permits confirmatory reuse")
    cohort_rows = cohort.get("tasks")
    if not isinstance(cohort_rows, list) or [
        row.get("task") if isinstance(row, dict) else None
        for row in cohort_rows
    ] != [row["task"] for row in task_rows]:
        raise ValueError("preregistered cohort task order differs")
    for cohort_row, task_row in zip(cohort_rows, task_rows):
        expected = {
            "runtime_contract_sha256": task_row["task_contract_sha256"],
            "task_card_sha256": task_row["task_card_sha256"],
            "maturity_contract_sha256": task_row["maturity_contract_sha256"],
        }
        if any(
            not _is_sha256(value) or cohort_row.get(field) != value
            for field, value in expected.items()
        ):
            raise ValueError(
                "preregistered cohort task binding differs for %s"
                % task_row["task"]
            )


def _validate_preregistered_command(
    preregistration: dict[str, Any],
    preregistration_path: Path,
    report_path: Path,
    report: dict[str, Any],
    tasks: list[str],
    modes: list[str],
    seeds: list[int],
    budget: int,
    cohort_path: Path,
) -> None:
    if not _execution_preregistration_is_committed(preregistration_path):
        raise ValueError("execution preregistration is not committed at HEAD")
    provenance = report.get("source_provenance") or {}
    source_revision = provenance.get("git_revision")
    if not (
        isinstance(source_revision, str)
        and len(source_revision) in {40, 64}
        and all(character in "0123456789abcdef" for character in source_revision)
    ):
        raise ValueError("parent report source revision is invalid")
    relative_preregistration = preregistration_path.relative_to(ROOT).as_posix()
    try:
        source_blob = subprocess.check_output(
            ["git", "show", "%s:%s" % (source_revision, relative_preregistration)],
            cwd=str(ROOT),
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(
            "execution preregistration did not exist at the report revision"
        ) from exc
    if source_blob != preregistration_path.read_bytes():
        raise ValueError("execution preregistration differs at report revision")
    command = (preregistration.get("design") or {}).get("primary_command")
    if not (
        isinstance(command, list)
        and len(command) >= 2
        and all(isinstance(value, str) for value in command)
        and (ROOT / command[1]).resolve()
        == (ROOT / "scripts" / "batch_evolve.py").resolve()
    ):
        raise ValueError("preregistered primary command is invalid")
    try:
        parsed = build_parser().parse_args(command[2:])
    except SystemExit as exc:
        raise ValueError("preregistered primary command does not parse") from exc
    config = report.get("config") or {}
    expected = {
        "tasks": tasks,
        "algorithms": ["greedy_rewrite"],
        "feedback_modes": modes,
        "seeds": seeds,
        "budget": budget,
        "timeout": config.get("timeout_s"),
        "condition_order_design": config.get("condition_order"),
        "block_workers": config.get("block_workers"),
        "run_role": "calibration",
        "active_wall_horizon": config.get("active_wall_horizon_s"),
        "sentinel_interval": config.get("sentinel_interval_s"),
        "signed_decisions": config.get("signed_decisions"),
        "signed_decision_policy": config.get("signed_decision_policy"),
        "condition_order_randomization_seed": config.get(
            "condition_order_randomization_seed"
        ),
    }
    actual = {
        "tasks": _csv(parsed.tasks or ""),
        "algorithms": _csv(parsed.algorithms),
        "feedback_modes": _csv(parsed.feedback_modes),
        "seeds": parsed.seeds,
        "budget": parsed.budget,
        "timeout": parsed.timeout,
        "condition_order_design": parsed.condition_order_design,
        "block_workers": parsed.block_workers,
        "run_role": parsed.run_role,
        "active_wall_horizon": parsed.active_wall_horizon,
        "sentinel_interval": parsed.sentinel_interval,
        "signed_decisions": parsed.signed_decisions,
        "signed_decision_policy": parsed.signed_decision_policy,
        "condition_order_randomization_seed": (
            parsed.condition_order_randomization_seed
        ),
    }
    if actual != expected or parsed.all is not True or parsed.resume is True:
        raise ValueError("preregistered primary command axes differ")
    bound_paths = (
        (parsed.preregistration, preregistration_path, "preregistration"),
        (parsed.cohort_manifest, cohort_path, "cohort"),
        (parsed.output, report_path, "output"),
    )
    for declared, expected_path, label in bound_paths:
        if declared is None:
            raise ValueError("preregistered primary command %s path differs" % label)
        resolved = declared.expanduser()
        if not resolved.is_absolute():
            resolved = ROOT / resolved
        if resolved.resolve() != expected_path:
            raise ValueError("preregistered primary command %s path differs" % label)
    work_root = Path(str(config.get("work_root"))).expanduser().resolve()
    declared_work_root = parsed.workdir.expanduser()
    if not declared_work_root.is_absolute():
        declared_work_root = ROOT / declared_work_root
    if declared_work_root.resolve() != work_root:
        raise ValueError("preregistered primary command workdir differs")
    reported_command = provenance.get("command")
    if not (
        isinstance(reported_command, list)
        and len(reported_command) == len(command)
        and all(isinstance(value, str) for value in reported_command)
        and Path(reported_command[0]).resolve() == Path(command[0]).resolve()
        and Path(reported_command[1]).resolve()
        == (ROOT / "scripts" / "batch_evolve.py").resolve()
        and reported_command[2:] == command[2:]
    ):
        raise ValueError("parent report command differs from preregistration")
    analysis_command = (preregistration.get("design") or {}).get(
        "analysis_command"
    )
    if not (
        isinstance(analysis_command, list)
        and len(analysis_command) == 8
        and all(isinstance(value, str) for value in analysis_command)
        and (ROOT / analysis_command[1]).resolve()
        == (ROOT / "scripts" / "analyze_candidate_calibration.py").resolve()
        and analysis_command[2] == "--report"
        and (ROOT / analysis_command[3]).expanduser().resolve() == report_path
        and analysis_command[4] == "--preregistration"
        and (ROOT / analysis_command[5]).expanduser().resolve()
        == preregistration_path
        and analysis_command[6] == "--output"
        and Path(analysis_command[7]).name
    ):
        raise ValueError("preregistered analysis command differs")
    if (preregistration.get("design") or {}).get(
        "analysis_script_sha256"
    ) != _sha256(Path(__file__)):
        raise ValueError("preregistered analysis script hash differs")


def _validate_source_lineage(parent_revision: str, source_revision: str) -> None:
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", parent_revision, source_revision],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode != 0:
        raise ValueError("preregistered parent revision is not an ancestor")
    scoped_changes = subprocess.check_output(
        [
            "git", "diff", "--name-only", parent_revision, source_revision,
            "--", *SOURCE_SCOPE,
        ],
        cwd=str(ROOT),
        text=True,
        stderr=subprocess.DEVNULL,
    ).splitlines()
    if any(value.strip() for value in scoped_changes):
        raise ValueError("scoped source changed after preregistration parent")


def _validate_science_metric_estimands(
    task_rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    required_fields = {"metric", "value_type", "direction"}
    by_task: dict[str, list[dict[str, str]]] = {}
    for task_row in task_rows:
        specs = task_row.get("science_metric_estimands")
        if not isinstance(specs, list) or not specs:
            raise ValueError("preregistered science metric estimands are missing")
        if any(
            not isinstance(spec, dict) or set(spec) != required_fields
            for spec in specs
        ):
            raise ValueError("preregistered science metric estimands are invalid")
        metric_names = [spec["metric"] for spec in specs]
        if (
            any(
                not isinstance(name, str) or not name.strip()
                for name in metric_names
            )
            or len(set(metric_names)) != len(metric_names)
            or any(
                not isinstance(spec["value_type"], str)
                or spec["value_type"] not in SCIENCE_METRIC_VALUE_TYPES
                or not isinstance(spec["direction"], str)
                or spec["direction"] not in SCIENCE_METRIC_DIRECTIONS
                for spec in specs
            )
        ):
            raise ValueError("preregistered science metric estimands are invalid")
        by_task[task_row["task"]] = [dict(spec) for spec in specs]
    return by_task


def _validate_contract(
    report: dict[str, Any],
    preregistration: dict[str, Any],
    prereg_hash: str,
    report_path: Path,
    preregistration_path: Path,
) -> tuple[
    list[str],
    list[str],
    list[int],
    list[int],
    dict[str, list[dict[str, str]]],
]:
    design = preregistration.get("design") or {}
    task_rows = design.get("tasks")
    if not isinstance(task_rows, list) or not task_rows or not all(
        isinstance(row, dict) for row in task_rows
    ):
        raise ValueError("preregistered tasks must be a nonempty list")
    tasks = [row.get("task") for row in task_rows]
    modes = design.get("feedback_modes")
    seeds = design.get("local_replicate_identifiers")
    prefixes = design.get("budget_estimands")
    budget = design.get("proposal_budget_upper_bound")
    if not all(isinstance(task, str) and task for task in tasks) or (
        len(set(tasks)) != len(tasks)
    ):
        raise ValueError("preregistered tasks must be nonempty and unique")
    science_metric_estimands = _validate_science_metric_estimands(task_rows)
    if not isinstance(modes, list) or not modes or not all(
        isinstance(mode, str) and mode for mode in modes
    ) or len(set(modes)) != len(modes):
        raise ValueError("preregistered feedback modes must be nonempty and unique")
    if not isinstance(seeds, list) or not seeds or any(
        not isinstance(seed, int) or isinstance(seed, bool) for seed in seeds
    ) or len(set(seeds)) != len(seeds):
        raise ValueError(
            "preregistered replicate identifiers must be unique integers"
        )
    if (
        not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0
    ):
        raise ValueError("preregistered proposal budget must be a positive integer")
    if not isinstance(prefixes, list) or not prefixes:
        raise ValueError("preregistered budget estimands are missing")
    if any(
        not isinstance(value, int) or isinstance(value, bool)
        or value <= 0 or value > budget
        for value in prefixes
    ) or len(set(prefixes)) != len(prefixes) or prefixes != sorted(prefixes):
        raise ValueError("preregistered budget estimands are invalid")
    config = report.get("config") or {}
    if (
        not isinstance(config.get("budget"), int)
        or isinstance(config.get("budget"), bool)
        or not isinstance(config.get("seeds"), list)
        or any(
            not isinstance(seed, int) or isinstance(seed, bool)
            for seed in config.get("seeds", [])
        )
    ):
        raise ValueError("report seed or budget types are invalid")
    expected = {
        "tasks": tasks,
        "feedback_modes": modes,
        "seeds": seeds,
        "budget": budget,
        "run_role": "calibration",
    }
    for field, value in expected.items():
        if config.get(field) != value:
            raise ValueError("report differs from preregistration for %s" % field)
    if config.get("algorithms") != ["greedy_rewrite"]:
        raise ValueError("candidate calibration requires greedy_rewrite")
    expected_run_count = len(tasks) * len(modes) * len(seeds)
    if (
        not isinstance(config.get("scheduled_run_count"), int)
        or isinstance(config.get("scheduled_run_count"), bool)
        or config.get("scheduled_run_count") != expected_run_count
    ):
        raise ValueError("report scheduled run count differs from frozen design")
    if "condition_order_design" in design and config.get(
        "condition_order"
    ) != design["condition_order_design"]:
        raise ValueError("report condition order differs from preregistration")
    if "condition_order_schedule" in design and config.get(
        "condition_order_schedule"
    ) != design["condition_order_schedule"]:
        raise ValueError("report condition schedule differs from preregistration")
    frozen_bindings = config.get("frozen_task_bindings")
    if not isinstance(frozen_bindings, dict) or set(frozen_bindings) != set(tasks):
        raise ValueError("report frozen task binding set differs")
    for row in task_rows:
        task = row["task"]
        if not _is_sha256(row.get("maturity_contract_sha256")):
            raise ValueError(
                "preregistered maturity task binding is invalid for %s" % task
            )
        binding = frozen_bindings.get(task)
        if not isinstance(binding, dict) or any(
            field not in binding or row.get(field) != binding[field]
            for field in REQUIRED_TASK_BINDING_FIELDS
        ):
            raise ValueError("report frozen task binding differs for %s" % task)
        for field in (
            "task_contract_sha256", "task_package_sha256",
            "task_card_sha256", "runtime_source_sha256",
            "wave_manifest_sha256", "trusted_evaluator_runtime_sha256",
        ):
            value = binding[field]
            if not _is_sha256(value):
                raise ValueError("report frozen task binding hash is invalid")
        descriptor = validate_runtime_descriptor(
            binding["trusted_evaluator_runtime"]
        )
        if descriptor["fingerprint_sha256"] != binding[
            "trusted_evaluator_runtime_sha256"
        ]:
            raise ValueError("report frozen task binding runtime differs")
    frozen_source = preregistration.get("frozen_source")
    runtime_hashes = {
        row.get("runtime_source_sha256") for row in task_rows
    }
    if not isinstance(frozen_source, dict) or (
        len(runtime_hashes) != 1
        or frozen_source.get("runtime_source_sha256") not in runtime_hashes
    ):
        raise ValueError("preregistered frozen runtime source differs")
    parent_revision = frozen_source.get("parent_revision")
    if not (
        isinstance(parent_revision, str)
        and len(parent_revision) in {40, 64}
        and all(character in "0123456789abcdef" for character in parent_revision)
    ):
        raise ValueError("preregistered parent revision is missing")
    source_revision = (report.get("source_provenance") or {}).get("git_revision")
    _validate_source_lineage(parent_revision, source_revision)
    recorded_prereg = config.get("preregistration") or {}
    if not (
        recorded_prereg.get("sha256") == prereg_hash
        and recorded_prereg.get("execution_contract_validated") is True
    ):
        raise ValueError("report preregistration binding differs")
    resume_permitted = design.get("resume_permitted")
    if not isinstance(resume_permitted, bool) or recorded_prereg.get(
        "resume_suffix_permitted"
    ) is not resume_permitted:
        raise ValueError("report resume policy differs from preregistration")
    model = preregistration.get("model_condition") or {}
    if not _is_sha256(model.get("llm_condition_sha256")) or (
        config.get("llm_condition_sha256") != model.get("llm_condition_sha256")
    ):
        raise ValueError("report model condition differs from preregistration")
    if set(model.get("required_readable_fields") or []) != (
        REQUIRED_READABLE_MODEL_FIELDS
    ):
        raise ValueError("preregistered readable model fields are incomplete")
    report_model = config.get("llm") or {}
    if not (
        report_model.get("model") == model.get("model") == "hy3"
        and report_model.get("server_side_seed_control") is False
        and model.get("server_side_seed_control") is False
    ):
        raise ValueError("report model condition is not the preregistered HY3 condition")
    cohort = preregistration.get("source_cohort") or {}
    recorded_cohort = config.get("cohort_manifest") or {}
    if (
        recorded_cohort.get("sha256") != cohort.get("sha256")
        or recorded_cohort.get("path") != cohort.get("path")
    ):
        raise ValueError("report cohort differs from preregistration")
    if preregistration.get("claim_limit") != cohort.get("claim_limit"):
        raise ValueError("preregistration claim limit differs from cohort")
    cohort_path = (ROOT / str(cohort.get("path"))).resolve()
    try:
        cohort_path.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("preregistered cohort escapes the repository") from exc
    if not cohort_path.is_file() or _sha256(cohort_path) != cohort.get("sha256"):
        raise ValueError("preregistered cohort artifact differs")
    try:
        cohort_document = json.loads(cohort_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError("preregistered cohort is not valid JSON") from exc
    if not isinstance(cohort_document, dict):
        raise ValueError("preregistered cohort is not a JSON object")
    _validate_cohort_semantics(
        cohort_document,
        cohort,
        task_rows,
        design.get("analysis_role"),
    )
    _validate_preregistered_command(
        preregistration,
        preregistration_path,
        report_path,
        report,
        tasks,
        list(modes),
        list(seeds),
        budget,
        cohort_path,
    )
    return (
        tasks,
        list(modes),
        list(seeds),
        list(prefixes),
        science_metric_estimands,
    )


def _validate_verified_model_condition(
    verified: dict[str, Any], model: dict[str, Any],
) -> None:
    descriptor = verified.get("llm_condition")
    if not isinstance(descriptor, dict):
        raise ValueError("verified run lacks readable model condition")
    if not REQUIRED_READABLE_MODEL_FIELDS <= set(model):
        raise ValueError("preregistered readable model condition is incomplete")
    field_map = {
        "wire": "wire",
        "endpoint_sha256": "endpoint_sha256",
        "model": "model",
        "max_output_tokens": "max_output_tokens",
        "temperature": "temperature",
        "reasoning_effort": "reasoning_effort",
        "provider_request_timeout_seconds": "timeout_seconds",
        "stream": "stream",
        "chat_max_tokens_field": "chat_max_tokens_field",
        "chat_reasoning_fallback": "chat_reasoning_fallback",
        "server_side_seed_control": "server_side_seed_control",
    }
    if any(
        descriptor.get(descriptor_field) != model.get(model_field)
        for model_field, descriptor_field in field_map.items()
    ):
        raise ValueError("verified run readable model condition differs")


def _verify_successful_run(
    run: dict[str, Any],
    attempts: list[dict[str, Any]],
    config: dict[str, Any],
    binding: dict[str, Any],
    budget: int,
    model: dict[str, Any],
) -> dict[str, Any]:
    work_root_value = config.get("work_root")
    if not isinstance(work_root_value, str) or config.get(
        "work_root_scope"
    ) != "local_only_not_portable_evidence_identity":
        raise ValueError("report frozen work root is invalid")
    work_root = Path(work_root_value).expanduser()
    if not work_root.is_absolute() or str(work_root.resolve()) != work_root_value:
        raise ValueError("report frozen work root is not canonical")
    expected = _safe_batch_cell_paths(
        work_root,
        run["task"],
        run["algorithm"],
        [run["feedback_mode"]],
        run["seed"],
    )[0]
    if (
        run.get("workdir") != str(expected)
        or run.get("workdir_scope")
        != "local_only_not_portable_evidence_identity"
    ):
        raise ValueError("run workdir differs from frozen cell identity")
    verified = verify_run(
        expected,
        expected_budget=budget,
        expected_trusted_runtime_sha256=binding[
            "trusted_evaluator_runtime_sha256"
        ],
    )
    expected_identity = {
        "task_id": run["task"],
        "algorithm": run["algorithm"],
        "feedback_mode": run["feedback_mode"],
        "seed": run["seed"],
        "budget": budget,
        "llm_condition_sha256": config["llm_condition_sha256"],
        "trusted_evaluator_runtime": binding["trusted_evaluator_runtime"],
        "trusted_evaluator_runtime_sha256": binding[
            "trusted_evaluator_runtime_sha256"
        ],
    }
    for field in (
        "task_contract_sha256", "task_package_sha256",
        "runtime_source_sha256", "task_family_id", "wave_id",
        "wave_manifest_sha256",
    ):
        expected_identity[field] = binding[field]
    if verified.get("verified") is not True or any(
        verified.get(field) != value
        for field, value in expected_identity.items()
    ):
        raise ValueError("verified run identity differs from frozen cell")
    _validate_verified_model_condition(verified, model)
    actual_snapshot = compact_trajectory_snapshot(
        expected / "trajectory.jsonl", schema_version=2
    )
    if run.get("trajectory_snapshot") != actual_snapshot:
        raise ValueError("successful run snapshot differs from verified trajectory")
    actual_events = actual_snapshot["events"]
    _validate_run_scores(run, actual_events)
    trajectory_lines = (expected / "trajectory.jsonl").read_bytes().splitlines(
        keepends=True
    )
    for attempt in attempts:
        snapshot = attempt.get("trajectory_snapshot")
        if snapshot is None:
            continue
        events = snapshot.get("events") if isinstance(snapshot, dict) else None
        if not isinstance(events, list) or events != actual_events[:len(events)]:
            raise ValueError("attempt snapshot is not a verified trajectory prefix")
        prefix_hash = hashlib.sha256(
            b"".join(trajectory_lines[:len(events)])
        ).hexdigest()
        if snapshot.get("trajectory_sha256") not in {None, prefix_hash}:
            raise ValueError("attempt snapshot hash differs from trajectory prefix")
    return actual_snapshot


def _validate_run_scores(
    run: dict[str, Any], actual_events: list[dict[str, Any]],
) -> None:
    if not actual_events or not (
        run.get("baseline") == actual_events[0].get("best_score")
        and run.get("best") == actual_events[-1].get("best_score")
    ):
        raise ValueError("run baseline or best differs from verified trajectory")


def _best_artifact_science_metrics(
    events: list[dict[str, Any]],
    prefix: int,
    metric_specs: list[dict[str, str]],
) -> tuple[int, dict[str, Any]]:
    if events[0].get("accepted") is not True:
        raise ValueError("trajectory initial incumbent is not accepted")
    incumbent = events[0]
    for event in events[1:]:
        if int(event["step"]) > prefix:
            break
        if event.get("accepted") is True:
            incumbent = event
    metrics = incumbent.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("accepted incumbent science metrics are missing")
    values: dict[str, Any] = {}
    for spec in metric_specs:
        metric = spec["metric"]
        value = metrics.get(metric)
        if spec["value_type"] == "numeric":
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(float(value))
            ):
                raise ValueError("accepted incumbent numeric science metric is invalid")
            values[metric] = float(value)
        elif not isinstance(value, bool):
            raise ValueError("accepted incumbent boolean science metric is invalid")
        else:
            values[metric] = value
    return int(incumbent["step"]), values


def _prefix_row(
    run: dict[str, Any] | None,
    prefix: int,
    metric_specs: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    cumulative_fields = {
        "valid_proposals_through_prefix": 0,
        "invalid_proposals_through_prefix": 0,
        "proposal_errors_through_prefix": 0,
        "proposal_timeouts_through_prefix": 0,
        "signed_abstentions_through_prefix": 0,
    }
    if run is None:
        return {
            "observed": False,
            "status": "missing_run_row",
            **cumulative_fields,
        }
    events = (run.get("trajectory_snapshot") or {}).get("events") or []
    steps = [event.get("step") for event in events]
    if steps != list(range(len(events))):
        raise ValueError("trajectory snapshot steps are not contiguous")
    matches = [event for event in events if event.get("step") == prefix]
    status = (
        "error" if run.get("error")
        else "protocol_incomplete" if run.get("protocol_incomplete")
        else "completed"
    )
    proposal_events = [
        row for row in events if 0 < int(row["step"]) <= prefix
    ]
    cumulative_fields = {
        "valid_proposals_through_prefix": sum(
            row.get("valid") is True for row in proposal_events
        ),
        "invalid_proposals_through_prefix": sum(
            row.get("valid") is not True for row in proposal_events
        ),
        "proposal_errors_through_prefix": sum(
            isinstance(row.get("error"), str) and bool(row.get("error"))
            for row in proposal_events
        ),
        "proposal_timeouts_through_prefix": sum(
            isinstance(row.get("error"), str)
            and "timeout" in row["error"].lower()
            for row in proposal_events
        ),
        "signed_abstentions_through_prefix": sum(
            (row.get("algorithm_metadata") or {}).get(
                "signed_decision_action"
            ) == "abstain"
            for row in proposal_events
        ),
    }
    if not matches:
        return {"observed": False, "status": status, **cumulative_fields}
    event = matches[0]
    score = event.get("best_score")
    if (
        not isinstance(score, (int, float)) or isinstance(score, bool)
        or not math.isfinite(float(score))
    ):
        raise ValueError("trajectory prefix score is not finite")
    baseline = run.get("baseline")
    if not isinstance(baseline, (int, float)) or isinstance(baseline, bool):
        baseline = events[0].get("best_score") if events else None
    if (
        not isinstance(baseline, (int, float)) or isinstance(baseline, bool)
        or not math.isfinite(float(baseline))
    ):
        raise ValueError("trajectory baseline is not finite")
    science_metrics = {}
    if metric_specs:
        source_step, science_metrics = _best_artifact_science_metrics(
            events, prefix, metric_specs
        )
    return {
        "observed": True,
        "status": status,
        "best_score": float(score),
        "baseline_score": float(baseline),
        "valid_at_prefix": event.get("valid") is True,
        "accepted_at_prefix": event.get("accepted") is True,
        "exceeds_baseline": float(score) > float(baseline),
        "exceeds_reference": float(score) > 1.0,
        **({
            "best_artifact_source_step": source_step,
            "best_artifact_science_metrics": science_metrics,
        } if metric_specs else {}),
        **cumulative_fields,
    }


def _summarize_science_metrics(
    rows: list[dict[str, Any]],
    metric_specs: list[dict[str, str]],
    scheduled_n: int,
) -> dict[str, dict[str, Any]]:
    observed = [row for row in rows if row["observed"]]
    summaries = {}
    for spec in metric_specs:
        metric = spec["metric"]
        values = [
            row["best_artifact_science_metrics"][metric]
            for row in observed
        ]
        summary = {
            "value_type": spec["value_type"],
            "direction": spec["direction"],
            "scheduled_n": scheduled_n,
            "observed_n": len(observed),
            "missing_n": scheduled_n - len(observed),
        }
        if spec["value_type"] == "numeric":
            summary["mean_over_observed"] = (
                sum(values) / len(values) if values else None
            )
        else:
            summary["true_fraction_of_observed"] = (
                sum(values) / len(values) if values else None
            )
        summaries[metric] = summary
    return summaries


def _summarize_axis(
    selected: dict[tuple[str, str, str, int], dict[str, Any]],
    tasks: list[str],
    modes: list[str],
    seeds: list[int],
    prefixes: list[int],
    science_metric_estimands: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    by_condition: dict[str, dict[str, Any]] = {}
    for task in tasks:
        for mode in modes:
            condition = {}
            for prefix in prefixes:
                metric_specs = science_metric_estimands[task]
                rows = [
                    _prefix_row(
                        selected.get((task, "greedy_rewrite", mode, seed)),
                        prefix,
                        metric_specs,
                    )
                    for seed in seeds
                ]
                observed = [row for row in rows if row["observed"]]
                valid_count = sum(row["valid_at_prefix"] for row in observed)
                accepted_count = sum(
                    row["accepted_at_prefix"] for row in observed
                )
                above_baseline_count = sum(
                    row["exceeds_baseline"] for row in observed
                )
                above_reference_count = sum(
                    row["exceeds_reference"] for row in observed
                )
                cumulative_fields = (
                    "valid_proposals_through_prefix",
                    "invalid_proposals_through_prefix",
                    "proposal_errors_through_prefix",
                    "proposal_timeouts_through_prefix",
                    "signed_abstentions_through_prefix",
                )
                condition["B%d" % prefix] = {
                    "scheduled_n": len(seeds),
                    "observed_n": len(observed),
                    "missing_n": len(seeds) - len(observed),
                    "mean_best_score": (
                        sum(row["best_score"] for row in observed) / len(observed)
                        if observed else None
                    ),
                    "valid_at_prefix_n": valid_count,
                    "valid_at_prefix_fraction_of_scheduled": (
                        valid_count / len(seeds)
                    ),
                    "accepted_at_prefix_n": accepted_count,
                    "accepted_at_prefix_fraction_of_scheduled": (
                        accepted_count / len(seeds)
                    ),
                    "exceeds_baseline_n": above_baseline_count,
                    "exceeds_baseline_fraction_of_scheduled": (
                        above_baseline_count / len(seeds)
                    ),
                    "exceeds_reference_n": above_reference_count,
                    "exceeds_reference_fraction_of_scheduled": (
                        above_reference_count / len(seeds)
                    ),
                    "status_counts": {
                        status: sum(row["status"] == status for row in rows)
                        for status in sorted({row["status"] for row in rows})
                    },
                    "science_metrics": _summarize_science_metrics(
                        rows, metric_specs, len(seeds)
                    ),
                    "best_artifact_science_metrics_by_replicate": [
                        {
                            "replicate_identifier": seed,
                            "observed": row["observed"],
                            "status": row["status"],
                            "best_artifact_source_step": row.get(
                                "best_artifact_source_step"
                            ),
                            "metrics": row.get(
                                "best_artifact_science_metrics"
                            ),
                        }
                        for seed, row in zip(seeds, rows)
                    ],
                    **{
                        field + "_n": sum(row[field] for row in rows)
                        for field in cumulative_fields
                    },
                }
            by_condition["%s|%s" % (task, mode)] = condition

    contrasts: dict[str, dict[str, float | None]] = {}
    science_metric_contrasts: dict[
        str, dict[str, dict[str, float] | None]
    ] = {}
    if set(modes) == {"normal", "selection_blind"}:
        for task in tasks:
            task_contrasts = {}
            task_science_metric_contrasts = {}
            for prefix in prefixes:
                normal = by_condition["%s|normal" % task]["B%d" % prefix]
                blind = by_condition[
                    "%s|selection_blind" % task
                ]["B%d" % prefix]
                complete_arms = (
                    normal["observed_n"] == normal["scheduled_n"]
                    and blind["observed_n"] == blind["scheduled_n"]
                )
                task_contrasts["B%d" % prefix] = (
                    normal["mean_best_score"] - blind["mean_best_score"]
                    if complete_arms else None
                )
                task_science_metric_contrasts["B%d" % prefix] = (
                    {
                        spec["metric"]: (
                            normal["science_metrics"][spec["metric"]][
                                "mean_over_observed"
                                if spec["value_type"] == "numeric"
                                else "true_fraction_of_observed"
                            ]
                            - blind["science_metrics"][spec["metric"]][
                                "mean_over_observed"
                                if spec["value_type"] == "numeric"
                                else "true_fraction_of_observed"
                            ]
                        )
                        for spec in science_metric_estimands[task]
                    }
                    if complete_arms else None
                )
            contrasts[task] = task_contrasts
            science_metric_contrasts[task] = task_science_metric_contrasts
    return {
        "by_task_condition": by_condition,
        "normal_minus_selection_blind": contrasts,
        "science_metric_normal_minus_selection_blind": (
            science_metric_contrasts
        ),
    }


def analyze(report_path: Path, preregistration_path: Path) -> dict[str, Any]:
    report_path = Path(report_path).resolve()
    preregistration_path = Path(preregistration_path).resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    preregistration = json.loads(
        preregistration_path.read_text(encoding="utf-8")
    )
    prereg_hash = _sha256(preregistration_path)
    (
        tasks,
        modes,
        seeds,
        prefixes,
        science_metric_estimands,
    ) = _validate_contract(
        report,
        preregistration,
        prereg_hash,
        report_path,
        preregistration_path,
    )
    expected_keys = {
        (task, "greedy_rewrite", mode, seed)
        for task in tasks for mode in modes for seed in seeds
    }
    bindings = report["config"]["frozen_task_bindings"]
    attempts: dict[tuple[str, str, str, int], list[dict[str, Any]]] = {}
    for run in report.get("runs") or []:
        key = _run_key(run)
        if key not in expected_keys:
            raise ValueError("run cell identity lies outside the frozen cohort")
        binding = bindings[key[0]]
        run_budget = run.get("budget")
        if not (
            isinstance(run_budget, int)
            and not isinstance(run_budget, bool)
            and run_budget == preregistration["design"][
                "proposal_budget_upper_bound"
            ]
            and run.get("trusted_evaluator_runtime")
            == binding.get("trusted_evaluator_runtime")
            and run.get("trusted_evaluator_runtime_sha256")
            == binding.get("trusted_evaluator_runtime_sha256")
        ):
            raise ValueError("run cell identity differs from frozen runtime")
        attempts.setdefault(key, []).append(run)
    first = {key: rows[0] for key, rows in attempts.items()}
    latest = {key: rows[-1] for key, rows in attempts.items()}
    for key, run in latest.items():
        if run.get("error") or run.get("protocol_incomplete"):
            continue
        _verify_successful_run(
            run,
            attempts[key],
            report["config"],
            bindings[key[0]],
            preregistration["design"]["proposal_budget_upper_bound"],
            preregistration["model_condition"],
        )
    all_latest_successful = bool(
        set(latest) == expected_keys
        and all(
            not run.get("error") and not run.get("protocol_incomplete")
            for run in latest.values()
        )
    )
    aggregate = report.get("aggregate") or {}
    intent = aggregate.get("intent_to_evaluate") or {}
    parent_aggregate_complete = bool(
        aggregate.get("successful_runs") == len(expected_keys)
        and aggregate.get("failed_runs") == 0
        and intent.get("scheduled_runs") == len(expected_keys)
        and intent.get("successful_runs") == len(expected_keys)
        and intent.get("terminal_failed_runs") == 0
        and intent.get("missing_run_rows") == 0
    )
    complete = bool(
        set(first) == expected_keys
        and preregistration["design"]["resume_permitted"] is False
        and all(len(rows) == 1 for rows in attempts.values())
        and all_latest_successful
        and parent_aggregate_complete
        and (report.get("source_provenance") or {}).get("source_tree_dirty") is False
        and (report.get("source_provenance") or {}).get("git_available") is True
        and isinstance(
            (report.get("source_provenance") or {}).get("git_revision"), str
        )
        and (report.get("final_integrity") or {}).get("passed") is True
        and report.get("execution_passed") is True
        and report.get("trusted_evidence") is True
        and report.get("passed") is True
        and report.get("trust_decision") == "trusted_clean_revision"
        and report.get("trust_status") == "TRUSTED_SECURE_EVAL"
        and report.get("evidence_scope")
        == "MODEL_CALIBRATION_NOT_POPULATION_PERFORMANCE"
    )
    result: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": "HY3_CANDIDATE_CALIBRATION_NOT_HARDNESS_CERTIFICATION_OR_CAUSAL_FEEDBACK_EVIDENCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "inputs": {
            "report": {"path": _recorded_path(report_path), "sha256": _sha256(report_path)},
            "preregistration": {
                "path": _recorded_path(preregistration_path),
                "sha256": prereg_hash,
            },
            "parent_report_trust": {
                "source_revision": (report.get("source_provenance") or {}).get(
                    "git_revision"
                ),
                "execution_passed": report.get("execution_passed"),
                "trusted_evidence": report.get("trusted_evidence"),
                "passed": report.get("passed"),
                "trust_decision": report.get("trust_decision"),
            },
        },
        "analysis_contract": {
            "primary": "first_attempt_intent_to_evaluate",
            "sensitivity": "latest_attempt_after_transparent_resume",
            "resume_permitted": preregistration["design"]["resume_permitted"],
            "trusted_evidence_requires_one_attempt_per_scheduled_cell": True,
            "thresholds": {
                "baseline": "strictly greater than the run's frozen baseline score",
                "reference": "strictly greater than normalized score 1.0",
            },
            "missing_prefix_policy": "retain in scheduled denominator, exclude from observed mean, and suppress the condition contrast",
            "contrast": "difference of condition means, normal minus selection_blind; descriptive and unpaired because provider-side seeds are unavailable",
            "science_metric_estimands": science_metric_estimands,
            "science_metric_incumbent_policy": "at each exact budget prefix, summarize the latest accepted artifact, with step 0 as the initial incumbent",
            "science_metric_contrast": "difference of numeric means or boolean true fractions, normal minus selection_blind; suppressed unless both arms are complete",
        },
        "scheduled_run_count": len(expected_keys),
        "observed_first_attempt_run_count": len(first),
        "attempt_count": sum(len(rows) for rows in attempts.values()),
        "analyses": {
            "first_attempt": _summarize_axis(
                first,
                tasks,
                modes,
                seeds,
                prefixes,
                science_metric_estimands,
            ),
            "latest_attempt_after_transparent_resume": _summarize_axis(
                latest,
                tasks,
                modes,
                seeds,
                prefixes,
                science_metric_estimands,
            ),
        },
        "limitations": [
            "Budget estimands below the maximum are prefixes of each maximum-budget trajectory, not independent policy restarts.",
            "Local replicate identifiers do not control provider generation randomness.",
            "%d local replicate identifiers support descriptive candidate calibration only."
            % len(seeds),
            "Scores do not establish real-world scientific validity or task hardness certification.",
        ],
    }
    finalize_report_trust(result, complete)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze(args.report, args.preregistration)
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
