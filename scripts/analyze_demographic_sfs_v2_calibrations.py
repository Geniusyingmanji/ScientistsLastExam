#!/usr/bin/env python3
"""Bind and analyze the DemographicSFS-v2 GPT-5.5 calibrations.

The three model conditions are single descriptive runs on a synthetic finite-SFS
task.  This audit verifies input provenance, raw/portable trajectory agreement,
lineage, accounting, retained artifacts, and the separate fit, prediction,
mechanism, coverage, refusal, false-discovery, confidence and experiment axes.
Azure exposes no server-side generation seed, so the normal/open-loop contrast is
not treated as a causal feedback effect.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.protocol import compact_trajectory_snapshot, load_trajectory  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


TASK = "PopulationGenetics/DemographicSFS"
CALIBRATION_SOURCE_REVISION = "9a72b511311c04b26d39658e76cf2d1cc0cc3d3f"
MODEL_SOURCE_REVISION = "1c30a990e1e233acb7f93f53d0130856a7bab6d9"
CALIBRATION = "experiments/demographic_sfs_v2_calibration_2026-07-25_v2.json"
REPORTS = {
    "budget_one": "experiments/gpt55_demographic_sfs_v2_b1_2026-07-25.json",
    "normal_budget_three": "experiments/gpt55_demographic_sfs_v2_b3_2026-07-25.json",
    "blind_budget_three": (
        "experiments/gpt55_demographic_sfs_v2_blind_b3_2026-07-25.json"
    ),
}
EXPECTED_CONDITIONS = {
    "budget_one": {"mode": "normal", "budget": 1, "seed": 0},
    "normal_budget_three": {"mode": "normal", "budget": 3, "seed": 1},
    "blind_budget_three": {
        "mode": "selection_blind", "budget": 3, "seed": 1,
    },
}
TASK_RUNTIME_SCOPE = (
    "frontier_science",
    ":(exclude)frontier_science/certification.yaml",
    "benchmarks/PopulationGenetics/DemographicSFS",
    "requirements-upstream.txt",
)
SCIENCE_FIELDS = (
    "development_mechanism_score",
    "development_observed_sfs_fit_score",
    "development_prediction_score",
    "robustness_score",
    "development_validation_gap",
    "development_scientific_joint_score",
    "heldout_policy_score",
    "heldout_mechanism_score",
    "heldout_observed_sfs_fit_score",
    "heldout_prediction_score",
    "heldout_scientific_joint_score",
    "heldout_robustness_score",
    "development_supported_claim_coverage",
    "heldout_supported_claim_coverage",
    "development_unsupported_refusal_rate",
    "heldout_unsupported_refusal_rate",
    "development_false_discovery_rate",
    "heldout_false_discovery_rate",
    "development_confidence_score",
    "heldout_confidence_score",
    "development_mean_budget_used",
    "heldout_mean_budget_used",
    "development_mean_experiment_calls",
    "heldout_mean_experiment_calls",
    "heldout_feasibility_rate",
    "candidate_world_call_count",
    "candidate_world_valid_rate",
)
PER_WORLD_FIELDS = (
    "split",
    "world_index",
    "valid",
    "kind",
    "claimed_public_model",
    "abstain",
    "confidence",
    "budget_used",
    "experiment_calls",
    "mechanism_quality",
    "parameter_quality",
    "observed_sfs_fit_quality",
    "heldout_sample_size_quality",
    "scientific_quality",
    "correct_refusal",
    "false_discovery",
    "supported_claim",
    "confidence_score",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value == value
        and abs(float(value)) != float("inf")
    )


def _science_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in SCIENCE_FIELDS}


def _source_changes(left: str, right: str) -> list[str]:
    output = subprocess.check_output(
        ["git", "diff", "--name-only", left, right, "--", *TASK_RUNTIME_SCOPE],
        cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL,
    )
    return [line for line in output.splitlines() if line.strip()]


def _failure_kind(event: dict[str, Any]) -> str | None:
    metrics = event.get("metrics") or {}
    explicit = metrics.get("candidate_failure_kind")
    if isinstance(explicit, str) and explicit:
        return explicit
    message = metrics.get("error_message") or event.get("error")
    prefix = "candidate invalid: "
    if isinstance(message, str) and message.startswith(prefix):
        return message[len(prefix):]
    return None


def _retained_artifact_scan(path: Path) -> dict[str, Any]:
    """Screen retained source for direct hidden-instance/evaluator lookup.

    This is deliberately a narrow static screen.  It supplements, but cannot
    replace, runtime filesystem/network isolation or rule out model memorization.
    """

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    string_literals = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    forbidden_literals = {
        "ancestral_misidentification",
        "contraction_a",
        "contraction_b",
        "expansion_a",
        "expansion_b",
        "four_epoch",
        "population_mixture",
    }
    literal_hits = sorted(string_literals & forbidden_literals)
    source_term_hits = sorted(term for term in (
        "DEVELOPMENT_SPECS",
        "HELDOUT_SPECS",
        "_ExactReferencePolicy",
        "_reference_policy",
        "verification/evaluator",
        "demographic_sfs_v2_calibration",
    ) if term in source)

    forbidden_import_roots = {
        "http", "os", "pathlib", "requests", "socket", "subprocess", "urllib",
    }
    import_hits = set()
    forbidden_call_hits = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            import_hits.update(
                alias.name.split(".")[0]
                for alias in node.names
                if alias.name.split(".")[0] in forbidden_import_roots
            )
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in forbidden_import_roots:
                import_hits.add(root)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {
                "compile", "eval", "exec", "open",
            }:
                forbidden_call_hits.add(node.func.id)
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in {"read_bytes", "read_text"}
            ):
                forbidden_call_hits.add(node.func.attr)

    passed = not (
        literal_hits or source_term_hits or import_hits or forbidden_call_hits
    )
    return {
        "source_sha256": _sha256(path),
        "source_bytes": len(source.encode("utf-8")),
        "source_lines": len(source.splitlines()),
        "hidden_world_literal_hits": literal_hits,
        "evaluator_or_calibration_source_term_hits": source_term_hits,
        "forbidden_import_hits": sorted(import_hits),
        "forbidden_call_hits": sorted(forbidden_call_hits),
        "runtime_network_and_filesystem_isolation_checked_separately": True,
        "passed": passed,
    }


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    classical = document.get("truth_blind_multisample_fit") or {}
    equal_budget = document.get("equal_budget_repeated_small_sample_fit") or {}
    underinformative = document.get("underinformative_single_spectrum_fit") or {}
    exact = document.get("exact_reference") or {}
    rank_checks = document.get("identifiability_checks") or []
    mismatch_checks = document.get("misspecified_resolvability_checks") or []
    limits = document.get("finite_sfs_near_equivalence_limits") or []
    gate = document.get("difficulty_gate") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("passed") is True
        and document.get("trusted_evidence") is True
        and provenance.get("git_revision") == CALIBRATION_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and exact.get("valid") == 1.0
        and exact.get("combined_score") == 1.0
        and exact.get("heldout_policy_score") == 1.0
        and gate.get("passed") is True
        and classical.get("development_mean_budget_used") == 8.0
        and classical.get("heldout_mean_budget_used") == 8.0
        and equal_budget.get("development_mean_budget_used") == 8.0
        and equal_budget.get("heldout_mean_budget_used") == 8.0
        and classical.get("combined_score", 0.0)
        > equal_budget.get("combined_score", 1.0) + 0.15
        and classical.get("heldout_policy_score", 0.0)
        > equal_budget.get("heldout_policy_score", 1.0) + 0.08
        and underinformative.get("development_mean_budget_used") == 1.0
        and len(rank_checks) == 7
        and all(row.get("passed") is True for row in rank_checks)
        and len(mismatch_checks) == 2
        and all(row.get("passed") is True for row in mismatch_checks)
        and len(limits) == 2
        and all(
            row.get("indistinguishable_under_registered_threshold") is True
            for row in limits
        )
    ):
        raise ValueError("DemographicSFS-v2 task calibration gate failed")

    keep = (
        "combined_score", "heldout_policy_score",
        "development_mechanism_score", "heldout_mechanism_score",
        "development_observed_sfs_fit_score", "heldout_observed_sfs_fit_score",
        "development_prediction_score", "heldout_prediction_score",
        "development_supported_claim_coverage", "heldout_supported_claim_coverage",
        "development_unsupported_refusal_rate", "heldout_unsupported_refusal_rate",
        "development_false_discovery_rate", "heldout_false_discovery_rate",
        "development_mean_budget_used", "heldout_mean_budget_used",
    )

    def compact(metrics: dict[str, Any]) -> dict[str, Any]:
        return {key: metrics.get(key) for key in keep}

    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "truth_blind_multisample_fit": compact(classical),
        "equal_budget_repeated_small_sample_fit": compact(equal_budget),
        "underinformative_single_spectrum_fit": compact(underinformative),
        "maximum_identifiability_condition_number": max(
            float(row["condition_number"]) for row in rank_checks
        ),
        "minimum_resolvable_mismatch_expected_reduced_deviance": min(
            float(row["expected_noisy_reduced_deviance"])
            for row in mismatch_checks
        ),
        "finite_sfs_near_equivalence_limits": limits,
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


def _load_model(label: str, relative: str) -> dict[str, Any]:
    expected = EXPECTED_CONDITIONS[label]
    report_path = ROOT / relative
    document = json.loads(report_path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("passed") is True
        and document.get("trusted_evidence") is True
        and provenance.get("git_revision") == MODEL_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
    ):
        raise ValueError("untrusted demographic model report: %s" % relative)

    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one completed demographic model run")
    run = runs[0]
    config = document.get("config") or {}
    if not (
        run.get("task") == TASK
        and run.get("algorithm") == "greedy_rewrite"
        and run.get("feedback_mode") == expected["mode"]
        and run.get("seed") == expected["seed"]
        and config.get("budget") == expected["budget"]
        and config.get("llm", {}).get("model") == "gpt-5.5"
        and config.get("llm", {}).get("server_side_seed_control") is False
    ):
        raise ValueError("unexpected demographic calibration condition")

    workdir = Path(run["workdir"]).resolve()
    try:
        relative_workdir = workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("demographic workdir is outside repository") from exc
    trajectory_path = workdir / "trajectory.jsonl"
    raw_events = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable demographic snapshot differs from raw trajectory")
    if len(raw_events) != expected["budget"] + 1:
        raise ValueError("demographic trajectory is incomplete")

    trajectory = []
    for compact_event, raw in zip(snapshot["events"], raw_events):
        if not (
            int(compact_event["step"]) == int(raw["step"])
            and compact_event["candidate_sha256"] == raw["candidate_sha256"]
            and compact_event["parent_sha256"] == raw["parent_sha256"]
        ):
            raise ValueError("raw and portable demographic lineage differs")
        metrics = raw.get("metrics") or {}
        science = _science_metrics(metrics)
        if any(
            value is not None and not _finite_number(value)
            for value in science.values()
        ):
            raise ValueError("demographic science metric is non-finite")
        per_world = metrics.get("per_world") or []
        valid = bool(raw.get("valid")) and metrics.get("valid") == 1.0
        if valid:
            if len(per_world) != 11:
                raise ValueError("valid demographic event lacks eleven worlds")
            expected_splits = ["development"] * 6 + ["heldout"] * 5
            if [row.get("split") for row in per_world] != expected_splits:
                raise ValueError("demographic world split order differs")
        elif per_world:
            raise ValueError("invalid demographic event unexpectedly exposes worlds")
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
            "science_metrics": science,
            "valid_world_count": sum(bool(row.get("valid")) for row in per_world),
            "invalid_world_count": sum(not bool(row.get("valid")) for row in per_world),
            "per_world": [
                {key: row.get(key) for key in PER_WORLD_FIELDS}
                for row in per_world
            ],
            "llm": raw.get("llm") or {},
            "algorithm_metadata": raw.get("algorithm_metadata") or {},
        })

    summary = run.get("summary") or {}
    manifest_path = workdir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if expected["mode"] == "selection_blind" else "online_incumbent"
    )
    best_program_path = workdir / "best_program.py"
    terminal_program_path = workdir / "solution.py"
    best_hash = _sha256(best_program_path)
    selected_events = [
        event for event in trajectory
        if event["candidate_sha256"] == best_hash
    ]
    if len(selected_events) != 1:
        raise ValueError("demographic best program does not identify one event")
    selected = selected_events[0]
    proposals = trajectory[1:]
    failure_counts: dict[str, int] = {}
    for event in proposals:
        if event["failure_kind"]:
            failure_counts[event["failure_kind"]] = (
                failure_counts.get(event["failure_kind"], 0) + 1
            )
    scans = {
        "selected_best": _retained_artifact_scan(best_program_path),
        "terminal": _retained_artifact_scan(terminal_program_path),
    }
    record = {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(report_path),
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "llm_condition_sha256": config.get("llm_condition_sha256"),
        "model": config.get("llm", {}).get("model"),
        "server_side_seed_control": False,
        "feedback_mode": expected["mode"],
        "feedback_scope": summary.get("feedback_scope"),
        "selection_policy": summary.get("selection_policy"),
        "seed": int(run["seed"]),
        "proposal_budget": expected["budget"],
        "oracle_calls": int(summary["oracle_calls"]),
        "budget_units": int(summary["budget_units"]),
        "llm_calls": int(summary["llm"]["calls"]),
        "provider_usage_records": int(summary["llm"]["provider_usage_records"]),
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
        "terminal_program_sha256": _sha256(terminal_program_path),
        "selected_step": selected["step"],
        "selected_candidate_sha256": selected["candidate_sha256"],
        "selected_metrics": selected["science_metrics"],
        "selected_per_world": selected["per_world"],
        "terminal_candidate_sha256": trajectory[-1]["candidate_sha256"],
        "trajectory": trajectory,
        "proposal_count": len(proposals),
        "valid_proposal_count": sum(event["valid"] for event in proposals),
        "invalid_proposal_count": sum(not event["valid"] for event in proposals),
        "valid_nonzero_proposal_count": sum(
            event["valid"] and event["score"] > 0.0 for event in proposals
        ),
        "failure_counts": failure_counts,
        "retained_artifact_scans": scans,
        "artifact_scan_scope": (
            "retained selected-best and terminal source; intermediate proposal text is "
            "not retained, while every proposal remains hash- and metric-bound"
        ),
    }
    record["integrity_passed"] = bool(
        _lineage_is_valid(record)
        and record["selection_policy"] == expected_policy
        and record["oracle_calls"] == expected["budget"] + 1
        and record["budget_units"] == expected["budget"] + 1
        and record["llm_calls"] == expected["budget"]
        and record["provider_usage_records"] == expected["budget"]
        and int(run["evaluated"]) == expected["budget"] + 1
        and record["accepted_proposals"] == sum(
            event["accepted"] for event in proposals
        )
        and abs(record["best_score"] - selected["score"]) < 1.0e-12
        and record["terminal_program_sha256"] == record["terminal_candidate_sha256"]
        and all(scan["passed"] for scan in scans.values())
        and all(
            event["valid_world_count"] == 11
            for event in trajectory if event["valid"]
        )
        and manifest.get("task_id") == TASK
        and manifest.get("feedback_mode") == expected["mode"]
        and manifest.get("seed") == expected["seed"]
        and manifest.get("llm_condition_sha256")
        == config.get("llm_condition_sha256")
    )
    if not record["integrity_passed"]:
        raise ValueError("demographic lineage, accounting, or artifact gate failed")
    return record


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    runtime_source_equivalent: bool = True,
    runtime_source_changes: list[str] | None = None,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    classical = calibration["truth_blind_multisample_fit"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    conditions = {record["llm_condition_sha256"] for record in records.values()}
    contracts = {record["task_contract_sha256"] for record in records.values()}
    runtimes = {record["runtime_source_sha256"] for record in records.values()}
    proposals = [
        event for record in records.values() for event in record["trajectory"][1:]
    ]
    normal_proposals = normal["trajectory"][1:]
    normal_selected = normal["selected_metrics"]
    blind_selected = blind["selected_metrics"]
    normal_best_heldout = max(
        normal_proposals,
        key=lambda event: (
            event["science_metrics"]["heldout_mechanism_score"]
            if event["valid"] else -1.0
        ),
    )
    normal_minus_blind = {
        field: normal_selected[field] - blind_selected[field]
        for field in SCIENCE_FIELDS
        if normal_selected[field] is not None and blind_selected[field] is not None
    }
    normal_minus_blind.update({
        "best_score": normal["best_score"] - blind["best_score"],
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "wall_seconds": normal["wall_seconds"] - blind["wall_seconds"],
    })
    normal_vs_classical = {
        "development_mechanism_gap_model_minus_classical": (
            normal_selected["development_mechanism_score"]
            - classical["development_mechanism_score"]
        ),
        "heldout_mechanism_gap_model_minus_classical": (
            normal_selected["heldout_mechanism_score"]
            - classical["heldout_mechanism_score"]
        ),
        "development_prediction_gap_model_minus_classical": (
            normal_selected["development_prediction_score"]
            - classical["development_prediction_score"]
        ),
        "heldout_prediction_gap_model_minus_classical": (
            normal_selected["heldout_prediction_score"]
            - classical["heldout_prediction_score"]
        ),
    }
    prediction_mechanism_gaps = {
        "development": (
            normal_selected["development_prediction_score"]
            - normal_selected["development_mechanism_score"]
        ),
        "heldout": (
            normal_selected["heldout_prediction_score"]
            - normal_selected["heldout_mechanism_score"]
        ),
    }
    failure_counts = {
        kind: sum(event["failure_kind"] == kind for event in proposals)
        for kind in sorted({
            event["failure_kind"] for event in proposals if event["failure_kind"]
        })
    }
    execution_passed = bool(
        calibration["source_revision"] == CALIBRATION_SOURCE_REVISION
        and revisions == {MODEL_SOURCE_REVISION}
        and runtime_source_equivalent
        and len(scopes) == 1
        and len(conditions) == 1
        and None not in conditions
        and len(contracts) == 1
        and None not in contracts
        and len(runtimes) == 1
        and None not in runtimes
        and all(record["integrity_passed"] for record in records.values())
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["seed"] == 0
        and normal["seed"] == blind["seed"] == 1
        and normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and len(proposals) == 7
        and sum(event["valid"] for event in proposals) == 3
        and failure_counts == {"candidate_runtime_error": 4}
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "SYNTHETIC_FINITE_SFS_SINGLE_RUN_GPT55_CALIBRATION_NOT_FEEDBACK_"
            "CAUSAL_POPULATION_REAL_SEQUENCE_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "calibration_source_revision": CALIBRATION_SOURCE_REVISION,
        "model_source_revision": MODEL_SOURCE_REVISION,
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
            "valid_proposal_count": sum(event["valid"] for event in proposals),
            "invalid_proposal_count": sum(not event["valid"] for event in proposals),
            "valid_nonzero_proposal_count": sum(
                event["valid"] and event["score"] > 0.0 for event in proposals
            ),
            "all_eleven_worlds_valid_count": sum(
                event["valid"] and event["valid_world_count"] == 11
                for event in proposals
            ),
            "failure_counts": failure_counts,
        },
        "normal_proposal_science_curve": [
            {
                "step": event["step"],
                "score": event["score"],
                "accepted": event["accepted"],
                **event["science_metrics"],
            }
            for event in normal_proposals
        ],
        "normal_selected_prediction_minus_mechanism": prediction_mechanism_gaps,
        "normal_selected_minus_truth_blind_classical": normal_vs_classical,
        "normal_minus_blind_selected_descriptive_contrast": normal_minus_blind,
        "selection_axis_counterexample": {
            "development_selected_step": normal["selected_step"],
            "development_selected_mechanism_score": normal_selected[
                "development_mechanism_score"
            ],
            "development_selected_heldout_mechanism_score": normal_selected[
                "heldout_mechanism_score"
            ],
            "best_heldout_mechanism_step": normal_best_heldout["step"],
            "best_heldout_mechanism_score": normal_best_heldout[
                "science_metrics"
            ]["heldout_mechanism_score"],
            "best_heldout_step_development_mechanism_score": normal_best_heldout[
                "science_metrics"
            ]["development_mechanism_score"],
        },
        "descriptive_findings": {
            "budget_one_model_proposal_is_invalid": (
                one["valid_proposal_count"] == 0
                and one["failure_counts"] == {"candidate_runtime_error": 1}
            ),
            "normal_budget_three_has_three_valid_nonzero_proposals": (
                normal["valid_nonzero_proposal_count"] == 3
                and normal["invalid_proposal_count"] == 0
            ),
            "normal_accepts_only_first_proposal": (
                normal["accepted_proposals"] == 1
                and normal["selected_step"] == 1
            ),
            "normal_selected_uses_full_budget_in_two_calls": (
                normal_selected["development_mean_budget_used"] == 8.0
                and normal_selected["heldout_mean_budget_used"] == 8.0
                and normal_selected["development_mean_experiment_calls"] == 2.0
                and normal_selected["heldout_mean_experiment_calls"] == 2.0
            ),
            "normal_selected_has_full_coverage_refusal_and_zero_false_discovery": (
                normal_selected["development_supported_claim_coverage"] == 1.0
                and normal_selected["heldout_supported_claim_coverage"] == 1.0
                and normal_selected["development_unsupported_refusal_rate"] == 1.0
                and normal_selected["heldout_unsupported_refusal_rate"] == 1.0
                and normal_selected["development_false_discovery_rate"] == 0.0
                and normal_selected["heldout_false_discovery_rate"] == 0.0
            ),
            "normal_selected_prediction_exceeds_mechanism_in_both_splits": (
                prediction_mechanism_gaps["development"] > 0.20
                and prediction_mechanism_gaps["heldout"] > 0.50
            ),
            "truth_blind_classical_exceeds_normal_selected_mechanism": (
                normal_vs_classical[
                    "development_mechanism_gap_model_minus_classical"
                ] < 0.0
                and normal_vs_classical[
                    "heldout_mechanism_gap_model_minus_classical"
                ] < 0.0
            ),
            "development_selection_discards_better_heldout_mechanism": (
                normal_best_heldout["step"] != normal["selected_step"]
                and normal_best_heldout["science_metrics"][
                    "heldout_mechanism_score"
                ] > normal_selected["heldout_mechanism_score"]
            ),
            "blind_budget_three_has_no_valid_model_proposal": (
                blind["valid_proposal_count"] == 0
                and blind["failure_counts"] == {"candidate_runtime_error": 3}
            ),
            "normal_and_blind_are_oracle_call_matched": (
                normal_minus_blind["oracle_calls"] == 0
            ),
            "normal_and_blind_are_token_matched": (
                normal_minus_blind["total_tokens"] == 0
            ),
            "retained_artifacts_pass_narrow_shortcut_scan": all(
                scan["passed"]
                for record in records.values()
                for scan in record["retained_artifact_scans"].values()
            ),
            "feedback_effect_identified": False,
            "arbitrary_demographic_history_identified": False,
            "real_population_or_autonomous_discovery_demonstrated": False,
        },
        "limitations": [
            "Each condition has one run; no confidence interval, population, leaderboard or scaling-law estimate is supported.",
            "The Azure endpoint exposes no server-side generation seed, so equal local seed labels do not pair model randomness.",
            "Normal and selection-blind match oracle calls but differ in tokens, prompts, parent histories and generated programs; their contrast is descriptive, not causal.",
            "Budget one uses local seed label zero and budget three label one; they are independent calibrations, not prefixes of one trajectory.",
            "Candidate exception text is intentionally sanitized; four failures are classified only as candidate_runtime_error, although retained terminal source permits narrower manual diagnosis for two conditions.",
            "The static audit covers retained selected-best and terminal source; intermediate proposal text is not retained, though its hashes and metrics are bound.",
            "The task fixes ancestral scale and assumes neutral panmixia, independent loci and known mutation opportunity; it omits linkage, recombination, selection, migration, structure, ascertainment and real sequence QC.",
            "Finite-SFS prediction and fit do not establish demographic mechanism; some four-epoch and population-mixture histories remain non-rejectable by construction.",
            "No real population data, independent population-genetics review or biological confirmation is present.",
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
    current_revision = source_provenance(ROOT).get("git_revision")
    changes_to_model = _source_changes(
        CALIBRATION_SOURCE_REVISION, MODEL_SOURCE_REVISION
    )
    changes_after_model = _source_changes(MODEL_SOURCE_REVISION, current_revision)
    changes = sorted(set(changes_to_model + changes_after_model))
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
