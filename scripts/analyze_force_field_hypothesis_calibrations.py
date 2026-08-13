#!/usr/bin/env python3
"""Bind and analyze the three ForceFieldCalibration-v2 GPT-5.5 runs.

The inputs are single descriptive calibrations.  Equal local seed labels do
not control Azure generation randomness, so normal versus selection-blind
differences are not feedback effects, rankings, scaling laws, or scientific
discovery evidence.
"""

from __future__ import annotations

import argparse
import ast
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

from sle.protocol import (  # noqa: E402
    compact_trajectory_snapshot,
    load_trajectory,
)
from sle.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)
from sle.runtime_migration import (  # noqa: E402
    runtime_migration_status,
    runtime_source_changes,
)


TASK = "MolecularDynamics/ForceFieldCalibration"
CALIBRATION = (
    "experiments/force_field_hypothesis_lab_v2_calibration_2026-07-26.json"
)
REPORTS = {
    "budget_one": (
        "experiments/gpt55_force_field_hypothesis_v2_b1_2026-07-26.json"
    ),
    "normal_budget_three": (
        "experiments/gpt55_force_field_hypothesis_v2_b3_2026-07-26.json"
    ),
    "blind_budget_three": (
        "experiments/gpt55_force_field_hypothesis_v2_blind_b3_2026-07-26.json"
    ),
}
INPUT_SOURCE_REVISION = "0f8a43d404df2834bcbc461ac9391c7695e71f1a"
BASELINE_SHA256 = (
    "8edee96aeb0ee22f10838110e0d600c1e540d2fba411ced0e13ca27721eab23b"
)
TASK_RUNTIME_SCOPE = (
    "sle/evaluate.py",
    "sle/trusted_driver.py",
    "sle/secure_eval.py",
    "sle/candidate_worker.py",
    "sle/rpc_codec.py",
    "sle/spec.py",
    "sle/registry.py",
    "benchmarks/Chemistry/ForceFieldCalibration",
    "requirements-upstream.txt",
)
SCIENCE_FIELDS = (
    "combined_score",
    "raw_score",
    "robustness_score",
    "heldout_policy_score",
    "heldout_robustness_score",
    "feasibility_rate",
    "heldout_feasibility_rate",
    "development_raw_joint_score",
    "heldout_raw_joint_score",
    "development_raw_robust_joint_score",
    "heldout_raw_robust_joint_score",
    "development_abstention_baseline",
    "heldout_abstention_baseline",
    "development_lineage_score",
    "heldout_lineage_score",
    "development_acquisition_score",
    "heldout_acquisition_score",
    "development_information_gain",
    "heldout_information_gain",
    "development_design_coverage",
    "heldout_design_coverage",
    "development_hypothesis_score",
    "heldout_hypothesis_score",
    "development_true_hypothesis_retention_rate",
    "heldout_true_hypothesis_retention_rate",
    "development_premature_elimination_rate",
    "heldout_premature_elimination_rate",
    "development_model_selection_score",
    "heldout_model_selection_score",
    "development_parameter_score",
    "heldout_parameter_score",
    "development_interval_score",
    "heldout_interval_score",
    "development_interval_coverage",
    "heldout_interval_coverage",
    "development_prediction_score",
    "heldout_prediction_score",
    "development_robust_prediction_score",
    "heldout_robust_prediction_score",
    "development_virial_score",
    "heldout_virial_score",
    "development_boyle_decision_score",
    "heldout_boyle_decision_score",
    "development_confidence_score",
    "heldout_confidence_score",
    "development_supported_claim_coverage",
    "heldout_supported_claim_coverage",
    "development_supported_correct_model_rate",
    "heldout_supported_correct_model_rate",
    "development_unsupported_refusal_rate",
    "heldout_unsupported_refusal_rate",
    "development_false_discovery_rate",
    "heldout_false_discovery_rate",
    "development_mean_query_calls",
    "heldout_mean_query_calls",
    "development_mean_query_budget_units",
    "heldout_mean_query_budget_units",
    "development_reference_policy_score",
    "heldout_reference_policy_score",
    "development_oracle_clean_score",
    "heldout_oracle_clean_score",
    "candidate_instance_call_count",
    "candidate_instance_valid_rate",
)
WORLD_FIELDS = (
    "split",
    "world_index",
    "kind",
    "valid",
    "failure_kind",
    "supported",
    "true_hypothesis",
    "selected_model",
    "lineage_quality",
    "acquisition_quality",
    "information_gain",
    "design_coverage",
    "hypothesis_quality",
    "selection_quality",
    "parameter_quality",
    "interval_quality",
    "interval_coverage",
    "prediction_quality",
    "robust_prediction_quality",
    "virial_quality",
    "decision_quality",
    "joint_quality",
    "robust_joint_quality",
    "correct_refusal",
    "false_discovery",
    "abstained",
    "confidence",
    "query_calls",
    "query_budget_units",
    "evidence_count",
    "available_evidence_count",
)
EXPECTED_FAILURE_COUNTS = {
    "budget_one": {"invalid_submission": 1},
    "normal_budget_three": {"candidate_runtime_error": 3},
    "blind_budget_three": {
        "blocked_or_missing_import": 1,
        "candidate_runtime_error": 2,
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _science(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in SCIENCE_FIELDS}


def _world_summary(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {field: row.get(field) for field in WORLD_FIELDS}
        for row in (metrics.get("per_world") or [])
    ]


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, TASK_RUNTIME_SCOPE, root=ROOT)


def _failure_kind(event: dict[str, Any]) -> str | None:
    metrics = event.get("metrics") or {}
    explicit = metrics.get("candidate_failure_kind")
    if isinstance(explicit, str) and explicit:
        return explicit
    message = metrics.get("error_message") or event.get("error")
    prefix = "candidate invalid: "
    if isinstance(message, str) and message.startswith(prefix):
        return message[len(prefix):]
    world_failures = {
        str(row.get("failure_kind"))
        for row in (metrics.get("per_world") or [])
        if isinstance(row.get("failure_kind"), str) and row.get("failure_kind")
    }
    return next(iter(world_failures)) if len(world_failures) == 1 else None


def _source_scan(path: Path) -> dict[str, Any]:
    """Statically inspect a retained source without executing generated code."""

    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {
            "source_sha256": _sha256(path),
            "syntax_valid": False,
            "syntax_error": "%s:%s" % (exc.lineno, exc.offset),
            "fixed_world_literal_hits": [],
            "evaluator_source_term_hits": [],
            "dynamic_source_import_hits": [],
            "dynamic_source_call_hits": [],
            "known_missing_import_symbols": [],
            "shortcut_safe": False,
        }

    constants = {
        str(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, (str, int))
        and not isinstance(node.value, bool)
    }
    fixed_worlds = {
        "52011", "52021", "52027", "52039", "52051", "52057", "52067",
        "62003", "62011", "62017", "62029", "62039",
    }
    literal_hits = sorted(fixed_worlds & constants)
    lower = source.lower()
    evaluator_terms = (
        "verification/evaluator",
        "evaluator.py",
        "_make_world",
        "_public_problem",
        "development_specs",
        "heldout_specs",
    )
    evaluator_hits = sorted(term for term in evaluator_terms if term in lower)
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in (
            node.names if isinstance(node, ast.Import)
            else [ast.alias(name=node.module or "")]
        )
    }
    suspicious_imports = sorted(imports & {"importlib", "inspect", "pathlib"})
    suspicious_calls = sorted({
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"open", "eval", "exec", "compile", "__import__"}
    })
    missing_symbols = sorted({
        "%s.%s" % (node.module, alias.name)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if (node.module, alias.name) == ("scipy.optimize", "quad")
    })
    shortcut_safe = not (
        literal_hits or evaluator_hits or suspicious_imports or suspicious_calls
    )
    return {
        "source_sha256": _sha256(path),
        "syntax_valid": True,
        "syntax_error": None,
        "fixed_world_literal_hits": literal_hits,
        "evaluator_source_term_hits": evaluator_hits,
        "dynamic_source_import_hits": suspicious_imports,
        "dynamic_source_call_hits": suspicious_calls,
        "known_missing_import_symbols": missing_symbols,
        "shortcut_safe": shortcut_safe,
    }


def _lineage_is_valid(record: dict[str, Any]) -> bool:
    events = record["trajectory"]
    baseline = events[0]["candidate_sha256"]
    if record["feedback_mode"] == "selection_blind":
        return all(event["parent_sha256"] == baseline for event in events[1:])
    parent = baseline
    for event in events[1:]:
        if event["parent_sha256"] != parent:
            return False
        if event["accepted"]:
            parent = event["candidate_sha256"]
    return True


def _decomposition(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "score": {
            "development_joint": metrics.get("combined_score"),
            "development_robust": metrics.get("robustness_score"),
            "heldout_joint": metrics.get("heldout_policy_score"),
            "heldout_robust": metrics.get("heldout_robustness_score"),
        },
        "active_hypothesis_management": {
            "development_acquisition": metrics.get(
                "development_acquisition_score"
            ),
            "heldout_acquisition": metrics.get("heldout_acquisition_score"),
            "development_information_gain": metrics.get(
                "development_information_gain"
            ),
            "heldout_information_gain": metrics.get(
                "heldout_information_gain"
            ),
            "development_hypothesis": metrics.get(
                "development_hypothesis_score"
            ),
            "heldout_hypothesis": metrics.get("heldout_hypothesis_score"),
            "development_true_hypothesis_retention": metrics.get(
                "development_true_hypothesis_retention_rate"
            ),
            "heldout_true_hypothesis_retention": metrics.get(
                "heldout_true_hypothesis_retention_rate"
            ),
            "development_premature_elimination": metrics.get(
                "development_premature_elimination_rate"
            ),
            "heldout_premature_elimination": metrics.get(
                "heldout_premature_elimination_rate"
            ),
        },
        "inference": {
            "development_model_selection": metrics.get(
                "development_model_selection_score"
            ),
            "heldout_model_selection": metrics.get(
                "heldout_model_selection_score"
            ),
            "development_parameter": metrics.get("development_parameter_score"),
            "heldout_parameter": metrics.get("heldout_parameter_score"),
            "development_interval": metrics.get("development_interval_score"),
            "heldout_interval": metrics.get("heldout_interval_score"),
            "development_prediction": metrics.get(
                "development_prediction_score"
            ),
            "heldout_prediction": metrics.get("heldout_prediction_score"),
            "development_virial": metrics.get("development_virial_score"),
            "heldout_virial": metrics.get("heldout_virial_score"),
            "development_boyle_decision": metrics.get(
                "development_boyle_decision_score"
            ),
            "heldout_boyle_decision": metrics.get(
                "heldout_boyle_decision_score"
            ),
        },
        "claim_control": {
            "development_supported_coverage": metrics.get(
                "development_supported_claim_coverage"
            ),
            "heldout_supported_coverage": metrics.get(
                "heldout_supported_claim_coverage"
            ),
            "development_supported_correct_model": metrics.get(
                "development_supported_correct_model_rate"
            ),
            "heldout_supported_correct_model": metrics.get(
                "heldout_supported_correct_model_rate"
            ),
            "development_unsupported_refusal": metrics.get(
                "development_unsupported_refusal_rate"
            ),
            "heldout_unsupported_refusal": metrics.get(
                "heldout_unsupported_refusal_rate"
            ),
            "development_false_discovery": metrics.get(
                "development_false_discovery_rate"
            ),
            "heldout_false_discovery": metrics.get(
                "heldout_false_discovery_rate"
            ),
            "development_interval_coverage": metrics.get(
                "development_interval_coverage"
            ),
            "heldout_interval_coverage": metrics.get(
                "heldout_interval_coverage"
            ),
        },
        "query_use": {
            "development_query_calls": metrics.get("development_mean_query_calls"),
            "heldout_query_calls": metrics.get("heldout_mean_query_calls"),
            "development_query_units": metrics.get(
                "development_mean_query_budget_units"
            ),
            "heldout_query_units": metrics.get(
                "heldout_mean_query_budget_units"
            ),
        },
    }


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    dimensions = document.get("task_dimensions") or {}
    baseline = document.get("direct_weak_baseline") or {}
    secure = document.get("secure_weak_baseline") or {}
    reference = document.get("truth_blind_reference") or {}
    screening = document.get("screening_hypothesis_and_reference_checks") or {}
    acquisition = document.get("acquisition_contrast_checks") or {}
    pair_checks = document.get("independent_pair_energy_force_checks") or {}
    virial_checks = document.get("independent_second_virial_boyle_checks") or {}
    isolation = document.get("secure_isolation_and_failure_checks") or {}
    task_hashes = document.get("task_source_sha256") or {}
    historical_task_path = "benchmarks/MolecularDynamics/ForceFieldCalibration"
    expected_hash_paths = {
        historical_task_path + "/Task.md",
        historical_task_path + "/TASK_CARD.yaml",
        historical_task_path + "/solution.py",
        historical_task_path + "/verification/evaluator.py",
        historical_task_path + "/frontier_eval/metadata.yaml",
        historical_task_path + "/frontier_eval/run_eval.py",
        "scripts/calibrate_force_field_hypothesis_lab.py",
    }
    if not (
        document.get("execution_passed") is True
        and document.get("passed") is True
        and document.get("trusted_evidence") is True
        and provenance.get("git_revision") == INPUT_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and document.get("task") == TASK
        and dimensions.get("development_world_count") == 7
        and dimensions.get("heldout_world_count") == 5
        and dimensions.get("supported_world_count") == 6
        and dimensions.get("unsupported_world_count") == 6
        and dimensions.get("supported_family_count") == 2
        and dimensions.get("unsupported_kind_count") == 3
        and dimensions.get("query_budget_units") == 24
        and dimensions.get("maximum_query_calls") == 6
        and dimensions.get("first_query_max_configurations") == 1
        and document.get("secure_baseline_exactly_matches_direct") is True
        and all(
            secure.get(key) == value for key, value in baseline.items()
        )
        and set(secure) - set(baseline) == {"raw_score"}
        and secure.get("raw_score") == 0.0
        and baseline.get("valid") == 1.0
        and baseline.get("combined_score") == 0.0
        and baseline.get("candidate_instance_call_count") == 12.0
        and baseline.get("candidate_instance_valid_rate") == 1.0
        and reference.get("valid") == 1.0
        and float(reference.get("combined_score", 0.0)) > 0.96
        and float(reference.get("heldout_policy_score", 0.0)) > 0.94
        and float(reference.get("robustness_score", 0.0)) > 0.96
        and float(reference.get("heldout_robustness_score", 0.0)) > 0.94
        and reference.get("development_supported_claim_coverage") == 1.0
        and reference.get("heldout_supported_claim_coverage") == 1.0
        and reference.get("development_supported_correct_model_rate") == 1.0
        and reference.get("heldout_supported_correct_model_rate") == 1.0
        and reference.get("development_unsupported_refusal_rate") == 1.0
        and reference.get("heldout_unsupported_refusal_rate") == 1.0
        and reference.get("development_false_discovery_rate") == 0.0
        and reference.get("heldout_false_discovery_rate") == 0.0
        and reference.get("development_interval_coverage") == 1.0
        and reference.get("heldout_interval_coverage") == 1.0
        and reference.get("development_true_hypothesis_retention_rate") == 1.0
        and reference.get("heldout_true_hypothesis_retention_rate") == 1.0
        and reference.get("development_premature_elimination_rate") == 0.0
        and reference.get("heldout_premature_elimination_rate") == 0.0
        and len(reference.get("per_world") or []) == 12
        and screening.get("early_ambiguity_passed") is True
        and screening.get("supported_model_discrimination_passed") is True
        and screening.get("unsupported_refusal_passed") is True
        and screening.get("interval_coverage_passed") is True
        and screening.get("hypothesis_retention_passed") is True
        and screening.get("passed") is True
        and len(screening.get("records") or []) == 12
        and acquisition.get("passed") is True
        and len(acquisition.get("records") or []) == 12
        and float(acquisition.get("minimum_acquisition_quality_gain", 0.0)) > 0.37
        and pair_checks.get("passed") is True
        and len(pair_checks.get("records") or []) == 2
        and virial_checks.get("passed") is True
        and len(virial_checks.get("records") or []) == 2
        and isolation.get("fresh_process_per_world_passed") is True
        and isolation.get("fail_closed_passed") is True
        and isolation.get("passed") is True
        and len(isolation.get("records") or []) == 7
        and set(task_hashes) == expected_hash_paths
        and task_hashes.get(
            historical_task_path + "/solution.py"
        ) == BASELINE_SHA256
    ):
        raise ValueError("ForceFieldCalibration-v2 task calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "evidence_scope": document["evidence_scope"],
        "task_dimensions": dimensions,
        "task_source_sha256": task_hashes,
        "weak_baseline": _science(baseline),
        "truth_blind_reference": _science(reference),
        "truth_blind_reference_worlds": _world_summary(reference),
        "screening_and_reference_checks": {
            "record_count": len(screening["records"]),
            "early_ambiguity_passed": screening["early_ambiguity_passed"],
            "supported_model_discrimination_passed": screening[
                "supported_model_discrimination_passed"
            ],
            "unsupported_refusal_passed": screening[
                "unsupported_refusal_passed"
            ],
            "interval_coverage_passed": screening["interval_coverage_passed"],
            "hypothesis_retention_passed": screening[
                "hypothesis_retention_passed"
            ],
            "passed": screening["passed"],
        },
        "acquisition_contrast_checks": {
            "record_count": len(acquisition["records"]),
            "minimum_acquisition_quality_gain": acquisition[
                "minimum_acquisition_quality_gain"
            ],
            "passed": acquisition["passed"],
        },
        "independent_pair_energy_force_checks": pair_checks,
        "independent_second_virial_boyle_checks": virial_checks,
        "secure_isolation_and_failure_checks": isolation,
        "limitations": document.get("limitations") or [],
    }


def _load_model(label: str, relative: str) -> dict[str, Any]:
    report_path = ROOT / relative
    document = json.loads(report_path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("passed") is True
        and document.get("trusted_evidence") is True
        and provenance.get("git_revision") == INPUT_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
    ):
        raise ValueError("untrusted force-field model report: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one successful force-field run")
    run = runs[0]
    config = document.get("config") or {}
    expected_mode = (
        "selection_blind" if label == "blind_budget_three" else "normal"
    )
    expected_budget = 1 if label == "budget_one" else 3
    expected_seed = 0 if label == "budget_one" else 1
    if not (
        run.get("task") == TASK
        and run.get("algorithm") == "greedy_rewrite"
        and run.get("feedback_mode") == expected_mode
        and run.get("seed") == expected_seed
        and config.get("budget") == expected_budget
        and config.get("llm", {}).get("model") == "gpt-5.5"
        and config.get("llm", {}).get("server_side_seed_control") is False
    ):
        raise ValueError("unexpected force-field calibration condition")

    workdir = Path(run["workdir"]).resolve()
    try:
        relative_workdir = workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("force-field workdir is outside repository") from exc
    trajectory_path = workdir / "trajectory.jsonl"
    raw_events = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable force-field snapshot differs from raw trajectory")
    if len(raw_events) != expected_budget + 1:
        raise ValueError("force-field trajectory is incomplete")

    trajectory = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
            and int(compact["step"]) == int(raw["step"])
        ):
            raise ValueError("raw and portable force-field lineage differs")
        metrics = raw.get("metrics") or {}
        science = _science(metrics)
        if any(
            value is not None and not _finite_number(value)
            for value in science.values()
        ):
            raise ValueError("force-field science metric is non-finite")
        worlds = _world_summary(metrics)
        valid = bool(raw.get("valid")) and metrics.get("valid") == 1.0
        trajectory.append({
            "step": int(raw["step"]),
            "oracle_calls": int(raw["oracle_calls"]),
            "budget_units": int(raw["budget_units"]),
            "score": float(raw["score"]),
            "best_score": float(raw["best_score"]),
            "valid": valid,
            "accepted": bool(raw["accepted"]),
            "candidate_sha256": raw["candidate_sha256"],
            "parent_sha256": raw["parent_sha256"],
            "failure_kind": _failure_kind(raw),
            "infrastructure_failure": bool(
                metrics.get("infrastructure_failure")
            ),
            "science_metrics": science,
            "world_metrics": worlds,
            "valid_world_count": sum(bool(row["valid"]) for row in worlds),
            "invalid_world_count": sum(not bool(row["valid"]) for row in worlds),
            "llm": raw.get("llm") or {},
            "algorithm_metadata": raw.get("algorithm_metadata") or {},
        })

    summary = run.get("summary") or {}
    summary_path = workdir / "summary.json"
    stored_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if stored_summary != summary:
        raise ValueError("stored summary differs from report summary")
    manifest_path = workdir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checkpoint_path = workdir / "checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if expected_mode == "selection_blind" else "online_incumbent"
    )
    best_program = workdir / "best_program.py"
    terminal_program = workdir / "solution.py"
    best_hash = _sha256(best_program)
    terminal_hash = _sha256(terminal_program)
    selected_events = [
        event for event in trajectory if event["candidate_sha256"] == best_hash
    ]
    if len(selected_events) != 1:
        raise ValueError("force-field best program does not bind one event")
    selected = selected_events[0]
    proposals = trajectory[1:]
    failure_counts: dict[str, int] = {}
    for event in proposals:
        if event["failure_kind"]:
            failure_counts[event["failure_kind"]] = (
                failure_counts.get(event["failure_kind"], 0) + 1
            )
    scans = {
        "best_program": _source_scan(best_program),
        "terminal_program": _source_scan(terminal_program),
    }
    checkpoint_program = checkpoint.get("best_program")
    checkpoint_program_hash = (
        _sha256_text(checkpoint_program)
        if isinstance(checkpoint_program, str) else None
    )
    record = {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(report_path),
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "llm_condition_sha256": config.get("llm_condition_sha256"),
        "model": config.get("llm", {}).get("model"),
        "server_side_seed_control": False,
        "feedback_mode": expected_mode,
        "feedback_scope": summary.get("feedback_scope"),
        "selection_policy": summary.get("selection_policy"),
        "seed": expected_seed,
        "proposal_budget": expected_budget,
        "oracle_calls": int(summary["oracle_calls"]),
        "budget_units": int(summary["budget_units"]),
        "llm_calls": int(summary["llm"]["calls"]),
        "provider_usage_records": int(
            summary["llm"]["provider_usage_records"]
        ),
        "input_tokens": summary["llm"].get("input_tokens"),
        "output_tokens": summary["llm"].get("output_tokens"),
        "total_tokens": summary["llm"].get("total_tokens"),
        "wall_seconds": float(summary["wall_seconds"]),
        "baseline_score": float(run["baseline"]),
        "best_score": float(run["best"]),
        "best_so_far_auc": float(summary["best_so_far_auc"]),
        "accepted_proposals": int(run["accepted"]),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "run_manifest_sha256": _sha256(manifest_path),
        "checkpoint_sha256": _sha256(checkpoint_path),
        "summary_sha256": _sha256(summary_path),
        "task_contract_sha256": manifest.get("task_contract_sha256"),
        "runtime_source_sha256": manifest.get("runtime_source_sha256"),
        "baseline_candidate_sha256": trajectory[0]["candidate_sha256"],
        "best_program": str(relative_workdir / "best_program.py"),
        "best_program_sha256": best_hash,
        "terminal_program": str(relative_workdir / "solution.py"),
        "terminal_program_sha256": terminal_hash,
        "checkpoint_best_program_sha256": checkpoint_program_hash,
        "selected_step": selected["step"],
        "selected_origin": "baseline" if selected["step"] == 0 else "proposal",
        "selected_candidate_sha256": selected["candidate_sha256"],
        "selected_metrics": selected["science_metrics"],
        "terminal_candidate_sha256": trajectory[-1]["candidate_sha256"],
        "proposal_count": len(proposals),
        "valid_proposal_count": sum(event["valid"] for event in proposals),
        "invalid_proposal_count": sum(not event["valid"] for event in proposals),
        "failure_counts": dict(sorted(failure_counts.items())),
        "infrastructure_failure_count": sum(
            event["infrastructure_failure"] for event in proposals
        ),
        "trajectory": trajectory,
        "retained_artifact_scans": scans,
        "artifact_retention_scope": (
            "selected best source, checkpoint best source and terminal proposal "
            "source are retained; intermediate proposal sources are not retained, "
            "but candidate hashes, frozen/online parent lineage, sanitized failure "
            "kinds, accounting and full raw-trajectory hashes remain bound"
        ),
    }
    baseline = trajectory[0]
    invalid_submission_events = [
        event for event in proposals
        if event["failure_kind"] == "invalid_submission"
    ]
    full_world_failure_valid = all(
        event["valid_world_count"] == 0
        and event["invalid_world_count"] == 12
        and event["science_metrics"]["candidate_instance_call_count"] == 12.0
        and event["science_metrics"]["candidate_instance_valid_rate"] == 0.0
        and {row["failure_kind"] for row in event["world_metrics"]}
        == {"invalid_submission"}
        for event in invalid_submission_events
    )
    non_world_failures_valid = all(
        event["world_metrics"] == []
        and event["score"] == -1.0e18
        for event in proposals
        if event["failure_kind"] in {
            "candidate_runtime_error", "blocked_or_missing_import"
        }
    )
    record["integrity_passed"] = bool(
        _lineage_is_valid(record)
        and record["selection_policy"] == expected_policy
        and record["oracle_calls"] == expected_budget + 1
        and record["budget_units"] == expected_budget + 1
        and record["llm_calls"] == expected_budget
        and record["provider_usage_records"] == expected_budget
        and int(run["evaluated"]) == expected_budget + 1
        and record["accepted_proposals"] == 0
        and record["valid_proposal_count"] == 0
        and record["failure_counts"] == EXPECTED_FAILURE_COUNTS[label]
        and record["infrastructure_failure_count"] == 0
        and record["baseline_score"] == record["best_score"] == 0.0
        and record["best_so_far_auc"] == 0.0
        and record["selected_step"] == 0
        and selected["valid"]
        and baseline["valid_world_count"] == 12
        and baseline["invalid_world_count"] == 0
        and baseline["science_metrics"]["candidate_instance_call_count"] == 12.0
        and baseline["science_metrics"]["candidate_instance_valid_rate"] == 1.0
        and len(invalid_submission_events)
        == EXPECTED_FAILURE_COUNTS[label].get("invalid_submission", 0)
        and full_world_failure_valid
        and non_world_failures_valid
        and record["baseline_candidate_sha256"] == BASELINE_SHA256
        and record["best_program_sha256"] == BASELINE_SHA256
        and record["terminal_program_sha256"]
        == record["terminal_candidate_sha256"]
        and checkpoint.get("schema_version") == 1
        and checkpoint.get("algorithm") == "greedy_rewrite"
        and checkpoint.get("task_id") == TASK
        and checkpoint.get("seed") == expected_seed
        and checkpoint.get("next_iter") == expected_budget + 1
        and checkpoint.get("baseline_score") == 0.0
        and checkpoint.get("best_score") == 0.0
        and checkpoint.get("best_sha256") == BASELINE_SHA256
        and checkpoint_program_hash == BASELINE_SHA256
        and checkpoint_program == best_program.read_text(encoding="utf-8")
        and all(scan["syntax_valid"] for scan in scans.values())
        and all(scan["shortcut_safe"] for scan in scans.values())
        and manifest.get("task_id") == TASK
        and manifest.get("feedback_mode") == expected_mode
        and manifest.get("seed") == expected_seed
        and manifest.get("llm_condition_sha256")
        == config.get("llm_condition_sha256")
        and record["task_contract_sha256"] is not None
        and record["runtime_source_sha256"] is not None
    )
    if not record["integrity_passed"]:
        raise ValueError("force-field lineage, artifact or accounting gate failed")
    return record


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    runtime_source_equivalent: bool = True,
    runtime_source_changes: list[str] | None = None,
    runtime_migration: dict[str, Any] | None = None,
    calibration_source_revision: str = INPUT_SOURCE_REVISION,
    model_source_revision: str = INPUT_SOURCE_REVISION,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    conditions = {record["llm_condition_sha256"] for record in records.values()}
    contracts = {record["task_contract_sha256"] for record in records.values()}
    runtimes = {record["runtime_source_sha256"] for record in records.values()}
    proposals = [
        event for record in records.values() for event in record["trajectory"][1:]
    ]
    failure_counts: dict[str, int] = {}
    for event in proposals:
        if event["failure_kind"]:
            failure_counts[event["failure_kind"]] = (
                failure_counts.get(event["failure_kind"], 0) + 1
            )
    retained_hashes = {
        record[key]
        for record in records.values()
        for key in ("best_program_sha256", "terminal_program_sha256")
    }
    proposal_hashes = {event["candidate_sha256"] for event in proposals}
    retained_proposal_hashes = retained_hashes & proposal_hashes
    scans = [
        scan
        for record in records.values()
        for scan in record["retained_artifact_scans"].values()
    ]
    normal_selected = normal["selected_metrics"]
    blind_selected = blind["selected_metrics"]
    science_contrast = {
        field: normal_selected[field] - blind_selected[field]
        for field in SCIENCE_FIELDS
        if _finite_number(normal_selected.get(field))
        and _finite_number(blind_selected.get(field))
    }
    contrast = {
        "selected_science_metrics": science_contrast,
        "best_score": normal["best_score"] - blind["best_score"],
        "best_so_far_auc": (
            normal["best_so_far_auc"] - blind["best_so_far_auc"]
        ),
        "valid_proposal_count": (
            normal["valid_proposal_count"] - blind["valid_proposal_count"]
        ),
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
        "input_tokens": normal["input_tokens"] - blind["input_tokens"],
        "output_tokens": normal["output_tokens"] - blind["output_tokens"],
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "wall_seconds": normal["wall_seconds"] - blind["wall_seconds"],
    }
    terminal_missing_imports = {
        label: record["retained_artifact_scans"]["terminal_program"][
            "known_missing_import_symbols"
        ]
        for label, record in records.items()
    }
    execution_passed = bool(
        calibration["source_revision"] == calibration_source_revision
        and revisions == {model_source_revision}
        and runtime_source_equivalent
        and len(scopes) == 1
        and len(conditions) == 1
        and None not in conditions
        and len(contracts) == 1
        and None not in contracts
        and len(runtimes) == 1
        and None not in runtimes
        and all(record["integrity_passed"] for record in records.values())
        and all(scan["shortcut_safe"] for scan in scans)
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["seed"] == 0
        and normal["seed"] == blind["seed"] == 1
        and one["feedback_mode"] == normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and one["oracle_calls"] == 2
        and normal["oracle_calls"] == blind["oracle_calls"] == 4
        and len(proposals) == 7
        and not any(event["valid"] for event in proposals)
        and failure_counts == {
            "blocked_or_missing_import": 1,
            "candidate_runtime_error": 5,
            "invalid_submission": 1,
        }
        and not any(event["infrastructure_failure"] for event in proposals)
        and all(record["best_score"] == 0.0 for record in records.values())
        and all(record["accepted_proposals"] == 0 for record in records.values())
        and all(record["selected_step"] == 0 for record in records.values())
        and len({
            record["baseline_candidate_sha256"] for record in records.values()
        }) == 1
        and len(retained_proposal_hashes) == 3
        and len(proposal_hashes - retained_hashes) == 4
        and one["total_tokens"] == 7020
        and normal["total_tokens"] == 21309
        and blind["total_tokens"] == 21952
        and normal["input_tokens"] == blind["input_tokens"] == 6789
        and terminal_missing_imports == {
            "budget_one": [],
            "normal_budget_three": [],
            "blind_budget_three": ["scipy.optimize.quad"],
        }
    )
    condition_decomposition = {
        label: {
            "selected_artifact": _decomposition(record["selected_metrics"]),
            "proposal_outcomes": [
                {
                    "step": event["step"],
                    "candidate_sha256": event["candidate_sha256"],
                    "parent_sha256": event["parent_sha256"],
                    "score": event["score"],
                    "valid": event["valid"],
                    "failure_kind": event["failure_kind"],
                    "valid_world_count": event["valid_world_count"],
                    "invalid_world_count": event["invalid_world_count"],
                }
                for event in record["trajectory"][1:]
            ],
        }
        for label, record in records.items()
    }
    reference = calibration["truth_blind_reference"]
    baseline = calibration["weak_baseline"]
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "SINGLE_RUN_SYNTHETIC_ACTIVE_FORCE_FIELD_HYPOTHESIS_CALIBRATION_"
            "NOT_FEEDBACK_CAUSAL_MODEL_RANKING_MOLECULAR_DYNAMICS_MATERIAL_"
            "THERMODYNAMIC_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "model_source_revision": model_source_revision,
        "input_task_runtime_source_equivalent": runtime_source_equivalent,
        "input_task_runtime_source_changes": runtime_source_changes or [],
        "input_task_runtime_source_migration": runtime_migration,
        "input_source_scope_equivalent": len(scopes) == 1,
        "input_llm_condition_equivalent": len(conditions) == 1,
        "input_task_contract_equivalent": len(contracts) == 1,
        "input_runtime_manifest_equivalent": len(runtimes) == 1,
        "task_calibration": calibration,
        "records": records,
        "proposal_hurdle_summary": {
            "proposal_count": len(proposals),
            "valid_proposal_count": sum(event["valid"] for event in proposals),
            "invalid_proposal_count": sum(
                not event["valid"] for event in proposals
            ),
            "failure_counts": dict(sorted(failure_counts.items())),
            "invalid_submission_count": failure_counts.get(
                "invalid_submission", 0
            ),
            "candidate_runtime_error_count": failure_counts.get(
                "candidate_runtime_error", 0
            ),
            "blocked_or_missing_import_count": failure_counts.get(
                "blocked_or_missing_import", 0
            ),
            "infrastructure_failure_count": sum(
                event["infrastructure_failure"] for event in proposals
            ),
            "full_world_invalid_submission_count": sum(
                event["failure_kind"] == "invalid_submission"
                and event["invalid_world_count"] == 12
                for event in proposals
            ),
        },
        "retained_artifact_summary": {
            "best_source_count": len(records),
            "checkpoint_source_count": len(records),
            "terminal_source_count": len(records),
            "all_retained_sources_parse": all(
                scan["syntax_valid"] for scan in scans
            ),
            "all_retained_shortcut_scans_passed": all(
                scan["shortcut_safe"] for scan in scans
            ),
            "retained_proposal_source_count": len(retained_proposal_hashes),
            "unretained_proposal_source_count": len(
                proposal_hashes - retained_hashes
            ),
            "terminal_known_missing_import_symbols": terminal_missing_imports,
        },
        "condition_science_decomposition": condition_decomposition,
        "normal_minus_blind_budget_three_descriptive_contrast": contrast,
        "reference_gap_context": {
            "weak_baseline": _decomposition(baseline),
            "truth_blind_reference": _decomposition(reference),
            "development_score_gap": (
                reference["combined_score"] - baseline["combined_score"]
            ),
            "heldout_score_gap": (
                reference["heldout_policy_score"]
                - baseline["heldout_policy_score"]
            ),
            "development_robustness_gap": (
                reference["robustness_score"] - baseline["robustness_score"]
            ),
            "heldout_robustness_gap": (
                reference["heldout_robustness_score"]
                - baseline["heldout_robustness_score"]
            ),
        },
        "descriptive_findings": {
            "all_seven_model_proposals_are_invalid": (
                len(proposals) == 7
                and not any(event["valid"] for event in proposals)
            ),
            "one_proposal_reaches_all_worlds_but_returns_invalid_submissions": (
                sum(
                    event["failure_kind"] == "invalid_submission"
                    and event["invalid_world_count"] == 12
                    for event in proposals
                ) == 1
            ),
            "six_proposals_fail_before_world_level_science_metrics": (
                sum(not event["world_metrics"] for event in proposals) == 6
            ),
            "five_proposals_are_candidate_runtime_errors": (
                failure_counts.get("candidate_runtime_error") == 5
            ),
            "one_terminal_proposal_has_known_missing_scipy_import": (
                terminal_missing_imports["blind_budget_three"]
                == ["scipy.optimize.quad"]
            ),
            "no_infrastructure_failure": not any(
                event["infrastructure_failure"] for event in proposals
            ),
            "all_conditions_retain_the_weak_baseline": all(
                record["selected_step"] == 0 for record in records.values()
            ),
            "normal_budget_three_online_parent_never_changes": all(
                event["parent_sha256"] == normal["baseline_candidate_sha256"]
                for event in normal["trajectory"][1:]
            ),
            "selection_blind_uses_frozen_parent": all(
                event["parent_sha256"] == blind["baseline_candidate_sha256"]
                for event in blind["trajectory"][1:]
            ),
            "normal_and_blind_are_oracle_call_matched": (
                contrast["oracle_calls"] == 0
            ),
            "normal_and_blind_are_input_token_matched": (
                contrast["input_tokens"] == 0
            ),
            "normal_and_blind_are_total_token_matched": (
                contrast["total_tokens"] == 0
            ),
            "truth_blind_reference_resolves_supported_and_unsupported_worlds": (
                reference["development_supported_correct_model_rate"] == 1.0
                and reference["heldout_supported_correct_model_rate"] == 1.0
                and reference["development_unsupported_refusal_rate"] == 1.0
                and reference["heldout_unsupported_refusal_rate"] == 1.0
                and reference["development_false_discovery_rate"] == 0.0
                and reference["heldout_false_discovery_rate"] == 0.0
            ),
            "feedback_effect_identified": False,
            "force_field_or_autonomous_discovery_demonstrated": False,
        },
        "limitations": [
            "Each condition has one run; no confidence interval, population, leaderboard, model-ranking or scaling-law estimate is supported.",
            "The Azure endpoint exposes no server-side generation seed, so equal local seed labels do not pair model randomness.",
            "Normal and selection-blind match oracle calls, local seed labels and input-token totals but differ in feedback semantics, generated sources, output tokens and wall time; their contrast is descriptive, not causal.",
            "Because normal accepted no proposal, its online incumbent remained the baseline; this observed lineage does not substitute for a randomized feedback intervention.",
            "Budget one uses a different local seed label and is an independent calibration, not a prefix of budget three.",
            "Candidate exception text is intentionally sanitized. Five failures can only be called candidate_runtime_error; the retained blind terminal source separately exposes one invalid scipy.optimize.quad import.",
            "Only the terminal proposal source from each condition is retained. Four intermediate proposal bodies are unavailable, so hashes and sanitized failure classes do not justify narrower diagnoses.",
            "The single invalid_submission proposal ran three query calls using eleven configuration units in every world, but its rejected output supports no model, parameter, interval, prediction or thermodynamic claim.",
            "The truth-blind reference is a reproducible normalization witness, not a globally optimal active policy, a material force field or a scientific discovery.",
            "The task is a deterministic three-particle reduced-order laboratory with repository-visible generators, not molecular dynamics, electronic structure, a thermodynamic measurement or experimental validation.",
            "Scientific or discovery claims require server-held cohorts, contamination auditing, many-particle and ab-initio or experimental validation, prospective replication and independent domain review.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def analyze() -> dict[str, Any]:
    calibration = _load_calibration(CALIBRATION)
    records = {
        label: _load_model(label, relative)
        for label, relative in REPORTS.items()
    }
    current_revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
    ).strip()
    changes = _source_changes(INPUT_SOURCE_REVISION, current_revision)
    migration = runtime_migration_status(
        INPUT_SOURCE_REVISION, current_revision, changes,
    ) if changes else None
    equivalent = bool(not changes or (migration or {}).get("accepted") is True)
    return _analyze_records(
        calibration,
        records,
        runtime_source_equivalent=equivalent,
        runtime_source_changes=changes,
        runtime_migration=migration,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze()
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
