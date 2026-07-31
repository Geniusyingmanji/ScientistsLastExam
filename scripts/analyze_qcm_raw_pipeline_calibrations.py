#!/usr/bin/env python3
"""Bind and analyze the three QuartzCrystalMicrobalanceLab GPT-5.5 runs.

These are single descriptive calibrations. Equal local seed labels do not
control Azure generation randomness, so normal versus selection-blind
differences are not feedback effects, rankings, or scaling-law evidence.
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

from frontier_science.protocol import (  # noqa: E402
    compact_trajectory_snapshot,
    load_trajectory,
)
from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)
from frontier_science.runtime_migration import runtime_source_changes  # noqa: E402


TASK = "Sensors/QuartzCrystalMicrobalanceLab"
CALIBRATION = "experiments/qcm_raw_pipeline_calibration_2026-07-25.json"
REPORTS = {
    "budget_one": "experiments/gpt55_qcm_raw_pipeline_v1_b1_2026-07-25.json",
    "normal_budget_three": (
        "experiments/gpt55_qcm_raw_pipeline_v1_b3_2026-07-25.json"
    ),
    "blind_budget_three": (
        "experiments/gpt55_qcm_raw_pipeline_v1_blind_b3_2026-07-25.json"
    ),
}
INPUT_SOURCE_REVISION = "c49f5143b9b3487b9a66ec21e09fe9253a6c303b"
TASK_RUNTIME_SCOPE = (
    ":(glob)frontier_science/**/*.py",
    "benchmarks/Engineering/QuartzCrystalMicrobalanceLab",
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
    "development_lineage_score",
    "heldout_lineage_score",
    "development_calibration_score",
    "heldout_calibration_score",
    "development_extraction_score",
    "heldout_extraction_score",
    "development_mechanism_score",
    "heldout_mechanism_score",
    "development_prediction_score",
    "heldout_prediction_score",
    "development_decision_score",
    "heldout_decision_score",
    "development_robust_prediction_score",
    "heldout_robust_prediction_score",
    "development_robust_decision_score",
    "heldout_robust_decision_score",
    "development_supported_claim_coverage",
    "heldout_supported_claim_coverage",
    "development_unsupported_refusal_rate",
    "heldout_unsupported_refusal_rate",
    "development_false_discovery_rate",
    "heldout_false_discovery_rate",
    "development_fault_diagnosis_accuracy",
    "heldout_fault_diagnosis_accuracy",
    "development_confidence_score",
    "heldout_confidence_score",
    "development_reference_preprocessor_score",
    "heldout_reference_preprocessor_score",
    "development_oracle_clean_feature_score",
    "heldout_oracle_clean_feature_score",
    "development_mean_calibration_rms_counts",
    "heldout_mean_calibration_rms_counts",
    "development_mean_saturation_fraction",
    "heldout_mean_saturation_fraction",
    "development_mean_missing_fraction",
    "heldout_mean_missing_fraction",
    "candidate_instance_call_count",
    "candidate_instance_valid_rate",
)
WORLD_FIELDS = (
    "split",
    "world_index",
    "kind",
    "valid",
    "failure_kind",
    "lineage_quality",
    "calibration_quality",
    "extraction_quality",
    "mechanism_quality",
    "prediction_quality",
    "decision_quality",
    "robust_prediction_quality",
    "robust_decision_quality",
    "diagnosis_quality",
    "joint_quality",
    "robust_joint_quality",
    "correct_refusal",
    "false_discovery",
    "abstained",
    "confidence",
    "confidence_score",
    "calibration_rms_counts",
    "saturation_fraction",
    "missing_fraction",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _shortcut_scan(path: Path) -> dict[str, Any]:
    """Reject retained programs containing fixed worlds or evaluator access."""

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    constants = {
        str(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, (str, int))
        and not isinstance(node.value, bool)
    }
    fixed_worlds = {
        "31801", "31813", "31827", "31837", "31849", "31859",
        "41809", "41821", "41833", "41843",
    }
    literal_hits = sorted(fixed_worlds & constants)
    lower = source.lower()
    evaluator_terms = (
        "verification/evaluator",
        "evaluator.py",
        "_make_world",
        "_truth_by_sweep",
        "_reference_pipeline",
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
    return {
        "source_sha256": _sha256(path),
        "fixed_world_literal_hits": literal_hits,
        "evaluator_source_term_hits": evaluator_hits,
        "dynamic_source_import_hits": suspicious_imports,
        "dynamic_source_call_hits": suspicious_calls,
        "passed": not (
            literal_hits or evaluator_hits or suspicious_imports or suspicious_calls
        ),
    }


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    dimensions = document.get("task_dimensions") or {}
    baseline = document.get("direct_weak_baseline") or {}
    secure = document.get("secure_weak_baseline") or {}
    reference = document.get("truth_blind_reference") or {}
    resonance = document.get("independent_resonance_checks") or {}
    affine = document.get("complex_affine_calibration_checks") or {}
    classification = document.get("classification_and_missingness_checks") or {}
    robustness = document.get("sealed_robustness_shift_checks") or {}
    isolation = document.get("secure_isolation_and_failure_checks") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("passed") is True
        and document.get("trusted_evidence") is True
        and provenance.get("git_revision") == INPUT_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and document.get("task") == TASK
        and dimensions.get("development_world_count") == 6
        and dimensions.get("heldout_world_count") == 4
        and dimensions.get("harmonic_count") == 3
        and dimensions.get("deposition_time_count") == 3
        and dimensions.get("sweep_count_per_world") == 9
        and dimensions.get("supported_world_count") == 5
        and dimensions.get("physical_anomaly_world_count") == 3
        and dimensions.get("instrument_fault_world_count") == 2
        and document.get("secure_baseline_exactly_matches_direct") is True
        and baseline.get("valid") == 1.0
        and baseline.get("combined_score") == 0.0
        and secure.get("combined_score") == 0.0
        and resonance.get("passed") is True
        and affine.get("passed") is True
        and classification.get("passed") is True
        and classification.get("missing_supported_recovery_passed") is True
        and classification.get("physical_anomaly_classification_passed") is True
        and classification.get("instrument_fault_classification_passed") is True
        and robustness.get("passed") is True
        and isolation.get("passed") is True
        and isolation.get("fresh_process_per_world_passed") is True
        and isolation.get("fail_closed_passed") is True
        and reference.get("valid") == 1.0
        and float(reference.get("combined_score", 0.0)) > 0.99
        and float(reference.get("heldout_policy_score", 0.0)) > 0.99
        and float(reference.get("robustness_score", 0.0)) > 0.90
        and float(reference.get("heldout_robustness_score", 0.0)) > 0.90
        and reference.get("development_supported_claim_coverage") == 1.0
        and reference.get("heldout_supported_claim_coverage") == 1.0
        and reference.get("development_unsupported_refusal_rate") == 1.0
        and reference.get("heldout_unsupported_refusal_rate") == 1.0
        and reference.get("development_fault_diagnosis_accuracy") == 1.0
        and reference.get("heldout_fault_diagnosis_accuracy") == 1.0
        and reference.get("development_false_discovery_rate") == 0.0
        and reference.get("heldout_false_discovery_rate") == 0.0
        and len(reference.get("per_world") or []) == 10
    ):
        raise ValueError("QuartzCrystalMicrobalanceLab calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "evidence_scope": document["evidence_scope"],
        "task_dimensions": dimensions,
        "task_source_sha256": document.get("task_source_sha256"),
        "weak_baseline": _science(baseline),
        "truth_blind_reference": _science(reference),
        "truth_blind_reference_worlds": _world_summary(reference),
        "independent_resonance_checks": resonance,
        "complex_affine_calibration_checks": affine,
        "classification_and_missingness_checks": classification,
        "sealed_robustness_shift_checks": robustness,
        "secure_isolation_and_failure_checks": isolation,
        "limitations": document.get("limitations") or [],
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


def _all_refusal(metrics: dict[str, Any]) -> bool:
    return bool(
        metrics.get("development_supported_claim_coverage") == 0.0
        and metrics.get("heldout_supported_claim_coverage") == 0.0
        and metrics.get("development_unsupported_refusal_rate") == 1.0
        and metrics.get("heldout_unsupported_refusal_rate") == 1.0
        and metrics.get("development_false_discovery_rate") == 0.0
        and metrics.get("heldout_false_discovery_rate") == 0.0
    )


def _zero_science_pipeline(metrics: dict[str, Any]) -> bool:
    return all(metrics.get(field) == 0.0 for field in (
        "development_calibration_score",
        "heldout_calibration_score",
        "development_extraction_score",
        "heldout_extraction_score",
        "development_mechanism_score",
        "heldout_mechanism_score",
        "development_prediction_score",
        "heldout_prediction_score",
        "development_decision_score",
        "heldout_decision_score",
    ))


def _decomposition(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "score": {
            "development_joint": metrics.get("combined_score"),
            "development_robust": metrics.get("robustness_score"),
            "heldout_joint": metrics.get("heldout_policy_score"),
            "heldout_robust": metrics.get("heldout_robustness_score"),
        },
        "raw_pipeline": {
            "development_calibration": metrics.get(
                "development_calibration_score"
            ),
            "heldout_calibration": metrics.get("heldout_calibration_score"),
            "development_extraction": metrics.get(
                "development_extraction_score"
            ),
            "heldout_extraction": metrics.get("heldout_extraction_score"),
        },
        "scientific_inference": {
            "development_mechanism": metrics.get(
                "development_mechanism_score"
            ),
            "heldout_mechanism": metrics.get("heldout_mechanism_score"),
            "development_prediction": metrics.get(
                "development_prediction_score"
            ),
            "heldout_prediction": metrics.get("heldout_prediction_score"),
            "development_decision": metrics.get("development_decision_score"),
            "heldout_decision": metrics.get("heldout_decision_score"),
            "development_shifted_prediction": metrics.get(
                "development_robust_prediction_score"
            ),
            "heldout_shifted_prediction": metrics.get(
                "heldout_robust_prediction_score"
            ),
            "development_shifted_decision": metrics.get(
                "development_robust_decision_score"
            ),
            "heldout_shifted_decision": metrics.get(
                "heldout_robust_decision_score"
            ),
        },
        "claim_control": {
            "development_supported_coverage": metrics.get(
                "development_supported_claim_coverage"
            ),
            "heldout_supported_coverage": metrics.get(
                "heldout_supported_claim_coverage"
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
            "development_fault_diagnosis": metrics.get(
                "development_fault_diagnosis_accuracy"
            ),
            "heldout_fault_diagnosis": metrics.get(
                "heldout_fault_diagnosis_accuracy"
            ),
        },
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
        raise ValueError("untrusted QCM model report: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one successful QCM run")
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
        raise ValueError("unexpected QCM calibration condition")

    workdir = Path(run["workdir"]).resolve()
    try:
        relative_workdir = workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("QCM workdir is outside repository") from exc
    trajectory_path = workdir / "trajectory.jsonl"
    raw_events = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable QCM snapshot differs from raw trajectory")
    if len(raw_events) != expected_budget + 1:
        raise ValueError("QCM trajectory is incomplete")

    trajectory = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
            and int(compact["step"]) == int(raw["step"])
        ):
            raise ValueError("raw and portable QCM lineage differs")
        metrics = raw.get("metrics") or {}
        science = _science(metrics)
        if any(
            value is not None and not _finite_number(value)
            for value in science.values()
        ):
            raise ValueError("QCM science metric is non-finite")
        worlds = _world_summary(metrics)
        if len(worlds) != 10:
            raise ValueError("QCM event lacks all ten worlds")
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
    manifest_path = workdir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if expected_mode == "selection_blind" else "online_incumbent"
    )
    best_program = workdir / "best_program.py"
    terminal_program = workdir / "solution.py"
    best_hash = _sha256(best_program)
    selected_events = [
        event for event in trajectory if event["candidate_sha256"] == best_hash
    ]
    if len(selected_events) != 1:
        raise ValueError("QCM best program does not bind one event")
    selected = selected_events[0]
    proposals = trajectory[1:]
    valid_proposals = [event for event in proposals if event["valid"]]
    highest_valid = max(valid_proposals, key=lambda event: event["score"])
    failure_counts: dict[str, int] = {}
    for event in proposals:
        if event["failure_kind"]:
            failure_counts[event["failure_kind"]] = (
                failure_counts.get(event["failure_kind"], 0) + 1
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
        "task_contract_sha256": manifest.get("task_contract_sha256"),
        "runtime_source_sha256": manifest.get("runtime_source_sha256"),
        "best_program": str(relative_workdir / "best_program.py"),
        "best_program_sha256": best_hash,
        "terminal_program": str(relative_workdir / "solution.py"),
        "terminal_program_sha256": _sha256(terminal_program),
        "selected_step": selected["step"],
        "selected_origin": "baseline" if selected["step"] == 0 else "proposal",
        "selected_candidate_sha256": selected["candidate_sha256"],
        "selected_metrics": selected["science_metrics"],
        "highest_scoring_valid_proposal_step": highest_valid["step"],
        "highest_scoring_valid_proposal_sha256": highest_valid[
            "candidate_sha256"
        ],
        "highest_scoring_valid_proposal_metrics": highest_valid[
            "science_metrics"
        ],
        "terminal_candidate_sha256": trajectory[-1]["candidate_sha256"],
        "proposal_count": len(proposals),
        "valid_proposal_count": len(valid_proposals),
        "invalid_proposal_count": len(proposals) - len(valid_proposals),
        "valid_nonzero_proposal_count": sum(
            event["score"] > 0.0 for event in valid_proposals
        ),
        "valid_all_refusal_proposal_count": sum(
            _all_refusal(event["science_metrics"]) for event in valid_proposals
        ),
        "valid_zero_science_pipeline_proposal_count": sum(
            _zero_science_pipeline(event["science_metrics"])
            for event in valid_proposals
        ),
        "failure_counts": failure_counts,
        "infrastructure_failure_count": sum(
            event["infrastructure_failure"] for event in proposals
        ),
        "trajectory": trajectory,
        "retained_artifact_scans": {
            "best_program": _shortcut_scan(best_program),
            "terminal_program": _shortcut_scan(terminal_program),
        },
        "artifact_retention_scope": (
            "best and terminal sources are retained; intermediate proposal "
            "sources are not retained, but candidate hashes, parent lineage, "
            "per-world metrics, accounting and full raw-trajectory hashes remain bound"
        ),
    }
    record["integrity_passed"] = bool(
        _lineage_is_valid(record)
        and record["selection_policy"] == expected_policy
        and record["oracle_calls"] == expected_budget + 1
        and record["budget_units"] == expected_budget + 1
        and record["llm_calls"] == expected_budget
        and record["provider_usage_records"] == expected_budget
        and int(run["evaluated"]) == expected_budget + 1
        and record["accepted_proposals"] == int(run["accepted"])
        and abs(record["best_score"] - selected["score"]) < 1e-12
        and selected["valid"]
        and selected["valid_world_count"] == 10
        and all(event["valid_world_count"] == 10 for event in trajectory)
        and record["terminal_program_sha256"]
        == record["terminal_candidate_sha256"]
        and all(
            scan["passed"] for scan in record["retained_artifact_scans"].values()
        )
        and record["infrastructure_failure_count"] == 0
        and manifest.get("task_id") == TASK
        and manifest.get("feedback_mode") == expected_mode
        and manifest.get("seed") == expected_seed
        and manifest.get("llm_condition_sha256")
        == config.get("llm_condition_sha256")
        and record["task_contract_sha256"] is not None
        and record["runtime_source_sha256"] is not None
    )
    if not record["integrity_passed"]:
        raise ValueError("QCM lineage, artifact or accounting gate failed")
    return record


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    runtime_source_equivalent: bool = True,
    runtime_source_changes: list[str] | None = None,
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
    valid_proposals = [event for event in proposals if event["valid"]]
    failure_counts: dict[str, int] = {}
    for event in proposals:
        if event["failure_kind"]:
            failure_counts[event["failure_kind"]] = (
                failure_counts.get(event["failure_kind"], 0) + 1
            )
    contrast = {
        field: normal["selected_metrics"][field]
        - blind["selected_metrics"][field]
        for field in SCIENCE_FIELDS
    }
    contrast.update({
        "best_score": normal["best_score"] - blind["best_score"],
        "best_so_far_auc": (
            normal["best_so_far_auc"] - blind["best_so_far_auc"]
        ),
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "wall_seconds": normal["wall_seconds"] - blind["wall_seconds"],
        "valid_proposal_count": (
            normal["valid_proposal_count"] - blind["valid_proposal_count"]
        ),
    })
    all_refusal_count = sum(
        _all_refusal(event["science_metrics"]) for event in valid_proposals
    )
    zero_pipeline_count = sum(
        _zero_science_pipeline(event["science_metrics"])
        for event in valid_proposals
    )
    all_claim_count = sum(
        event["science_metrics"]["development_supported_claim_coverage"] == 1.0
        and event["science_metrics"]["heldout_supported_claim_coverage"] == 1.0
        and event["science_metrics"]["development_unsupported_refusal_rate"] == 0.0
        and event["science_metrics"]["heldout_unsupported_refusal_rate"] == 0.0
        for event in valid_proposals
    )
    partial_nontransfer_count = sum(
        0.0 < event["science_metrics"]["development_supported_claim_coverage"] < 1.0
        and event["science_metrics"]["heldout_supported_claim_coverage"] == 0.0
        for event in valid_proposals
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
        and all(scan["passed"] for scan in scans)
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["seed"] == 0
        and normal["seed"] == blind["seed"] == 1
        and one["feedback_mode"] == normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and one["oracle_calls"] == 2
        and normal["oracle_calls"] == blind["oracle_calls"] == 4
        and len(proposals) == 7
        and len(valid_proposals) == 7
        and failure_counts == {}
        and sum(event["infrastructure_failure"] for event in proposals) == 0
        and sum(event["score"] > 0.0 for event in valid_proposals) == 0
        and all_refusal_count == 5
        and zero_pipeline_count == 7
        and all_claim_count == 1
        and partial_nontransfer_count == 1
        and all(record["best_score"] == 0.0 for record in records.values())
        and all(record["accepted_proposals"] == 0 for record in records.values())
        and all(record["selected_step"] == 0 for record in records.values())
        and normal["total_tokens"] == 18662
        and blind["total_tokens"] == 17797
        and len(retained_proposal_hashes) == 3
        and len(proposal_hashes - retained_hashes) == 4
    )
    condition_decomposition = {
        label: {
            "selected_artifact": _decomposition(record["selected_metrics"]),
            "highest_scoring_valid_proposal": _decomposition(
                record["highest_scoring_valid_proposal_metrics"]
            ),
            "proposal_score_trajectory": [
                event["score"] for event in record["trajectory"][1:]
            ],
            "proposal_science_decomposition": [
                _decomposition(event["science_metrics"])
                for event in record["trajectory"][1:]
            ],
        }
        for label, record in records.items()
    }
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "SINGLE_RUN_SYNTHETIC_QCM_RAW_PIPELINE_CALIBRATION_NOT_CAUSAL_"
            "MODEL_RANKING_INSTRUMENT_FILM_MATERIAL_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "model_source_revision": model_source_revision,
        "input_task_runtime_source_equivalent": runtime_source_equivalent,
        "input_task_runtime_source_changes": runtime_source_changes or [],
        "input_source_scope_equivalent": len(scopes) == 1,
        "input_llm_condition_equivalent": len(conditions) == 1,
        "input_task_contract_equivalent": len(contracts) == 1,
        "input_runtime_manifest_equivalent": len(runtimes) == 1,
        "task_calibration": calibration,
        "records": records,
        "proposal_hurdle_summary": {
            "proposal_count": len(proposals),
            "valid_proposal_count": len(valid_proposals),
            "invalid_proposal_count": len(proposals) - len(valid_proposals),
            "valid_nonzero_proposal_count": sum(
                event["score"] > 0.0 for event in valid_proposals
            ),
            "valid_all_refusal_proposal_count": all_refusal_count,
            "valid_all_claim_proposal_count": all_claim_count,
            "valid_partial_development_nontransfer_proposal_count": (
                partial_nontransfer_count
            ),
            "valid_zero_science_pipeline_proposal_count": zero_pipeline_count,
            "failure_counts": failure_counts,
            "infrastructure_failure_count": sum(
                event["infrastructure_failure"] for event in proposals
            ),
        },
        "retained_artifact_summary": {
            "best_source_count": len(records),
            "terminal_source_count": len(records),
            "all_retained_scans_passed": all(scan["passed"] for scan in scans),
            "retained_proposal_source_count": len(retained_proposal_hashes),
            "unretained_proposal_source_count": len(
                proposal_hashes - retained_hashes
            ),
        },
        "condition_science_decomposition": condition_decomposition,
        "normal_minus_blind_budget_three_descriptive_contrast": contrast,
        "descriptive_findings": {
            "all_seven_proposals_are_valid_but_score_zero": bool(
                len(valid_proposals) == 7
                and all(event["score"] == 0.0 for event in valid_proposals)
            ),
            "all_seven_proposals_have_zero_normalized_raw_pipeline_and_inference": (
                zero_pipeline_count == 7
            ),
            "five_proposals_are_conservative_all_refusal": (
                all_refusal_count == 5
            ),
            "one_proposal_claims_every_world_and_has_false_discoveries": any(
                event["science_metrics"][
                    "development_supported_claim_coverage"
                ] == 1.0
                and event["science_metrics"][
                    "heldout_supported_claim_coverage"
                ] == 1.0
                and event["science_metrics"][
                    "development_unsupported_refusal_rate"
                ] == 0.0
                and event["science_metrics"][
                    "heldout_unsupported_refusal_rate"
                ] == 0.0
                and event["science_metrics"][
                    "development_false_discovery_rate"
                ] > 0.0
                and event["science_metrics"][
                    "heldout_false_discovery_rate"
                ] > 0.0
                for event in valid_proposals
            ),
            "one_proposal_has_partial_development_coverage_without_heldout_transfer": (
                partial_nontransfer_count == 1
            ),
            "all_conditions_retain_the_weak_baseline": all(
                record["selected_step"] == 0 for record in records.values()
            ),
            "normal_and_blind_are_oracle_call_matched": (
                contrast["oracle_calls"] == 0
            ),
            "normal_and_blind_are_token_matched": (
                contrast["total_tokens"] == 0
            ),
            "feedback_effect_identified": False,
            "qcm_instrument_film_or_autonomous_discovery_demonstrated": False,
        },
        "limitations": [
            "Each condition has one run; no confidence interval, population, leaderboard, model-ranking or scaling-law estimate is supported.",
            "The Azure endpoint exposes no server-side generation seed, so equal local seed labels do not pair model randomness.",
            "Normal and selection-blind match oracle calls but differ in tokens, prompts, histories and wall time; their contrast is descriptive, not causal.",
            "Selection-blind performs offline best-of-three selection over proposals that all see the frozen baseline; it is not a deployed sequential policy.",
            "Budget one uses a different local seed label and is an independent calibration, not a prefix of budget three.",
            "Calibration, extraction, mechanism, prediction, decision, robustness, held-out, refusal, fault and per-world metrics were evaluator-only.",
            "Four intermediate proposal source bodies were not retained; raw-trajectory, candidate, parent and report hashes bind outcomes but do not permit source-level shortcut inspection.",
            "The truth-blind reference is a reproducible normalization witness, not an autonomous agent, a physical QCM instrument or a discovered film/material law.",
            "The deterministic BVD/Sauerbrey simulator omits temperature, roughness, fluid loading, distributed films, nonlinear electronics and actuator safety.",
            "Engineering or discovery claims require server-held traces, contamination auditing, independent sensing/thin-film review and prospective physical replication.",
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
    return _analyze_records(
        calibration,
        records,
        runtime_source_equivalent=not changes,
        runtime_source_changes=changes,
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
