#!/usr/bin/env python3
"""Bind and analyze AlloyHardnessOptimization GPT-5.5 calibrations.

The inputs are three single-run calibrations over a public, retrospective
literature replay.  This script verifies provenance, raw trajectory and parent
lineage, retained source artifacts, deterministic re-evaluation, DOI/recipe
shortcut scans, assay use, predictions, uncertainty intervals, study transfer,
and sparse cross-DOI exact-recipe confirmation.  It does not interpret the
normal/open-loop contrast as a feedback effect or the replay as prospective
alloy discovery.
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

from frontier_science.evaluate import evaluate_candidate  # noqa: E402
from frontier_science.protocol import (  # noqa: E402
    compact_trajectory_snapshot,
    load_trajectory,
)
from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)
from frontier_science.registry import find_task  # noqa: E402
from frontier_science.runtime_migration import (  # noqa: E402
    RUNTIME_PATHS,
    runtime_migration_status,
)


TASK = "MaterialsScience/AlloyHardnessOptimization"
INPUT_SOURCE_REVISION = "52dcec0c1a4df2d7f92cdef1d6d2bafa2e81f18e"
CALIBRATION = "experiments/alloy_hardness_v1_calibration_2026-07-26.json"
SOURCE_MIGRATION = (
    "experiments/alloy_hash_order_migration_audit_2026-07-26.json"
)
SOURCE_MIGRATION_SHA256 = (
    "bea6d21e542c27903a31ee9bdb0d9fced6a4a7014b41c6df4ec8f224512672bb"
)
SOURCE_MIGRATION_REVISION = "89e3345db57e15b5bbfe10e36f5c06bd260b9293"
SOURCE_MIGRATION_CHANGES = (
    "benchmarks/MaterialsScience/AlloyHardnessOptimization/solution.py",
    "benchmarks/MaterialsScience/AlloyHardnessOptimization/verification/evaluator.py",
)
SOURCE_MIGRATION_HASHES = {
    "benchmarks/MaterialsScience/AlloyHardnessOptimization/solution.py": (
        "9079971176c51f75a0363e59286f29d0f42bf3b78310c8bc65a515b376165bc5"
    ),
    "benchmarks/MaterialsScience/AlloyHardnessOptimization/verification/evaluator.py": (
        "6a2ac322d7cb67818ad4fabca24bfc9a21dc0ddb05c3037c91e9f9fab70537ae"
    ),
}
DATA = (
    ROOT
    / "benchmarks/MaterialsScience/AlloyHardnessOptimization/verification/"
    "alloy_hardness_v1.json"
)
REPORTS = {
    "budget_one": "experiments/gpt55_alloy_hardness_v1_b1_2026-07-26.json",
    "normal_budget_three": (
        "experiments/gpt55_alloy_hardness_v1_b3_2026-07-26.json"
    ),
    "blind_budget_three": (
        "experiments/gpt55_alloy_hardness_v1_blind_b3_2026-07-26.json"
    ),
}
EXPECTED_CONDITIONS = {
    "budget_one": {"mode": "normal", "budget": 1, "seed": 0},
    "normal_budget_three": {"mode": "normal", "budget": 3, "seed": 1},
    "blind_budget_three": {
        "mode": "selection_blind",
        "budget": 3,
        "seed": 1,
    },
}
BASELINE_SHA256 = (
    "fab66bd9e0f98ca7457cac075b102544355f7d4d4d4008185e942a4d3139117e"
)
DATA_SHA256 = (
    "a55effd2a4077b63a19a45a91729698e07b1bd9e89a72da79b87f2528a09d003"
)
TASK_RUNTIME_SCOPE = (
    "frontier_science/evaluate.py",
    "frontier_science/trusted_driver.py",
    "frontier_science/secure_eval.py",
    "frontier_science/candidate_worker.py",
    "frontier_science/rpc_codec.py",
    "frontier_science/spec.py",
    "frontier_science/registry.py",
    "benchmarks/MaterialsScience/AlloyHardnessOptimization",
    "requirements-upstream.txt",
)
SCIENCE_FIELDS = (
    "development_batch_utility",
    "development_mean_hardness_hv",
    "development_top_candidate_hit_rate",
    "development_batch_diversity",
    "development_proxy_false_promotion_rate",
    "development_prediction_score",
    "development_prediction_mae_hv",
    "development_prediction_interval_coverage",
    "development_mean_prediction_interval_width_hv",
    "development_unmeasured_prediction_mae_hv",
    "development_unmeasured_interval_coverage",
    "development_mean_assay_calls",
    "development_assay_unique_rate",
    "development_selected_assayed_fraction",
    "development_selected_unmeasured_fraction",
    "development_selected_with_confirmation_count",
    "development_selected_confirmation_coverage",
    "development_independent_confirmation_measurement_count",
    "development_independent_confirmation_mae_hv",
    "development_independent_confirmation_mean_bias_hv",
    "heldout_policy_score",
    "heldout_batch_utility",
    "heldout_mean_hardness_hv",
    "heldout_top_candidate_hit_rate",
    "heldout_batch_diversity",
    "heldout_proxy_false_promotion_rate",
    "heldout_prediction_score",
    "heldout_prediction_mae_hv",
    "heldout_prediction_interval_coverage",
    "heldout_mean_prediction_interval_width_hv",
    "heldout_unmeasured_prediction_mae_hv",
    "heldout_unmeasured_interval_coverage",
    "heldout_mean_assay_calls",
    "heldout_assay_unique_rate",
    "heldout_selected_assayed_fraction",
    "heldout_selected_unmeasured_fraction",
    "heldout_selected_with_confirmation_count",
    "heldout_selected_confirmation_coverage",
    "heldout_independent_confirmation_measurement_count",
    "heldout_independent_confirmation_mae_hv",
    "heldout_independent_confirmation_mean_bias_hv",
    "heldout_feasibility_rate",
    "candidate_world_call_count",
    "candidate_world_valid_rate",
)
PER_WORLD_FIELDS = (
    "world_index",
    "split",
    "valid",
    "failure_kind",
    "batch_utility",
    "mean_hardness_hv",
    "top_candidate_hit_rate",
    "batch_diversity",
    "proxy_false_promotion_rate",
    "prediction_mae_hv",
    "prediction_interval_coverage",
    "mean_prediction_interval_width_hv",
    "prediction_distribution_score",
    "unmeasured_prediction_count",
    "unmeasured_prediction_mae_hv",
    "unmeasured_interval_coverage",
    "assay_calls",
    "unique_assay_calls",
    "assay_unique_rate",
    "selected_assayed_fraction",
    "selected_unmeasured_fraction",
    "selected_with_confirmation_count",
    "selected_confirmation_coverage",
    "independent_confirmation_measurement_count",
    "independent_confirmation_mean_hv",
    "independent_confirmation_mae_hv",
    "independent_confirmation_mean_bias_hv",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _science_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in SCIENCE_FIELDS}


def _source_changes(left: str, right: str) -> list[str]:
    output = subprocess.check_output(
        ["git", "diff", "--name-only", left, right, "--", *TASK_RUNTIME_SCOPE],
        cwd=str(ROOT),
        text=True,
        stderr=subprocess.DEVNULL,
    )
    return [line for line in output.splitlines() if line.strip()]


def _is_ancestor(left: str, right: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", left, right],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def _source_migration_status(
    current_revision: str, changes: list[str],
) -> dict[str, Any]:
    """Accept only the hash-bound Alloy sorting migration audit.

    The audit was generated on a clean revision after enumerating the complete
    finite landscape and replaying all retained source artifacts.  Descendant
    analysis revisions are accepted only while the two runtime files remain
    byte-identical and no additional task-runtime path has changed.
    """

    path = ROOT / SOURCE_MIGRATION
    alloy_changes = [value for value in changes if value not in RUNTIME_PATHS]
    runtime_changes = [value for value in changes if value in RUNTIME_PATHS]
    runtime_migration = runtime_migration_status(
        INPUT_SOURCE_REVISION, current_revision, changes,
        additional_allowed_changes=SOURCE_MIGRATION_CHANGES,
        additional_checks={"alloy_hash_order_migration": True},
    ) if runtime_changes else None
    status: dict[str, Any] = {
        "required": bool(changes),
        "report": SOURCE_MIGRATION,
        "expected_report_sha256": SOURCE_MIGRATION_SHA256,
        "report_sha256": _sha256(path) if path.is_file() else None,
        "audited_revision": SOURCE_MIGRATION_REVISION,
        "current_revision": current_revision,
        "task_runtime_source_changes": list(changes),
        "expected_task_runtime_source_changes": list(SOURCE_MIGRATION_CHANGES),
        "alloy_task_runtime_source_changes": alloy_changes,
        "shared_runtime_source_changes": runtime_changes,
        "shared_runtime_migration": runtime_migration,
        "current_source_sha256": {
            relative: _sha256(ROOT / relative)
            for relative in SOURCE_MIGRATION_HASHES
            if (ROOT / relative).is_file()
        },
        "accepted": False,
    }
    if not path.is_file():
        status["failure_reason"] = "migration_report_missing"
        return status
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        status["failure_reason"] = "migration_report_invalid_json"
        return status
    provenance = report.get("source_provenance") or {}
    source = report.get("source_contract") or {}
    landscape = report.get("finite_landscape_audit") or {}
    calibration = report.get("clean_calibration_audit") or {}
    retained = report.get("retained_artifact_audit") or {}
    conclusion = report.get("conclusion") or {}
    source_records = source.get("source_hash_records") or []
    source_record_hashes = {
        row.get("path"): row.get("new_sha256")
        for row in source_records if isinstance(row, dict)
    }
    artifact_records = retained.get("artifact_instances") or []
    baseline = retained.get("baseline_replay") or {}
    checks = {
        "report_hash_matches": status["report_sha256"]
        == SOURCE_MIGRATION_SHA256,
        "report_passed_clean": bool(
            report.get("schema_version") == 1
            and report.get("task") == TASK
            and report.get("execution_passed") is True
            and report.get("passed") is True
            and report.get("trusted_evidence") is True
            and report.get("trust_decision") == "trusted_clean_revision"
            and provenance.get("git_revision") == SOURCE_MIGRATION_REVISION
            and provenance.get("source_tree_dirty") is False
            and provenance.get("source_changes") == []
        ),
        "audited_revision_is_ancestor": _is_ancestor(
            SOURCE_MIGRATION_REVISION, current_revision,
        ),
        "runtime_change_scope_matches": bool(
            alloy_changes == list(SOURCE_MIGRATION_CHANGES)
            and (
                not runtime_changes
                or (runtime_migration or {}).get("accepted") is True
            )
            and source.get("input_source_revision") == INPUT_SOURCE_REVISION
            and source.get("audited_target_revision")
            == SOURCE_MIGRATION_REVISION
            and source.get("task_runtime_source_changes")
            == list(SOURCE_MIGRATION_CHANGES)
            and source.get("allowed_task_runtime_source_changes")
            == list(SOURCE_MIGRATION_CHANGES)
            and source.get("passed") is True
        ),
        "current_runtime_hashes_match": bool(
            status["current_source_sha256"] == SOURCE_MIGRATION_HASHES
            and all(
                source_record_hashes.get(relative) == expected
                for relative, expected in SOURCE_MIGRATION_HASHES.items()
            )
        ),
        "finite_landscape_passed": bool(
            landscape.get("passed") is True
            and landscape.get("world_count") == 13
            and landscape.get("pair_count_per_seed") == 137
            and landscape.get("three_alloy_utility_count_per_seed") == 318
            and landscape.get("old_cross_seed_bit_exact") is False
            and landscape.get("new_cross_seed_bit_exact") is True
            and landscape.get("old_unique_landscape_sha256_count") == 5
            and landscape.get("new_unique_landscape_sha256_count") == 1
            and all(
                row.get("proxy_and_truth_optimal_rows_exactly_match") is True
                and row.get("baseline_metrics_exactly_match") is True
                and row.get("reference_metrics_exactly_match") is True
                for row in (landscape.get("records") or [])
            )
            and len(landscape.get("records") or []) == 5
        ),
        "clean_calibration_passed": bool(
            calibration.get("passed") is True
            and calibration.get("current_calibration_source_revision")
            == SOURCE_MIGRATION_REVISION
            and calibration.get("current_calibration_source_clean") is True
            and calibration.get("current_calibration_execution_passed") is True
            and calibration.get("current_calibration_trusted_evidence") is True
            and calibration.get("truth_blind_aggregate_metrics_exactly_match")
            is True
            and calibration.get("truth_blind_per_world_difference_count") == 1
            and float(calibration.get(
                "maximum_truth_blind_absolute_difference", math.inf,
            )) <= 2.0e-16
            and calibration.get("data_sha256") == DATA_SHA256
        ),
        "retained_replay_passed": bool(
            retained.get("passed") is True
            and retained.get("artifact_instance_count") == 6
            and retained.get("unique_retained_source_count") == 4
            and retained.get("proposal_record_count") == 7
            and retained.get("unique_proposal_count") == 7
            and retained.get("retained_unique_proposal_count") == 4
            and retained.get("unretained_unique_proposal_count") == 3
            and len(artifact_records) == 6
            and all(
                row.get("metrics_exactly_match_bound_trajectory") is True
                for row in artifact_records
            )
            and baseline.get("old_source_exactly_matches_frozen_metrics") is True
            and baseline.get("new_source_exactly_matches_frozen_metrics") is True
            and baseline.get("old_and_new_source_metrics_exactly_match") is True
        ),
        "conclusion_is_scoped": bool(
            conclusion.get("migration_accepted") is True
            and conclusion.get("scientific_selection_space_changed") is False
            and conclusion.get("baseline_or_reference_metrics_changed") is False
            and conclusion.get("retained_source_metrics_changed") is False
            and conclusion.get("intermediate_unretained_sources_replayed") is False
        ),
    }
    status["checks"] = checks
    status["accepted"] = all(checks.values())
    if not status["accepted"]:
        status["failure_reason"] = "migration_gate_failed"
    return status


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


def _source_scan(path: Path, data_path: Path = DATA) -> dict[str, Any]:
    """Screen retained source for fixed-recipe lookup and forbidden access."""

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    data = json.loads(data_path.read_text(encoding="utf-8"))
    alloy_ids = {
        str(row["id"])
        for world in data["worlds"]
        for row in world["candidates"]
    }
    dois = {
        str(world["source_doi"]).lower() for world in data["worlds"]
    }
    dois.update(
        str(row["doi"]).lower()
        for key in ("historical_source_recipes", "reserved_confirmation_recipes")
        for row in data[key]
    )
    string_literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    alloy_hits = sorted(alloy_ids & string_literals)
    doi_hits = sorted(dois & {value.lower() for value in string_literals})
    lower = source.lower()
    source_terms = (
        "alloy_hardness_v1",
        "mpea_dataset.csv",
        "verification/evaluator",
        "evaluator.py",
        "_reference_policy",
        "_anchors",
        "study_hardness_hv",
        "source_doi",
        "independent_exact_recipe_confirmations",
    )
    source_term_hits = sorted(term for term in source_terms if term in lower)
    forbidden_import_roots = {
        "http",
        "importlib",
        "inspect",
        "os",
        "pathlib",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    import_hits: set[str] = set()
    call_hits: set[str] = set()
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
                "__import__",
                "compile",
                "eval",
                "exec",
                "open",
            }:
                call_hits.add(node.func.id)
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in {
                    "read_bytes",
                    "read_text",
                    "urlopen",
                }
            ):
                call_hits.add(node.func.attr)
    passed = not (alloy_hits or doi_hits or source_term_hits or import_hits or call_hits)
    return {
        "source_sha256": _sha256(path),
        "source_bytes": len(source.encode("utf-8")),
        "source_lines": len(source.splitlines()),
        "fixed_alloy_id_literal_hits": alloy_hits,
        "doi_literal_hits": doi_hits,
        "evaluator_or_dataset_source_term_hits": source_term_hits,
        "forbidden_import_hits": sorted(import_hits),
        "forbidden_call_hits": sorted(call_hits),
        "runtime_network_and_filesystem_isolation_checked_separately": True,
        "passed": passed,
    }


def _compact_calibration_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    result = _science_metrics(metrics)
    result.update({
        "combined_score": metrics.get("combined_score"),
        "valid": metrics.get("valid"),
        "feasibility_rate": metrics.get("feasibility_rate"),
    })
    return result


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    rebuild = document.get("data_rebuild") or {}
    contract = rebuild.get("contract") or {}
    proxy = contract.get("proxy") or {}
    counts = document.get("counts") or {}
    anchors = document.get("anchors") or {}
    baseline = document.get("baseline_metrics") or {}
    reference = document.get("reference_metrics") or {}
    classical = document.get("truth_blind_assay_metrics") or {}
    isolation = document.get("secure_isolation_and_failure_checks") or {}
    checks = document.get("checks") or {}
    task_hashes = document.get("task_source_sha256") or {}
    expected_hash_paths = {
        "benchmarks/MaterialsScience/AlloyHardnessOptimization/Task.md",
        "benchmarks/MaterialsScience/AlloyHardnessOptimization/TASK_CARD.yaml",
        "benchmarks/MaterialsScience/AlloyHardnessOptimization/solution.py",
        "benchmarks/MaterialsScience/AlloyHardnessOptimization/verification/evaluator.py",
        "benchmarks/MaterialsScience/AlloyHardnessOptimization/verification/alloy_hardness_v1.json",
        "benchmarks/MaterialsScience/AlloyHardnessOptimization/frontier_eval/metadata.yaml",
        "benchmarks/MaterialsScience/AlloyHardnessOptimization/frontier_eval/run_eval.py",
        "scripts/build_alloy_hardness_data.py",
        "scripts/calibrate_alloy_hardness_optimization.py",
    }
    leave_one_doi_out = proxy.get("historical_leave_one_doi_out") or []
    if not (
        document.get("execution_passed") is True
        and document.get("passed") is True
        and document.get("trusted_evidence") is True
        and provenance.get("git_revision") == INPUT_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and document.get("task") == TASK
        and rebuild.get("exact_match") is True
        and rebuild.get("rebuilt_sha256") == DATA_SHA256
        and rebuild.get("expected_sha256") == DATA_SHA256
        and contract.get("total_csv_row_count") == 1545
        and contract.get("eligible_raw_row_count") == 358
        and contract.get("historical_pool_recipe_count") == 205
        and contract.get("historical_proxy_recipe_count") == 197
        and contract.get("historical_study_count") == 44
        and contract.get("reserved_confirmation_recipe_count") == 9
        and contract.get("reserved_confirmation_study_count") == 8
        and contract.get("target_world_count") == 13
        and contract.get("target_recipe_count") == 65
        and contract.get("development_world_count") == 8
        and contract.get("heldout_world_count") == 5
        and contract.get("batch_size") == 3
        and contract.get("assay_budget") == 2
        and proxy.get("alpha") == 100
        and proxy.get("alpha_grid") == [0.1, 1, 10, 100, 1000]
        and len(leave_one_doi_out) == 5
        and min(
            leave_one_doi_out,
            key=lambda row: (row["equal_study_weight_rmse_hv"], row["alpha"]),
        )["alpha"] == proxy.get("alpha")
        and counts == {
            "historical_proxy_recipes": 197,
            "historical_proxy_studies": 44,
            "reserved_confirmation_recipes": 9,
            "reserved_confirmation_studies": 8,
            "target_recipes": 65,
            "target_studies": 13,
        }
        and anchors.get("development", {}).get("reference_utility")
        > anchors.get("development", {}).get("baseline_utility") + 0.05
        and anchors.get("heldout", {}).get("reference_utility")
        > anchors.get("heldout", {}).get("baseline_utility") + 0.05
        and baseline.get("valid") == 1.0
        and baseline.get("combined_score") == 0.0
        and baseline.get("heldout_policy_score") == 0.0
        and reference.get("valid") == 1.0
        and reference.get("combined_score") == 1.0
        and reference.get("heldout_policy_score") == 1.0
        and classical.get("valid") == 1.0
        and float(classical.get("combined_score", 0.0)) > 0.65
        and float(classical.get("heldout_policy_score", 0.0)) > 0.87
        and classical.get("development_mean_assay_calls") == 2.0
        and classical.get("heldout_mean_assay_calls") == 2.0
        and classical.get("development_assay_unique_rate") == 1.0
        and classical.get("heldout_assay_unique_rate") == 1.0
        and document.get("secure_baseline_exactly_matches_direct") is True
        and document.get("search_visible_metric_keys")
        == ["combined_score", "feasibility_rate", "raw_score", "valid"]
        and all(checks.values())
        and len(checks) == 17
        and isolation.get("fresh_process_per_world_passed") is True
        and isolation.get("fail_closed_passed") is True
        and isolation.get("passed") is True
        and len(isolation.get("records") or []) == 4
        and set(task_hashes) == expected_hash_paths
        and task_hashes.get(
            "benchmarks/MaterialsScience/AlloyHardnessOptimization/solution.py"
        ) == BASELINE_SHA256
        and task_hashes.get(
            "benchmarks/MaterialsScience/AlloyHardnessOptimization/verification/alloy_hardness_v1.json"
        ) == DATA_SHA256
    ):
        raise ValueError("AlloyHardnessOptimization task calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "frozen_data_sha256": rebuild["rebuilt_sha256"],
        "counts": counts,
        "proxy_alpha": proxy["alpha"],
        "proxy_leave_one_doi_out": leave_one_doi_out,
        "anchors": anchors,
        "baseline": _compact_calibration_metrics(baseline),
        "reference": _compact_calibration_metrics(reference),
        "truth_blind_assay_policy": _compact_calibration_metrics(classical),
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


def _replay_retained_sources(
    sources: dict[str, Path], expected: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    spec = find_task(TASK, include_uncertified=True)
    results: dict[str, dict[str, Any]] = {}
    by_hash: dict[str, dict[str, Any]] = {}
    for name, path in sources.items():
        source_hash = _sha256(path)
        if source_hash not in by_hash:
            metrics = evaluate_candidate(spec, path, timeout_s=90)
            target = expected[source_hash]
            by_hash[source_hash] = {
                "source_sha256": source_hash,
                "valid": metrics.get("valid"),
                "combined_score": metrics.get("combined_score"),
                "heldout_policy_score": metrics.get("heldout_policy_score"),
                "metrics_exactly_match_bound_trajectory": metrics == target,
            }
        results[name] = dict(by_hash[source_hash])
    return results


def _load_model(
    label: str, relative: str, replay_retained_sources: bool = True,
) -> dict[str, Any]:
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
        raise ValueError("untrusted alloy model report: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one successful alloy model run")
    run = runs[0]
    config = document.get("config") or {}
    llm_config = config.get("llm") or {}
    if not (
        run.get("task") == TASK
        and run.get("algorithm") == "greedy_rewrite"
        and run.get("feedback_mode") == expected["mode"]
        and run.get("seed") == expected["seed"]
        and config.get("budget") == expected["budget"]
        and llm_config.get("model") == "gpt-5.5"
        and llm_config.get("reasoning_effort") == "low"
        and llm_config.get("server_side_seed_control") is False
    ):
        raise ValueError("unexpected alloy calibration condition")

    workdir = Path(run["workdir"]).resolve()
    try:
        relative_workdir = workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("alloy workdir is outside repository") from exc
    trajectory_path = workdir / "trajectory.jsonl"
    raw_events = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable alloy snapshot differs from raw trajectory")
    if len(raw_events) != expected["budget"] + 1:
        raise ValueError("alloy trajectory is incomplete")

    trajectory = []
    expected_by_hash: dict[str, dict[str, Any]] = {}
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            int(compact["step"]) == int(raw["step"])
            and compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
        ):
            raise ValueError("raw and portable alloy lineage differs")
        metrics = raw.get("metrics") or {}
        science = _science_metrics(metrics)
        if any(
            value is not None and not _finite_number(value)
            for value in science.values()
        ):
            raise ValueError("alloy science metric is non-finite")
        per_world = metrics.get("per_world") or []
        if len(per_world) != 13:
            raise ValueError("alloy event does not retain all thirteen worlds")
        if sum(row.get("split") == "development" for row in per_world) != 8:
            raise ValueError("alloy development world count differs")
        if sum(row.get("split") == "heldout" for row in per_world) != 5:
            raise ValueError("alloy held-out world count differs")
        expected_by_hash[raw["candidate_sha256"]] = metrics
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
                {field: row.get(field) for field in PER_WORLD_FIELDS}
                for row in per_world
            ],
            "llm": raw.get("llm") or {},
            "algorithm_metadata": raw.get("algorithm_metadata") or {},
        })

    summary = run.get("summary") or {}
    manifest_path = workdir / "run_manifest.json"
    checkpoint_path = workdir / "checkpoint.json"
    summary_path = workdir / "summary.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if expected["mode"] == "selection_blind"
        else "online_incumbent"
    )
    best_program_path = workdir / "best_program.py"
    terminal_program_path = workdir / "solution.py"
    best_hash = _sha256(best_program_path)
    terminal_hash = _sha256(terminal_program_path)
    selected_events = [
        event for event in trajectory if event["candidate_sha256"] == best_hash
    ]
    if len(selected_events) != 1:
        raise ValueError("alloy best program does not identify one event")
    selected = selected_events[0]
    proposals = trajectory[1:]
    failure_counts: dict[str, int] = {}
    for event in proposals:
        if event["failure_kind"]:
            failure_counts[event["failure_kind"]] = (
                failure_counts.get(event["failure_kind"], 0) + 1
            )
    scans = {
        "selected_best": _source_scan(best_program_path),
        "terminal": _source_scan(terminal_program_path),
    }
    retained_paths = {
        "selected_best": best_program_path,
        "terminal": terminal_program_path,
    }
    replay = (
        _replay_retained_sources(retained_paths, expected_by_hash)
        if replay_retained_sources
        else {}
    )
    record = {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(report_path),
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "llm_condition_sha256": config.get("llm_condition_sha256"),
        "model": llm_config.get("model"),
        "reasoning_effort": llm_config.get("reasoning_effort"),
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
        "checkpoint_sha256": _sha256(checkpoint_path),
        "summary_sha256": _sha256(summary_path),
        "task_contract_sha256": manifest.get("task_contract_sha256"),
        "runtime_source_sha256": manifest.get("runtime_source_sha256"),
        "baseline_candidate_sha256": trajectory[0]["candidate_sha256"],
        "best_program": str(relative_workdir / "best_program.py"),
        "best_program_sha256": best_hash,
        "terminal_program": str(relative_workdir / "solution.py"),
        "terminal_program_sha256": terminal_hash,
        "checkpoint_best_program_sha256": checkpoint.get("best_sha256"),
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
        "retained_artifact_scans": scans,
        "retained_artifact_replays": replay,
        "artifact_retention_scope": (
            "selected-best and terminal source artifacts; all intermediate "
            "candidates remain trajectory-hash-bound but unretained"
        ),
    }
    record["integrity_passed"] = bool(
        record["baseline_candidate_sha256"] == BASELINE_SHA256
        and _lineage_is_valid(record)
        and record["selection_policy"] == expected_policy
        and record["oracle_calls"] == expected["budget"] + 1
        and record["budget_units"] == expected["budget"] + 1
        and record["llm_calls"] == expected["budget"]
        and record["provider_usage_records"] == expected["budget"]
        and int(run["evaluated"]) == expected["budget"] + 1
        and record["accepted_proposals"]
        == sum(event["accepted"] for event in proposals)
        and abs(record["best_score"] - selected["score"]) < 1.0e-12
        and record["checkpoint_best_program_sha256"] == best_hash
        and record["terminal_program_sha256"] == record["terminal_candidate_sha256"]
        and all(scan["passed"] for scan in scans.values())
        and (
            not replay_retained_sources
            or all(
                item["metrics_exactly_match_bound_trajectory"]
                for item in replay.values()
            )
        )
        and all(event["valid_world_count"] == 13 for event in trajectory)
        and manifest.get("task_id") == TASK
        and manifest.get("feedback_mode") == expected["mode"]
        and manifest.get("seed") == expected["seed"]
        and manifest.get("llm_condition_sha256")
        == config.get("llm_condition_sha256")
        and isinstance(record["task_contract_sha256"], str)
        and isinstance(record["runtime_source_sha256"], str)
    )
    if not record["integrity_passed"]:
        raise ValueError("alloy lineage, replay, accounting, or shortcut gate failed")
    return record


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    runtime_source_equivalent: bool = True,
    runtime_source_changes: list[str] | None = None,
    source_migration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    conditions = {record["llm_condition_sha256"] for record in records.values()}
    task_contracts = {record["task_contract_sha256"] for record in records.values()}
    runtime_sources = {record["runtime_source_sha256"] for record in records.values()}
    selected_hashes = {
        record["selected_candidate_sha256"] for record in records.values()
    }
    proposals = [
        event for record in records.values() for event in record["trajectory"][1:]
    ]
    selected = {
        label: record["selected_metrics"] for label, record in records.items()
    }
    migration_equivalent = bool(
        not runtime_source_changes
        or (source_migration or {}).get("accepted") is True
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
        "input_tokens": normal["input_tokens"] - blind["input_tokens"],
        "output_tokens": normal["output_tokens"] - blind["output_tokens"],
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "wall_seconds": normal["wall_seconds"] - blind["wall_seconds"],
    })

    normal_step_one = normal["trajectory"][1]
    normal_selected = normal["trajectory"][normal["selected_step"]]
    blind_step_one = blind["trajectory"][1]
    blind_step_two = blind["trajectory"][2]
    blind_equal_score_better_science = (
        blind_step_two["score"] == blind_step_one["score"]
        and blind_step_two["science_metrics"]["development_prediction_score"]
        > blind_step_one["science_metrics"]["development_prediction_score"]
        and blind_step_two["science_metrics"]["heldout_prediction_score"]
        > blind_step_one["science_metrics"]["heldout_prediction_score"]
        and blind_step_two["science_metrics"][
            "development_mean_prediction_interval_width_hv"
        ]
        < blind_step_one["science_metrics"][
            "development_mean_prediction_interval_width_hv"
        ]
        and blind_step_two["science_metrics"][
            "heldout_mean_prediction_interval_width_hv"
        ]
        < blind_step_one["science_metrics"][
            "heldout_mean_prediction_interval_width_hv"
        ]
        and blind_step_two["science_metrics"][
            "development_prediction_interval_coverage"
        ]
        == blind_step_one["science_metrics"][
            "development_prediction_interval_coverage"
        ]
        == 1.0
        and blind_step_two["science_metrics"][
            "heldout_prediction_interval_coverage"
        ]
        == blind_step_one["science_metrics"][
            "heldout_prediction_interval_coverage"
        ]
        == 1.0
    )
    execution_passed = bool(
        calibration["source_revision"] == INPUT_SOURCE_REVISION
        and revisions == {INPUT_SOURCE_REVISION}
        and runtime_source_equivalent
        and migration_equivalent
        and len(scopes) == 1
        and tuple(calibration.get("source_scope") or []) in scopes
        and len(conditions) == 1
        and None not in conditions
        and len(task_contracts) == 1
        and None not in task_contracts
        and len(runtime_sources) == 1
        and None not in runtime_sources
        and len(selected_hashes) == 3
        and all(record["integrity_passed"] for record in records.values())
        and one["proposal_budget"] == 1
        and one["seed"] == 0
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and normal["seed"] == blind["seed"] == 1
        and normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and len(proposals) == 7
        and all(event["valid"] for event in proposals)
        and all(event["valid_world_count"] == 13 for event in proposals)
        and one["selected_step"] == 1
        and normal["selected_step"] == 3
        and blind["selected_step"] == 1
        and normal_step_one["score"] == 0.0
        and normal_step_one["science_metrics"]["heldout_policy_score"] > 0.15
        and not normal_step_one["accepted"]
        and normal_selected["science_metrics"]["heldout_policy_score"] == 0.0
        and blind_equal_score_better_science
        and not blind_step_two["accepted"]
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "RETROSPECTIVE_PUBLIC_DOI_GROUPED_ALLOY_HARDNESS_REPLAY_"
            "SINGLE_RUN_CALIBRATION_NOT_FEEDBACK_CAUSAL_PRETRAINING_CLEAN_"
            "PROSPECTIVE_SYNTHESIS_MECHANICAL_VALIDATION_OR_AUTONOMOUS_"
            "DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_source_revision": INPUT_SOURCE_REVISION,
        "input_task_runtime_source_equivalent": runtime_source_equivalent,
        "input_task_runtime_source_unchanged": not bool(
            runtime_source_changes
        ),
        "input_task_runtime_source_changes": runtime_source_changes or [],
        "input_task_runtime_source_migration": source_migration,
        "input_task_runtime_source_migration_equivalent": migration_equivalent,
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
            "positive_development_count": sum(
                event["score"] > 0.0 for event in proposals
            ),
            "all_thirteen_worlds_valid_count": sum(
                event["valid_world_count"] == 13 for event in proposals
            ),
            "failure_counts": {
                kind: sum(event["failure_kind"] == kind for event in proposals)
                for kind in sorted({
                    event["failure_kind"]
                    for event in proposals
                    if event["failure_kind"]
                })
            },
        },
        "normal_minus_blind_budget_three_descriptive_contrast": contrast,
        "selected_science_axes": {
            label: {
                "development_visible_score": records[label]["best_score"],
                "heldout_visible_score": metrics["heldout_policy_score"],
                "development_prediction_score": metrics[
                    "development_prediction_score"
                ],
                "heldout_prediction_score": metrics["heldout_prediction_score"],
                "development_interval_coverage": metrics[
                    "development_prediction_interval_coverage"
                ],
                "heldout_interval_coverage": metrics[
                    "heldout_prediction_interval_coverage"
                ],
                "development_confirmation_coverage": metrics[
                    "development_selected_confirmation_coverage"
                ],
                "heldout_confirmation_coverage": metrics[
                    "heldout_selected_confirmation_coverage"
                ],
                "development_confirmation_mae_hv": metrics[
                    "development_independent_confirmation_mae_hv"
                ],
                "heldout_confirmation_mae_hv": metrics[
                    "heldout_independent_confirmation_mae_hv"
                ],
            }
            for label, metrics in selected.items()
        },
        "selection_axis_counterexamples": {
            "normal_rejected_heldout_improvement": {
                "step": normal_step_one["step"],
                "development_visible_score": normal_step_one["score"],
                "accepted": normal_step_one["accepted"],
                "heldout_policy_score": normal_step_one["science_metrics"][
                    "heldout_policy_score"
                ],
                "selected_step": normal["selected_step"],
                "selected_development_visible_score": normal["best_score"],
                "selected_heldout_policy_score": normal["selected_metrics"][
                    "heldout_policy_score"
                ],
                "development_only_selection_discards_heldout_improvement": (
                    normal_step_one["score"] == 0.0
                    and normal_step_one["science_metrics"]["heldout_policy_score"]
                    > normal["selected_metrics"]["heldout_policy_score"]
                    and not normal_step_one["accepted"]
                ),
            },
            "blind_equal_visible_score_better_prediction": {
                "selected_step": blind_step_one["step"],
                "discarded_step": blind_step_two["step"],
                "selected_visible_score": blind_step_one["score"],
                "discarded_visible_score": blind_step_two["score"],
                "selected_development_prediction_score": blind_step_one[
                    "science_metrics"
                ]["development_prediction_score"],
                "discarded_development_prediction_score": blind_step_two[
                    "science_metrics"
                ]["development_prediction_score"],
                "selected_heldout_prediction_score": blind_step_one[
                    "science_metrics"
                ]["heldout_prediction_score"],
                "discarded_heldout_prediction_score": blind_step_two[
                    "science_metrics"
                ]["heldout_prediction_score"],
                "selected_development_interval_width_hv": blind_step_one[
                    "science_metrics"
                ]["development_mean_prediction_interval_width_hv"],
                "discarded_development_interval_width_hv": blind_step_two[
                    "science_metrics"
                ]["development_mean_prediction_interval_width_hv"],
                "selected_heldout_interval_width_hv": blind_step_one[
                    "science_metrics"
                ]["heldout_mean_prediction_interval_width_hv"],
                "discarded_heldout_interval_width_hv": blind_step_two[
                    "science_metrics"
                ]["heldout_mean_prediction_interval_width_hv"],
                "equal_visible_score_discards_better_prediction_with_same_coverage": (
                    blind_equal_score_better_science
                    and not blind_step_two["accepted"]
                ),
            },
        },
        "descriptive_findings": {
            "all_seven_model_proposals_are_protocol_valid": all(
                event["valid"] for event in proposals
            ),
            "all_seven_model_proposals_run_all_thirteen_worlds": all(
                event["valid_world_count"] == 13 for event in proposals
            ),
            "three_selected_artifacts_are_source_distinct": len(selected_hashes) == 3,
            "all_selected_models_use_full_unique_assay_budget": all(
                metrics["development_mean_assay_calls"] == 2.0
                and metrics["heldout_mean_assay_calls"] == 2.0
                and metrics["development_assay_unique_rate"] == 1.0
                and metrics["heldout_assay_unique_rate"] == 1.0
                for metrics in selected.values()
            ),
            "all_selected_models_have_full_prediction_interval_coverage": all(
                metrics["development_prediction_interval_coverage"] == 1.0
                and metrics["heldout_prediction_interval_coverage"] == 1.0
                for metrics in selected.values()
            ),
            "all_selected_models_have_sparse_exact_recipe_confirmation": all(
                metrics["development_selected_confirmation_coverage"]
                <= 1.0 / 12.0
                and metrics["heldout_selected_confirmation_coverage"]
                <= 1.0 / 15.0
                for metrics in selected.values()
            ),
            "all_selected_heldout_visible_scores_are_zero": all(
                metrics["heldout_policy_score"] == 0.0
                for metrics in selected.values()
            ),
            "normal_development_selection_discards_heldout_improvement": (
                normal_step_one["score"] == 0.0
                and normal_step_one["science_metrics"]["heldout_policy_score"]
                > normal["selected_metrics"]["heldout_policy_score"]
                and not normal_step_one["accepted"]
            ),
            "blind_equal_visible_score_discards_better_prediction": (
                blind_equal_score_better_science and not blind_step_two["accepted"]
            ),
            "normal_and_blind_selected_development_scores_equal": (
                contrast["best_score"] == 0.0
            ),
            "normal_and_blind_are_oracle_call_matched": contrast["oracle_calls"] == 0,
            "normal_and_blind_are_input_token_matched": contrast["input_tokens"] == 0,
            "normal_and_blind_are_total_token_matched": contrast["total_tokens"] == 0,
            "retained_artifacts_pass_shortcut_scan": all(
                scan["passed"]
                for record in records.values()
                for scan in record["retained_artifact_scans"].values()
            ),
            "retained_artifact_replays_are_deterministic": all(
                replay["metrics_exactly_match_bound_trajectory"]
                for record in records.values()
                for replay in record["retained_artifact_replays"].values()
            ),
            "exact_recipe_confirmation_supports_broad_generalization": False,
            "feedback_effect_identified": False,
            "pretraining_contamination_ruled_out": False,
            "prospective_alloy_discovery_demonstrated": False,
        },
        "limitations": [
            "Each model condition has one run; no confidence interval, population, leaderboard or scaling-law estimate is supported.",
            "The endpoint exposes no server-side generation seed, so equal local seed labels do not pair model randomness.",
            "Normal and selection-blind match input tokens and oracle calls but differ in output tokens, prompts, parent histories, source artifacts and wall time; their contrast is descriptive, not causal.",
            "Budget one uses local seed label zero and budget three label one; they are independent calibrations, not trajectory prefixes.",
            "Only selected-best and terminal source artifacts are retained; intermediate source text is unavailable, although every proposal remains hash- and trajectory-bound.",
            "Static scanning and a networkless sandbox cannot rule out pretraining memorization or semantically hidden public-data lookup.",
            "The 13 worlds are public DOI-grouped studies from one retrospective literature compilation; no alloy was synthesized or mechanically tested prospectively.",
            "The benchmark rules were frozen after inspection of the public compilation and were not prospectively preregistered.",
            "Study-held transfer does not harmonize processing, microstructure or indentation protocol, and exact composition/process records from another DOI cover only six of 65 target recipes.",
            "The assay reveals a target-study hardness value already present in the public replay; it is not a new physical experiment.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def analyze(replay_retained_sources: bool = True) -> dict[str, Any]:
    calibration = _load_calibration(CALIBRATION)
    records = {
        label: _load_model(
            label, relative, replay_retained_sources=replay_retained_sources,
        )
        for label, relative in REPORTS.items()
    }
    current_revision = source_provenance(ROOT).get("git_revision")
    changes = _source_changes(INPUT_SOURCE_REVISION, current_revision)
    source_migration = (
        _source_migration_status(current_revision, changes) if changes else None
    )
    runtime_source_equivalent = bool(
        not changes or (source_migration or {}).get("accepted") is True
    )
    return _analyze_records(
        calibration,
        records,
        runtime_source_equivalent=runtime_source_equivalent,
        runtime_source_changes=changes,
        source_migration=source_migration,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--skip-replay",
        action="store_true",
        help="skip deterministic retained-source re-evaluation",
    )
    args = parser.parse_args()
    report = analyze(replay_retained_sources=not args.skip_replay)
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
