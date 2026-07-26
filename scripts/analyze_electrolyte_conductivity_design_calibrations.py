#!/usr/bin/env python3
"""Bind and analyze ElectrolyteConductivityDesign GPT-5.5 calibrations.

The inputs are three single-run model conditions over a finite public EIS replay.
This script verifies their provenance, raw trajectory/accounting lineage, retained
artifacts, assay use, held-out temperature duties, discovery-repeat robustness and
untouched-repeat confirmation.  It deliberately does not turn the normal/open-loop
contrast or discovery-assay optimization into a causal-feedback, prospective, or
autonomous-scientific-discovery claim.
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


TASK = "Electrochemistry/ElectrolyteConductivityDesign"
TASK_SOURCE_REVISION = "903f84b520cf9b9d4668cc73bed6edc3a01cc118"
MODEL_SOURCE_REVISION = "489789a5de4265dba308f95b5a808324d2248048"
CALIBRATION = "experiments/electrolyte_conductivity_design_calibration_2026-07-25.json"
DATA = (
    ROOT
    / "benchmarks/Electrochemistry/ElectrolyteConductivityDesign/verification/"
    "electrolyte_conductivity_v1.json"
)
REPORTS = {
    "budget_one": (
        "experiments/gpt55_electrolyte_conductivity_v1_b1_2026-07-25.json"
    ),
    "normal_budget_three": (
        "experiments/gpt55_electrolyte_conductivity_v1_b3_2026-07-25.json"
    ),
    "blind_budget_three": (
        "experiments/gpt55_electrolyte_conductivity_v1_blind_b3_2026-07-25.json"
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
    "benchmarks/Electrochemistry/ElectrolyteConductivityDesign",
    "requirements-upstream.txt",
)
SCIENCE_FIELDS = (
    "development_batch_utility",
    "development_mean_weighted_conductivity_s_cm",
    "development_minimum_weighted_conductivity_s_cm",
    "development_top_quartile_hit_rate",
    "development_confirmation_mean_weighted_conductivity_s_cm",
    "development_confirmation_minimum_weighted_conductivity_s_cm",
    "development_confirmation_top_quartile_hit_rate",
    "development_proxy_false_promotion_rate",
    "development_batch_diversity",
    "development_mean_eis_fit_quality",
    "development_mean_arrhenius_r2",
    "development_mean_campaign_count",
    "robustness_score",
    "confirmation_score",
    "confirmation_robustness_score",
    "heldout_policy_score",
    "heldout_robustness_score",
    "heldout_confirmation_score",
    "heldout_confirmation_robustness_score",
    "heldout_mean_weighted_conductivity_s_cm",
    "heldout_minimum_weighted_conductivity_s_cm",
    "heldout_top_quartile_hit_rate",
    "heldout_confirmation_mean_weighted_conductivity_s_cm",
    "heldout_confirmation_minimum_weighted_conductivity_s_cm",
    "heldout_confirmation_top_quartile_hit_rate",
    "heldout_proxy_false_promotion_rate",
    "heldout_batch_diversity",
    "heldout_mean_eis_fit_quality",
    "heldout_mean_arrhenius_r2",
    "heldout_mean_campaign_count",
    "heldout_feasibility_rate",
    "development_mean_assay_calls",
    "heldout_mean_assay_calls",
    "development_assay_unique_rate",
    "heldout_assay_unique_rate",
    "development_selected_assayed_fraction",
    "heldout_selected_assayed_fraction",
    "development_normalized_gain_per_assay",
    "heldout_normalized_gain_per_assay",
    "candidate_world_valid_rate",
)
PER_WORLD_FIELDS = (
    "world_index", "split", "valid", "failure_kind", "batch_score",
    "batch_utility", "repeat_robustness_score", "repeat_lower_utility",
    "confirmation_score", "confirmation_robustness_score",
    "confirmation_utility", "confirmation_lower_utility",
    "mean_weighted_conductivity_s_cm",
    "minimum_weighted_conductivity_s_cm",
    "confirmation_mean_weighted_conductivity_s_cm",
    "confirmation_minimum_weighted_conductivity_s_cm",
    "top_quartile_hit_rate", "confirmation_top_quartile_hit_rate",
    "proxy_false_promotion_rate", "batch_diversity",
    "mean_confirmation_eis_fit_quality", "mean_confirmation_arrhenius_r2",
    "campaign_count", "assay_calls", "unique_assay_calls",
    "assay_unique_rate", "selected_assayed_fraction",
    "normalized_gain_per_assay", "selected_ids",
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
    """Screen retained source for direct formulation lookup and forbidden I/O."""

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    data = json.loads(data_path.read_text(encoding="utf-8"))
    forbidden_literals = {str(row["id"]) for row in data["candidates"]}
    string_literals = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    exact_hits = sorted(forbidden_literals & string_literals)
    source_terms = (
        "electrolyte_conductivity_v1", "Conductivtiy_experiment.csv",
        "verification/evaluator", "_reference_policy", "_anchors",
        "discovery_replicates", "confirmation_replicates",
    )
    source_term_hits = sorted(term for term in source_terms if term in source)
    forbidden_import_roots = {
        "http", "os", "pathlib", "requests", "socket", "subprocess", "urllib",
    }
    import_hits: set[str] = set()
    forbidden_call_hits: set[str] = set()
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
        exact_hits or source_term_hits or import_hits or forbidden_call_hits
    )
    return {
        "source_sha256": _sha256(path),
        "source_bytes": len(source.encode("utf-8")),
        "source_lines": len(source.splitlines()),
        "fixed_formulation_id_literal_hits": exact_hits,
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
    rebuild = document.get("source_rebuild") or {}
    arrhenius = document.get("independent_arrhenius_recalculation") or {}
    baseline = document.get("direct_baseline") or {}
    reference = document.get("direct_reference") or {}
    robust_reference = document.get("direct_robust_reference") or {}
    classical = (document.get("truth_blind_assay_policy") or {}).get("metrics") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("passed") is True
        and document.get("trusted_evidence") is True
        and provenance.get("git_revision") == TASK_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and rebuild.get("exact_match") is True
        and rebuild.get("source_formulation_count") == 85
        and rebuild.get("candidate_formulation_count") == 23
        and rebuild.get("rebuilt_sha256") == rebuild.get("expected_sha256")
        and arrhenius.get("experiment_count") == 141
        and arrhenius.get("unique_experiment_count") == 141
        and float(arrhenius.get("maximum_absolute_r2_error", 1.0)) < 1.0e-12
        and float(arrhenius.get("maximum_absolute_mse_error", 1.0)) < 1.0e-12
        and float(arrhenius.get("maximum_absolute_activation_energy_error", 1.0)) < 1.0e-10
        and baseline.get("valid") == 1.0
        and baseline.get("combined_score") == 0.0
        and reference.get("valid") == 1.0
        and reference.get("combined_score") == 1.0
        and reference.get("heldout_policy_score") == 1.0
        and robust_reference.get("robustness_score") == 1.0
        and robust_reference.get("heldout_robustness_score") == 1.0
        and classical.get("valid") == 1.0
        and float(classical.get("combined_score", 0.0)) > 0.25
        and float(classical.get("heldout_policy_score", 0.0)) > 0.25
        and float(classical.get("confirmation_score", 1.0)) < 0.10
        and classical.get("heldout_confirmation_score") == 0.0
        and classical.get("development_mean_assay_calls") == 8.0
        and classical.get("heldout_mean_assay_calls") == 8.0
        and float(document.get("minimum_nominal_or_robust_headroom", 0.0)) > 0.04
    ):
        raise ValueError("ElectrolyteConductivityDesign task calibration gate failed")

    def compact(metrics: dict[str, Any]) -> dict[str, Any]:
        result = _science_metrics(metrics)
        result.update({
            "combined_score": metrics["combined_score"],
            "valid": metrics["valid"],
        })
        return result

    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "frozen_data_sha256": rebuild["rebuilt_sha256"],
        "source_formulation_count": rebuild["source_formulation_count"],
        "candidate_formulation_count": rebuild["candidate_formulation_count"],
        "candidate_experiment_count": arrhenius["experiment_count"],
        "minimum_nominal_or_robust_headroom": document[
            "minimum_nominal_or_robust_headroom"
        ],
        "baseline": compact(baseline),
        "reference": compact(reference),
        "robust_reference": compact(robust_reference),
        "truth_blind_assay_policy": compact(classical),
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
        raise ValueError("untrusted electrolyte model report: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one successful electrolyte model run")
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
        raise ValueError("unexpected electrolyte calibration condition")

    workdir = Path(run["workdir"]).resolve()
    try:
        relative_workdir = workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("electrolyte workdir is outside repository") from exc
    trajectory_path = workdir / "trajectory.jsonl"
    raw_events = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable electrolyte snapshot differs from raw trajectory")
    if len(raw_events) != expected["budget"] + 1:
        raise ValueError("electrolyte trajectory is incomplete")

    trajectory = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            int(compact["step"]) == int(raw["step"])
            and compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
        ):
            raise ValueError("raw and portable electrolyte lineage differs")
        metrics = raw.get("metrics") or {}
        science = _science_metrics(metrics)
        if any(
            value is not None and not _finite_number(value)
            for value in science.values()
        ):
            raise ValueError("electrolyte science metric is non-finite")
        per_world = metrics.get("per_world") or []
        if len(per_world) != 8:
            raise ValueError("electrolyte event does not retain all eight worlds")
        if [row.get("split") for row in per_world] != [
            "development", "development", "development", "development",
            "development", "heldout", "heldout", "heldout",
        ]:
            raise ValueError("electrolyte world split order differs")
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
        event for event in trajectory if event["candidate_sha256"] == best_hash
    ]
    if len(selected_events) != 1:
        raise ValueError("electrolyte best program does not identify one event")
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
        "failure_counts": failure_counts,
        "fixed_instance_shortcut_scans": scans,
        "shortcut_scan_scope": (
            "retained selected-best and terminal sources; intermediate source text is "
            "not retained, while every intermediate candidate remains hash-bound"
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
        and isinstance(record["task_contract_sha256"], str)
        and isinstance(record["runtime_source_sha256"], str)
    )
    if not record["integrity_passed"]:
        raise ValueError("electrolyte lineage, accounting, or shortcut gate failed")
    return record


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    task_runtime_source_equivalent: bool = True,
    task_runtime_source_changes: list[str] | None = None,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    conditions = {record["llm_condition_sha256"] for record in records.values()}
    task_contracts = {record["task_contract_sha256"] for record in records.values()}
    runtime_sources = {record["runtime_source_sha256"] for record in records.values()}
    proposals = [
        event for record in records.values() for event in record["trajectory"][1:]
    ]
    selected = {
        label: record["selected_metrics"] for label, record in records.items()
    }
    contrast = {
        field: normal["selected_metrics"][field] - blind["selected_metrics"][field]
        for field in SCIENCE_FIELDS
    }
    contrast.update({
        "best_score": normal["best_score"] - blind["best_score"],
        "best_so_far_auc": normal["best_so_far_auc"] - blind["best_so_far_auc"],
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "wall_seconds": normal["wall_seconds"] - blind["wall_seconds"],
    })

    accepted_transitions = []
    previous = normal["trajectory"][0]
    for event in normal["trajectory"][1:]:
        if event["accepted"]:
            accepted_transitions.append({
                "from_step": previous["step"],
                "to_step": event["step"],
                "score_delta": event["score"] - previous["score"],
                "heldout_policy_delta": (
                    event["science_metrics"]["heldout_policy_score"]
                    - previous["science_metrics"]["heldout_policy_score"]
                ),
                "development_robustness_delta": (
                    event["science_metrics"]["robustness_score"]
                    - previous["science_metrics"]["robustness_score"]
                ),
                "heldout_robustness_delta": (
                    event["science_metrics"]["heldout_robustness_score"]
                    - previous["science_metrics"]["heldout_robustness_score"]
                ),
                "confirmation_delta": (
                    event["science_metrics"]["confirmation_score"]
                    - previous["science_metrics"]["confirmation_score"]
                ),
                "heldout_confirmation_delta": (
                    event["science_metrics"]["heldout_confirmation_score"]
                    - previous["science_metrics"]["heldout_confirmation_score"]
                ),
            })
            previous = event

    blind_best_confirmation = max(
        blind["trajectory"][1:],
        key=lambda event: event["science_metrics"]["confirmation_score"],
    )
    normal_rejected = [
        event for event in normal["trajectory"][1:] if not event["accepted"]
    ]
    normal_best_confirmation_robustness = max(
        normal_rejected or normal["trajectory"][1:],
        key=lambda event: event["science_metrics"]["confirmation_robustness_score"],
    )
    visible_confirmation_gaps = {
        label: {
            "development_visible_score": record["best_score"],
            "development_confirmation_score": selected[label]["confirmation_score"],
            "development_visible_minus_confirmation": (
                record["best_score"] - selected[label]["confirmation_score"]
            ),
            "heldout_visible_score": selected[label]["heldout_policy_score"],
            "heldout_confirmation_score": selected[label][
                "heldout_confirmation_score"
            ],
            "heldout_visible_minus_confirmation": (
                selected[label]["heldout_policy_score"]
                - selected[label]["heldout_confirmation_score"]
            ),
        }
        for label, record in records.items()
    }
    execution_passed = bool(
        calibration["source_revision"] == TASK_SOURCE_REVISION
        and revisions == {MODEL_SOURCE_REVISION}
        and task_runtime_source_equivalent
        and len(scopes) == 1
        and tuple(calibration.get("source_scope") or []) in scopes
        and len(conditions) == 1
        and None not in conditions
        and len(task_contracts) == 1
        and None not in task_contracts
        and len(runtime_sources) == 1
        and None not in runtime_sources
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
            "PUBLIC_EIS_OFFLINE_OPTIMIZATION_REPLAY_SINGLE_RUN_CALIBRATION_"
            "NOT_FEEDBACK_CAUSAL_PRETRAINING_CLEAN_PROSPECTIVE_INDEPENDENT_"
            "LAB_COMPLETE_CELL_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_task_source_revision": TASK_SOURCE_REVISION,
        "input_model_source_revision": MODEL_SOURCE_REVISION,
        "input_task_runtime_source_equivalent": task_runtime_source_equivalent,
        "input_task_runtime_source_changes": task_runtime_source_changes or [],
        "input_source_scope_equivalent": len(scopes) == 1,
        "input_llm_condition_equivalent": len(conditions) == 1,
        "input_task_contract_equivalent": len(task_contracts) == 1,
        "input_runtime_source_hash_equivalent": len(runtime_sources) == 1,
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
        "selected_visible_confirmation_gaps": visible_confirmation_gaps,
        "normal_minus_blind_selected_descriptive_contrast": contrast,
        "selection_axis_counterexamples": {
            "blind_development_selected_step": blind["selected_step"],
            "blind_development_selected_score": blind["best_score"],
            "blind_development_selected_confirmation_score": blind[
                "selected_metrics"
            ]["confirmation_score"],
            "blind_best_confirmation_step": blind_best_confirmation["step"],
            "blind_best_confirmation_score": blind_best_confirmation[
                "science_metrics"
            ]["confirmation_score"],
            "blind_best_confirmation_visible_score": blind_best_confirmation["score"],
            "normal_development_selected_step": normal["selected_step"],
            "normal_development_selected_confirmation_robustness": normal[
                "selected_metrics"
            ]["confirmation_robustness_score"],
            "normal_rejected_best_confirmation_robustness_step": (
                normal_best_confirmation_robustness["step"]
            ),
            "normal_rejected_best_confirmation_robustness_score": (
                normal_best_confirmation_robustness["science_metrics"][
                    "confirmation_robustness_score"
                ]
            ),
        },
        "descriptive_findings": {
            "all_seven_model_proposals_are_protocol_valid": all(
                event["valid"] for event in proposals
            ),
            "all_model_proposals_improve_the_zero_development_baseline": all(
                event["score"] > 0.0 for event in proposals
            ),
            "all_selected_models_use_full_unique_assay_budget": all(
                metrics["development_mean_assay_calls"] == 8.0
                and metrics["heldout_mean_assay_calls"] == 8.0
                and metrics["development_assay_unique_rate"] == 1.0
                and metrics["heldout_assay_unique_rate"] == 1.0
                for metrics in selected.values()
            ),
            "all_selected_models_have_zero_nominal_untouched_confirmation": all(
                metrics["confirmation_score"] == 0.0
                and metrics["heldout_confirmation_score"] == 0.0
                for metrics in selected.values()
            ),
            "normal_second_accept_improves_visible_transfer_and_discovery_repeat_robustness_without_confirmation": (
                len(accepted_transitions) >= 2
                and accepted_transitions[1]["score_delta"] > 0.0
                and accepted_transitions[1]["heldout_policy_delta"] > 0.0
                and accepted_transitions[1]["development_robustness_delta"] > 0.0
                and accepted_transitions[1]["heldout_robustness_delta"] > 0.0
                and normal["selected_metrics"]["confirmation_score"] == 0.0
                and normal["selected_metrics"]["heldout_confirmation_score"] == 0.0
            ),
            "blind_visible_selection_discards_higher_confirmation_candidate": (
                blind_best_confirmation["step"] != blind["selected_step"]
                and blind_best_confirmation["science_metrics"]["confirmation_score"]
                > blind["selected_metrics"]["confirmation_score"]
            ),
            "normal_visible_selection_discards_higher_confirmation_robustness_candidate": (
                normal_best_confirmation_robustness["step"] != normal["selected_step"]
                and normal_best_confirmation_robustness["science_metrics"][
                    "confirmation_robustness_score"
                ] > normal["selected_metrics"]["confirmation_robustness_score"]
            ),
            "normal_outperforms_blind_selected_development": contrast["best_score"] > 0.0,
            "normal_and_blind_are_oracle_call_matched": contrast["oracle_calls"] == 0,
            "normal_and_blind_are_token_matched": contrast["total_tokens"] == 0,
            "retained_artifacts_pass_fixed_instance_shortcut_scan": all(
                scan["passed"]
                for record in records.values()
                for scan in record["fixed_instance_shortcut_scans"].values()
            ),
            "independent_confirmation_supports_selected_visible_optimization": False,
            "feedback_effect_identified": False,
            "pretraining_contamination_ruled_out": False,
            "prospective_or_complete_cell_discovery_demonstrated": False,
        },
        "limitations": [
            "Each model condition has one run; no confidence interval, population, leaderboard or scaling-law estimate is supported.",
            "The Azure endpoint exposes no server-side generation seed, so equal local seed labels do not pair model randomness.",
            "Normal and selection-blind match oracle calls but differ in tokens, prompts, parent histories and wall time; their contrast is descriptive, not causal.",
            "Budget one uses local seed label zero and budget three label one; they are independent calibrations, not trajectory prefixes.",
            "The static lookup audit covers retained selected-best and terminal source artifacts; intermediate source text is not retained, though hashes and results are bound.",
            "Static scanning and a networkless sandbox cannot rule out pretraining memorization or semantically hidden public-data lookup.",
            "Held-out worlds change temperature-duty weights over the same finite formulation campaigns; only untouched repeats provide independent repeat confirmation.",
            "The discovery assay returns the same two repeats used by the visible optimization score, so its best-so-far curve is optimization evidence, not confirmation evidence.",
            "No new electrolyte was mixed or measured, and conductivity does not establish electrochemical stability, safety, compatibility, cycle life or manufacturability.",
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
    changes = _source_changes(TASK_SOURCE_REVISION, current_revision)
    return _analyze_records(
        calibration,
        records,
        task_runtime_source_equivalent=not changes,
        task_runtime_source_changes=changes,
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
