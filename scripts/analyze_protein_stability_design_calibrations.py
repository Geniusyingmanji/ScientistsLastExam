#!/usr/bin/env python3
"""Bind and analyze the ProteinStabilityDesign GPT-5.5 calibrations.

The three model conditions are single descriptive runs over a finite public DMS
replay.  This script verifies their provenance, trajectory/accounting lineage,
selected artifacts, held-out/protease axes, and absence of simple fixed-instance
lookup code.  It deliberately does not turn the normal/open-loop contrast into a
causal feedback or autonomous-discovery claim.
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
from frontier_science.runtime_migration import runtime_migration_status  # noqa: E402


TASK = "ProteinEngineering/ProteinStabilityDesign"
INPUT_SOURCE_REVISION = "72301eee6237a8a4382e7489e07ed772660a59bb"
CALIBRATION = "experiments/protein_stability_design_calibration_2026-07-25.json"
DATA = (
    ROOT
    / "benchmarks/ProteinEngineering/ProteinStabilityDesign/verification/"
    "protein_stability_landscapes_v1.json"
)
REPORTS = {
    "budget_one": "experiments/gpt55_protein_stability_v1_b1_2026-07-25.json",
    "normal_budget_three": (
        "experiments/gpt55_protein_stability_v1_b3_2026-07-25.json"
    ),
    "blind_budget_three": (
        "experiments/gpt55_protein_stability_v1_blind_b3_2026-07-25.json"
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
    "frontier_science/evaluate.py",
    "frontier_science/trusted_driver.py",
    "frontier_science/secure_eval.py",
    "frontier_science/candidate_worker.py",
    "frontier_science/rpc_codec.py",
    "frontier_science/spec.py",
    "frontier_science/registry.py",
    "benchmarks/ProteinEngineering/ProteinStabilityDesign",
    "requirements-upstream.txt",
)
SCIENCE_FIELDS = (
    "development_batch_utility",
    "development_mean_stability_ddg",
    "development_top_decile_hit_rate",
    "development_batch_diversity",
    "development_proxy_false_promotion_rate",
    "development_trypsin_score",
    "development_chymotrypsin_score",
    "robustness_score",
    "heldout_policy_score",
    "heldout_batch_utility",
    "heldout_mean_stability_ddg",
    "heldout_top_decile_hit_rate",
    "heldout_batch_diversity",
    "heldout_proxy_false_promotion_rate",
    "heldout_trypsin_score",
    "heldout_chymotrypsin_score",
    "heldout_robustness_score",
    "heldout_feasibility_rate",
    "development_mean_assay_calls",
    "heldout_mean_assay_calls",
    "development_assay_unique_rate",
    "heldout_assay_unique_rate",
    "development_selected_assayed_fraction",
    "heldout_selected_assayed_fraction",
    "development_selected_unmeasured_fraction",
    "heldout_selected_unmeasured_fraction",
    "development_normalized_utility_gain_per_assay",
    "heldout_normalized_utility_gain_per_assay",
    "candidate_world_valid_rate",
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


def _fixed_instance_shortcut_scan(
    path: Path, data_path: Path = DATA,
) -> dict[str, Any]:
    """Reject simple table/identity lookup in a retained model artifact.

    This is a static screen, not a proof against pretraining contamination.  The
    secure evaluator separately prevents filesystem/network access at runtime.
    """

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    data = json.loads(data_path.read_text(encoding="utf-8"))
    worlds = data["worlds"]

    forbidden_literals: set[str] = set()
    identity_tokens: set[str] = set()
    for world in worlds:
        forbidden_literals.update({world["id"], world["wild_type_sequence"]})
        identity_tokens.update(
            token for token in world["id"].split("_")
            if len(token) >= 4 and token not in {"Tsuboyama", "2023"}
        )
        for row in world["candidates"]:
            forbidden_literals.update({row["mutation"], row["sequence"]})

    string_literals = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    exact_hits = sorted(forbidden_literals & string_literals)
    identity_hits = sorted(identity_tokens & string_literals)

    forbidden_source_terms = (
        "protein_stability_landscapes_v1",
        "DMS_ProteinGym_substitutions",
        "DMS_substitutions.csv",
        "substitutions_raw_DMS",
        "verification/evaluator",
        "_reference_policy",
        "_reference_rows",
        "_anchors",
    )
    source_term_hits = sorted(
        term for term in forbidden_source_terms if term in source
    )

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
        exact_hits or identity_hits or source_term_hits
        or import_hits or forbidden_call_hits
    )
    return {
        "source_sha256": _sha256(path),
        "source_bytes": len(source.encode("utf-8")),
        "source_lines": len(source.splitlines()),
        "fixed_instance_literal_hits": exact_hits,
        "fixed_identity_token_hits": identity_hits,
        "evaluator_or_dataset_source_term_hits": source_term_hits,
        "forbidden_import_hits": sorted(import_hits),
        "forbidden_call_hits": sorted(forbidden_call_hits),
        "runtime_network_and_filesystem_isolation_checked_separately": True,
        "passed": passed,
    }


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    baseline = document.get("direct_baseline") or {}
    reference = document.get("direct_reference") or {}
    classical = (document.get("truth_blind_assay_policy") or {}).get("metrics") or {}
    rebuild = document.get("source_rebuild") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("passed") is True
        and document.get("trusted_evidence") is True
        and provenance.get("git_revision") == INPUT_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and document.get("data_provenance_checks_passed") is True
        and rebuild.get("exact_match") is True
        and rebuild.get("world_count") == 8
        and sum(rebuild.get("candidate_counts", {}).values()) == 2756
        and baseline.get("valid") == 1.0
        and baseline.get("combined_score") == 0.0
        and reference.get("valid") == 1.0
        and reference.get("combined_score") == 1.0
        and reference.get("robustness_score") == 1.0
        and reference.get("heldout_policy_score") == 1.0
        and reference.get("heldout_robustness_score") == 1.0
        and 0.25 < float(classical.get("combined_score", 0.0)) < 0.90
        and 0.25 < float(classical.get("heldout_policy_score", 0.0)) < 0.90
        and classical.get("development_mean_assay_calls") == 12.0
        and classical.get("heldout_mean_assay_calls") == 12.0
        and float(document.get("minimum_utility_headroom", 0.0)) > 0.10
        and float(document.get("minimum_protease_quality_headroom", 0.0)) > 0.0
    ):
        raise ValueError("ProteinStabilityDesign task calibration gate failed")
    baseline_metrics = _science_metrics(baseline)
    baseline_metrics.update({
        "combined_score": baseline["combined_score"],
        "valid": baseline["valid"],
    })
    reference_metrics = _science_metrics(reference)
    reference_metrics.update({
        "combined_score": reference["combined_score"],
        "valid": reference["valid"],
    })
    classical_metrics = _science_metrics(classical)
    classical_metrics.update({
        "combined_score": classical["combined_score"],
        "valid": classical["valid"],
    })
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "world_count": rebuild["world_count"],
        "candidate_count": sum(rebuild["candidate_counts"].values()),
        "source_rebuild_sha256": rebuild.get("rebuilt_sha256"),
        "minimum_utility_headroom": document["minimum_utility_headroom"],
        "minimum_protease_quality_headroom": document[
            "minimum_protease_quality_headroom"
        ],
        "baseline": baseline_metrics,
        "reference": reference_metrics,
        "truth_blind_assay_policy": classical_metrics,
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
        and provenance.get("git_revision") == INPUT_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
    ):
        raise ValueError("untrusted protein model report: %s" % relative)

    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one successful protein model run")
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
        raise ValueError("unexpected protein calibration condition")

    workdir = Path(run["workdir"]).resolve()
    try:
        relative_workdir = workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("protein workdir is outside repository") from exc
    trajectory_path = workdir / "trajectory.jsonl"
    raw_events = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable protein snapshot differs from raw trajectory")
    if len(raw_events) != expected["budget"] + 1:
        raise ValueError("protein trajectory is incomplete")

    trajectory = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            int(compact["step"]) == int(raw["step"])
            and compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
        ):
            raise ValueError("raw and portable protein lineage differs")
        metrics = raw.get("metrics") or {}
        science = _science_metrics(metrics)
        if any(
            value is not None and not _finite_number(value)
            for value in science.values()
        ):
            raise ValueError("protein science metric is non-finite")
        per_world = metrics.get("per_world") or []
        if len(per_world) != 8:
            raise ValueError("protein event does not retain all eight worlds")
        expected_splits = ["development"] * 5 + ["heldout"] * 3
        if [row.get("split") for row in per_world] != expected_splits:
            raise ValueError("protein world split order differs")
        trajectory.append({
            "step": int(raw["step"]),
            "oracle_calls": int(raw["oracle_calls"]),
            "budget_units": int(raw["budget_units"]),
            "score": float(raw["score"]),
            "best_score": float(raw["best_score"]),
            "valid": bool(raw.get("valid")) and metrics.get("valid") == 1.0,
            "accepted": bool(raw["accepted"]),
            "candidate_sha256": raw["candidate_sha256"],
            "parent_sha256": raw["parent_sha256"],
            "failure_kind": _failure_kind(raw),
            "science_metrics": science,
            "valid_world_count": sum(bool(row.get("valid")) for row in per_world),
            "invalid_world_count": sum(not bool(row.get("valid")) for row in per_world),
            "per_world": [{
                key: row.get(key) for key in (
                    "world_index", "split", "valid", "failure_kind", "batch_score",
                    "batch_utility", "mean_stability_ddg", "top_decile_hit_rate",
                    "batch_diversity", "proxy_false_promotion_rate",
                    "trypsin_score", "chymotrypsin_score", "protease_joint_score",
                    "assay_calls", "unique_assay_calls", "selected_assayed_fraction",
                    "normalized_utility_gain_per_assay",
                )
            } for row in per_world],
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
        event for event in trajectory if event["candidate_sha256"] == best_hash
    ]
    if len(selected_events) != 1:
        raise ValueError("protein best program does not identify one event")
    selected = selected_events[0]
    proposals = trajectory[1:]
    failure_counts: dict[str, int] = {}
    for event in proposals:
        if event["failure_kind"]:
            failure_counts[event["failure_kind"]] = (
                failure_counts.get(event["failure_kind"], 0) + 1
            )
    scans = {
        "selected_best": _fixed_instance_shortcut_scan(best_program_path),
        "terminal": _fixed_instance_shortcut_scan(terminal_program_path),
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
        "total_tokens": summary["llm"].get("total_tokens"),
        "wall_seconds": float(summary["wall_seconds"]),
        "baseline_score": float(run["baseline"]),
        "best_score": float(run["best"]),
        "accepted_proposals": int(run["accepted"]),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "run_manifest_sha256": _sha256(manifest_path),
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
        "failure_counts": failure_counts,
        "fixed_instance_shortcut_scans": scans,
        "shortcut_scan_scope": (
            "retained selected-best and terminal sources; intermediate source text is not "
            "retained, while every intermediate candidate remains hash-bound in the trajectory"
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
        and all(event["valid_world_count"] == 8 for event in trajectory)
        and manifest.get("task_id") == TASK
        and manifest.get("feedback_mode") == expected["mode"]
        and manifest.get("seed") == expected["seed"]
        and manifest.get("llm_condition_sha256") == config.get(
            "llm_condition_sha256"
        )
    )
    if not record["integrity_passed"]:
        raise ValueError("protein lineage, accounting, or shortcut gate failed")
    return record


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    expected_source_revision: str = INPUT_SOURCE_REVISION,
    runtime_source_equivalent: bool = True,
    runtime_source_changes: list[str] | None = None,
    runtime_migration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    conditions = {record["llm_condition_sha256"] for record in records.values()}
    proposals = [
        event for record in records.values() for event in record["trajectory"][1:]
    ]
    normal_events = normal["trajectory"]
    normal_accepted = [event for event in normal_events[1:] if event["accepted"]]
    normal_selected = normal["selected_metrics"]
    blind_selected = blind["selected_metrics"]
    contrast = {
        field: normal_selected[field] - blind_selected[field]
        for field in SCIENCE_FIELDS
    }
    contrast.update({
        "best_score": normal["best_score"] - blind["best_score"],
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "wall_seconds": normal["wall_seconds"] - blind["wall_seconds"],
    })

    accepted_transitions = []
    previous = normal_events[0]
    for event in normal_events[1:]:
        if event["accepted"]:
            accepted_transitions.append({
                "from_step": previous["step"],
                "to_step": event["step"],
                "score_delta": event["score"] - previous["score"],
                "development_robustness_delta": (
                    event["science_metrics"]["robustness_score"]
                    - previous["science_metrics"]["robustness_score"]
                ),
                "heldout_policy_delta": (
                    event["science_metrics"]["heldout_policy_score"]
                    - previous["science_metrics"]["heldout_policy_score"]
                ),
                "heldout_robustness_delta": (
                    event["science_metrics"]["heldout_robustness_score"]
                    - previous["science_metrics"]["heldout_robustness_score"]
                ),
            })
            previous = event

    blind_best_heldout = max(
        blind["trajectory"][1:],
        key=lambda event: event["science_metrics"]["heldout_policy_score"],
    )
    blind_best_robust = max(
        blind["trajectory"][1:],
        key=lambda event: event["science_metrics"]["heldout_robustness_score"],
    )
    execution_passed = bool(
        calibration["source_revision"] == expected_source_revision
        and revisions == {expected_source_revision}
        and runtime_source_equivalent
        and len(scopes) == 1
        and tuple(calibration.get("source_scope") or []) in scopes
        and len(conditions) == 1
        and None not in conditions
        and all(record["integrity_passed"] for record in records.values())
        and one["proposal_budget"] == 1
        and one["seed"] == 0
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and normal["seed"] == blind["seed"] == 1
        and normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and len(proposals) == 7
        and all(event["valid"] for event in proposals)
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "PUBLIC_PROTEINGYM_DMS_OFFLINE_REPLAY_SINGLE_RUN_CALIBRATION_NOT_"
            "FEEDBACK_CAUSAL_PRETRAINING_CLEAN_PROSPECTIVE_WET_LAB_FUNCTION_OR_"
            "AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_source_revision": expected_source_revision,
        "input_task_runtime_source_equivalent": runtime_source_equivalent,
        "input_task_runtime_source_changes": runtime_source_changes or [],
        "input_task_runtime_source_migration": runtime_migration,
        "input_source_scope_equivalent": len(scopes) == 1,
        "input_llm_condition_equivalent": len(conditions) == 1,
        "task_calibration": calibration,
        "records": records,
        "proposal_hurdle_summary": {
            "proposal_count": len(proposals),
            "valid_proposal_count": sum(event["valid"] for event in proposals),
            "invalid_proposal_count": sum(not event["valid"] for event in proposals),
            "positive_development_count": sum(event["score"] > 0.0 for event in proposals),
            "all_eight_worlds_valid_count": sum(
                event["valid_world_count"] == 8 for event in proposals
            ),
            "failure_counts": {
                kind: sum(event["failure_kind"] == kind for event in proposals)
                for kind in sorted({
                    event["failure_kind"] for event in proposals
                    if event["failure_kind"]
                })
            },
        },
        "normal_accepted_transition_audit": accepted_transitions,
        "normal_minus_blind_selected_descriptive_contrast": contrast,
        "selection_axis_counterexample": {
            "blind_development_selected_step": blind["selected_step"],
            "blind_development_selected_score": blind["best_score"],
            "blind_best_heldout_step": blind_best_heldout["step"],
            "blind_best_heldout_policy_score": blind_best_heldout[
                "science_metrics"
            ]["heldout_policy_score"],
            "blind_best_heldout_robustness_step": blind_best_robust["step"],
            "blind_best_heldout_robustness_score": blind_best_robust[
                "science_metrics"
            ]["heldout_robustness_score"],
        },
        "descriptive_findings": {
            "all_seven_model_proposals_are_protocol_valid": all(
                event["valid"] for event in proposals
            ),
            "all_model_proposals_improve_the_zero_development_baseline": all(
                event["score"] > 0.0 for event in proposals
            ),
            "budget_one_exceeds_truth_blind_development_score": (
                one["best_score"]
                > calibration["truth_blind_assay_policy"]["combined_score"]
            ),
            "budget_one_underperforms_truth_blind_heldout_policy": (
                one["selected_metrics"]["heldout_policy_score"]
                < calibration["truth_blind_assay_policy"]["heldout_policy_score"]
            ),
            "all_selected_models_use_full_unique_assay_budget": all(
                record["selected_metrics"]["development_mean_assay_calls"] == 12.0
                and record["selected_metrics"]["heldout_mean_assay_calls"] == 12.0
                and record["selected_metrics"]["development_assay_unique_rate"] == 1.0
                and record["selected_metrics"]["heldout_assay_unique_rate"] == 1.0
                for record in records.values()
            ),
            "normal_second_accept_improves_nominal_but_regresses_development_protease_robustness": any(
                row["score_delta"] > 0.0
                and row["development_robustness_delta"] < 0.0
                for row in accepted_transitions
            ),
            "blind_development_selection_discards_better_heldout_candidate": (
                blind_best_heldout["step"] != blind["selected_step"]
                and blind_best_heldout["science_metrics"]["heldout_policy_score"]
                > blind["selected_metrics"]["heldout_policy_score"]
            ),
            "normal_outperforms_blind_selected_development": contrast["best_score"] > 0.0,
            "normal_and_blind_are_oracle_call_matched": contrast["oracle_calls"] == 0,
            "normal_and_blind_are_token_matched": contrast["total_tokens"] == 0,
            "retained_artifacts_pass_fixed_instance_shortcut_scan": all(
                scan["passed"]
                for record in records.values()
                for scan in record["fixed_instance_shortcut_scans"].values()
            ),
            "feedback_effect_identified": False,
            "pretraining_contamination_ruled_out": False,
            "prospective_or_wet_lab_protein_discovery_demonstrated": False,
        },
        "limitations": [
            "Each condition has one run; no confidence interval, population, leaderboard or scaling-law estimate is supported.",
            "The Azure endpoint exposes no server-side generation seed, so equal local seed labels do not pair model randomness.",
            "Normal and selection-blind match oracle calls but differ in tokens, prompts, parent histories and wall time; their contrast is descriptive, not causal.",
            "Budget one uses local seed label zero and budget three label one; the runs are independent calibrations, not prefixes of one trajectory.",
            "The static lookup audit covers retained selected-best and terminal source artifacts; intermediate source text is not retained, though its hashes and results are bound.",
            "Static scanning and a networkless sandbox cannot rule out memorization from pretraining or a semantically obfuscated public-data lookup policy.",
            "Held-out domains come from the same finite public cDNA-display dataset and are validation, not fresh prospective confirmation.",
            "Proteolysis-derived stability does not establish expression, function, binding, toxicity, evolvability or in-vivo fitness.",
            "No sequence was synthesized and no independent biophysical or functional experiment was performed.",
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
