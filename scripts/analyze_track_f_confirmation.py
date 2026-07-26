#!/usr/bin/env python3
"""Analyze the fixed Track F cohort after deterministic fresh confirmation.

The sole powered primary is the independent-provider-draw contrast between
``normal`` and ``selection_blind`` for ActiveLaw fresh normalized mechanism at
the common realized-token endpoint.  Candidate-invalid artifacts remain in the
fixed denominator at the normalized score floor.  Infrastructure failures,
missing cells, stochastic replays, source drift or an edited analysis plan fail
closed.  Diffraction and all other contrasts are descriptive secondary stress
tests and are never promoted to a general scientific-agent claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scipy import __version__ as scipy_version
from scipy.stats import t as student_t


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.algorithms.common import (  # noqa: E402
    atomic_write_text,
    runtime_source_sha256,
    task_contract_sha256,
)
from frontier_science.provenance import (  # noqa: E402
    SOURCE_SCOPE,
    finalize_report_trust,
    source_provenance,
)
from frontier_science.registry import find_task  # noqa: E402


EXPECTED_MODES = (
    "normal", "score_only", "delayed_replay", "selection_blind",
)
EXPECTED_ENDPOINTS = (
    "full_proposal_horizon", "common_total_token_horizon",
)
PRIMARY_TASK = "DynamicalSystems/ActiveLawDiscovery"
PRIMARY_CONDITION = "normal"
PRIMARY_CONTROL = "selection_blind"
PRIMARY_ENDPOINT = "common_total_token_horizon"
PRIMARY_AXIS = "confirmation_normalized_mechanism_score"
SECONDARY_TASK = "Optics/DiffractionGratingDesign"
SECONDARY_AXIS = "confirmation_robustness_score"


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _mean_sd(values: list[float]) -> dict[str, Any]:
    if not values or any(not math.isfinite(value) for value in values):
        raise ValueError("analysis values must be non-empty and finite")
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "sample_sd": statistics.stdev(values) if len(values) > 1 else None,
        "minimum": min(values),
        "maximum": max(values),
    }


def independent_welch_contrast(
    treatment: list[float], control: list[float], *, alpha: float,
) -> dict[str, Any]:
    """Return a two-sided independent Welch contrast and 1-alpha CI."""
    if (
        len(treatment) < 2
        or len(control) < 2
        or not 0.0 < alpha < 1.0
        or any(not math.isfinite(value) for value in treatment + control)
    ):
        raise ValueError("invalid independent Welch inputs")
    treatment_summary = _mean_sd(treatment)
    control_summary = _mean_sd(control)
    difference = treatment_summary["mean"] - control_summary["mean"]
    s1 = float(treatment_summary["sample_sd"])
    s0 = float(control_summary["sample_sd"])
    v1 = s1 * s1 / len(treatment)
    v0 = s0 * s0 / len(control)
    standard_error = math.sqrt(v1 + v0)
    denominator = (
        (v1 * v1) / (len(treatment) - 1)
        + (v0 * v0) / (len(control) - 1)
    )
    variance_degenerate = standard_error == 0.0 or denominator == 0.0
    if variance_degenerate:
        degrees_of_freedom = None
        statistic = None
        p_value = None
        lower = upper = difference
    else:
        degrees_of_freedom = (v1 + v0) ** 2 / denominator
        statistic = difference / standard_error
        p_value = 2.0 * float(student_t.sf(abs(statistic), degrees_of_freedom))
        critical = float(student_t.ppf(1.0 - alpha / 2.0, degrees_of_freedom))
        lower = difference - critical * standard_error
        upper = difference + critical * standard_error
    pooled_denominator = len(treatment) + len(control) - 2
    pooled_variance = (
        (len(treatment) - 1) * s1 * s1
        + (len(control) - 1) * s0 * s0
    ) / pooled_denominator
    pooled_sd = math.sqrt(pooled_variance)
    if pooled_sd > 0.0:
        cohen_d = difference / pooled_sd
        correction = 1.0 - 3.0 / (
            4.0 * (len(treatment) + len(control)) - 9.0
        )
        hedges_g = correction * cohen_d
    else:
        cohen_d = hedges_g = None
    return {
        "treatment": treatment_summary,
        "control": control_summary,
        "difference_treatment_minus_control": difference,
        "standard_error": standard_error,
        "welch_degrees_of_freedom": degrees_of_freedom,
        "welch_t_statistic": statistic,
        "two_sided_p_value": p_value,
        "confidence_level": 1.0 - alpha,
        "confidence_interval": [lower, upper],
        "variance_degenerate": variance_degenerate,
        "cohen_d_pooled": cohen_d,
        "hedges_g_pooled": hedges_g,
    }


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("cannot load %s" % label) from exc
    if not isinstance(document, dict):
        raise ValueError("%s must be a JSON object" % label)
    return document


def _validate_inputs(
    preregistration_path: Path,
    search_report_path: Path,
    confirmation_report_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    prereg = _load_json(preregistration_path, "Track F preregistration")
    search = _load_json(search_report_path, "Track F search report")
    confirmation = _load_json(
        confirmation_report_path, "Track F confirmation report"
    )
    design = prereg.get("design") or {}
    analysis = prereg.get("analysis") or {}
    frozen = prereg.get("frozen_source") or {}
    tasks = [row.get("task") for row in design.get("tasks") or []]
    task_hashes = {
        row.get("task"): row.get("task_contract_sha256")
        for row in design.get("tasks") or []
    }
    replicates = [int(value) for value in design.get("replicate_identifiers") or []]
    prereg_binding = (search.get("config") or {}).get("preregistration") or {}
    confirmation_input = confirmation.get("input") or {}
    implementation = prereg.get("analysis_implementation") or {}
    if not (
        prereg.get("schema_version") == 1
        and prereg.get("preregistration_version") == 1
        and prereg.get("purpose") == "track_f_feedback_confirmatory_study"
        and tasks == [PRIMARY_TASK, SECONDARY_TASK]
        and len(replicates) == design.get("fixed_blocks_per_condition")
        and len(replicates) >= 2
        and len(set(replicates)) == len(replicates)
        and design.get("feedback_modes") == list(EXPECTED_MODES)
        and design.get("proposal_budget") == 3
        and design.get("scheduled_cell_count")
        == len(tasks) * len(EXPECTED_MODES) * len(replicates)
        and isinstance(design.get("confirmation_workers"), int)
        and not isinstance(design.get("confirmation_workers"), bool)
        and design.get("confirmation_workers") > 0
        and design.get("confirmation_worker_isolation") == "spawn_process"
        and design.get("confirmation_look_assignment")
        == "planned_order_before_dispatch"
        and analysis.get("primary_task") == PRIMARY_TASK
        and analysis.get("primary_condition") == PRIMARY_CONDITION
        and analysis.get("primary_control") == PRIMARY_CONTROL
        and analysis.get("primary_contrast") == "normal_minus_selection_blind"
        and analysis.get("primary_endpoint") == PRIMARY_ENDPOINT
        and analysis.get("primary_axis") == PRIMARY_AXIS
        and analysis.get("statistical_test")
        == "two_sided_independent_welch_t"
        and _finite_number(analysis.get("two_sided_alpha"))
        and 0.0 < float(analysis["two_sided_alpha"]) < 1.0
        and _finite_number(analysis.get("minimum_important_difference"))
        and float(analysis["minimum_important_difference"]) > 0.0
        and analysis.get("candidate_invalid_score") == 0.0
        and analysis.get("secondary_task") == SECONDARY_TASK
        and analysis.get("secondary_axis") == SECONDARY_AXIS
        and analysis.get("secondary_inference") == "descriptive_stress_test_only"
        and implementation.get("path")
        == "scripts/analyze_track_f_confirmation.py"
        and implementation.get("sha256") == _sha256(Path(__file__).resolve())
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
        and prereg_binding.get("sha256") == _sha256(preregistration_path)
        and prereg_binding.get("bytes") == len(preregistration_path.read_bytes())
        and confirmation.get("schema_version") == 1
        and confirmation.get("execution_passed") is True
        and confirmation.get("trusted_evidence") is True
        and confirmation.get("passed") is True
        and (confirmation.get("analysis_gate") or {}).get(
            "eligible_for_separate_preregistered_analysis"
        ) is True
        and (confirmation.get("claims") or {}).get(
            "preregistered_primary_hypothesis_test_completed"
        ) is False
        and (confirmation_input.get("preregistration") or {}).get("sha256")
        == _sha256(preregistration_path)
        and (confirmation_input.get("search_report") or {}).get("sha256")
        == _sha256(search_report_path)
    ):
        raise ValueError("Track F inputs differ from the frozen analysis plan")
    current = source_provenance(ROOT)
    search_revision = (search.get("source_provenance") or {}).get("git_revision")
    confirmation_revision = (
        confirmation.get("source_provenance") or {}
    ).get("git_revision")
    if not (
        current.get("git_available") is True
        and current.get("source_tree_dirty") is False
        and (search.get("source_provenance") or {}).get("source_tree_dirty") is False
        and (confirmation.get("source_provenance") or {}).get(
            "source_tree_dirty"
        ) is False
        and _source_equivalent(frozen.get("revision"), current["git_revision"])
        and _source_equivalent(frozen.get("revision"), search_revision)
        and _source_equivalent(frozen.get("revision"), confirmation_revision)
    ):
        raise ValueError("Track F analysis source differs from frozen source")
    expected_cells = len(tasks) * len(EXPECTED_MODES) * len(replicates)
    search_aggregate = search.get("aggregate") or {}
    if not (
        search_aggregate.get("successful_runs") == expected_cells
        and search_aggregate.get("failed_runs") == 0
        and (search_aggregate.get("intent_to_evaluate") or {}).get(
            "scheduled_runs"
        ) == expected_cells
    ):
        raise ValueError("Track F search risk set is incomplete")
    confirmation_parallelism = confirmation.get("confirmation_parallelism") or {}
    if not (
        confirmation_parallelism.get("workers")
        == design.get("confirmation_workers")
        and confirmation_parallelism.get("worker_isolation") == "spawn_process"
        and confirmation_parallelism.get("submission_order")
        == "planned_evaluations"
        and confirmation_parallelism.get("look_indices_assigned_before_dispatch")
        is True
        and confirmation_parallelism.get("completion_order_affects_analysis")
        is False
    ):
        raise ValueError("Track F confirmation parallelism differs from plan")
    return prereg, search, confirmation, {
        "tasks": tasks,
        "replicates": replicates,
        "alpha": float(analysis["two_sided_alpha"]),
        "minimum_important_difference": float(
            analysis["minimum_important_difference"]
        ),
        "candidate_invalid_score": float(analysis["candidate_invalid_score"]),
        "current_provenance": current,
    }


def _endpoint_records(
    confirmation: dict[str, Any], design: dict[str, Any],
) -> list[dict[str, Any]]:
    tasks = design["tasks"]
    replicates = design["replicates"]
    expected_ids = {
        "%s|%d|%s|%s" % (task, replicate, mode, endpoint)
        for task in tasks
        for replicate in replicates
        for mode in EXPECTED_MODES
        for endpoint in EXPECTED_ENDPOINTS
    }
    planned_rows = confirmation.get("planned_endpoints") or []
    result_rows = confirmation.get("endpoint_results") or []
    planned = {row.get("endpoint_id"): row for row in planned_rows}
    results = {row.get("endpoint_id"): row for row in result_rows}
    if (
        set(planned) != expected_ids
        or set(results) != expected_ids
        or len(planned) != len(planned_rows)
        or len(results) != len(result_rows)
    ):
        raise ValueError("Track F confirmation endpoint risk set differs")
    completion = confirmation.get("completion") or {}
    if not (
        completion.get("incomplete_or_infrastructure_failed_evaluations") == 0
        and completion.get("stochastic_artifacts") == 0
        and completion.get("deterministic_artifacts")
        == completion.get("planned_unique_artifacts")
    ):
        raise ValueError("Track F confirmation replay gate did not pass")
    records = []
    for endpoint_id in sorted(expected_ids):
        planned_row = planned[endpoint_id]
        result = results[endpoint_id]
        immutable_keys = (
            "endpoint_id", "task", "replicate_id", "condition", "endpoint",
            "common_total_token_horizon", "completed_through_step",
            "tokens_spent_by_completed_step", "best_source_step", "search_score",
            "candidate_sha256", "context_sha256", "artifact_id",
        )
        if not (
            all(result.get(key) == planned_row.get(key) for key in immutable_keys)
            and result.get("deterministic") is True
            and result.get("stochastic_artifact") is False
            and isinstance(result.get("metrics"), dict)
            and not bool(result["metrics"].get("infrastructure_failure"))
            and result["metrics"].get("trusted_context_sha256")
            == result.get("context_sha256")
        ):
            raise ValueError("Track F confirmation endpoint binding differs")
        metrics = result["metrics"]
        candidate_valid = float(metrics.get("valid", 0.0)) >= 1.0
        axis = PRIMARY_AXIS if result["task"] == PRIMARY_TASK else SECONDARY_AXIS
        raw_value = metrics.get(axis)
        if candidate_valid:
            if not _finite_number(raw_value):
                raise ValueError("valid confirmation endpoint lacks its science axis")
            value = float(raw_value)
            if not -1.0e-12 <= value <= 1.0 + 1.0e-12:
                raise ValueError("confirmation normalized science axis is out of range")
            value = min(1.0, max(0.0, value))
            imputed_invalid_floor = False
        else:
            value = float(design["candidate_invalid_score"])
            imputed_invalid_floor = True
        records.append({
            **{key: result[key] for key in immutable_keys},
            "science_axis": axis,
            "failure_inclusive_science_score": value,
            "candidate_valid": candidate_valid,
            "candidate_invalid_floor_applied": imputed_invalid_floor,
        })
    for task in tasks:
        for replicate in replicates:
            rows = [
                row for row in records
                if row["task"] == task and row["replicate_id"] == replicate
            ]
            horizons = {row["common_total_token_horizon"] for row in rows}
            if len(horizons) != 1 or next(iter(horizons)) <= 0:
                raise ValueError("common token horizon differs within a search block")
    return records


def _condition_summaries(
    records: list[dict[str, Any]], design: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summaries = []
    contrasts = []
    expected_n = len(design["replicates"])
    for task in design["tasks"]:
        for endpoint in EXPECTED_ENDPOINTS:
            by_mode = {}
            for mode in EXPECTED_MODES:
                rows = [
                    row for row in records
                    if row["task"] == task
                    and row["endpoint"] == endpoint
                    and row["condition"] == mode
                ]
                if len(rows) != expected_n:
                    raise ValueError("condition endpoint sample size differs")
                values = [row["failure_inclusive_science_score"] for row in rows]
                by_mode[mode] = values
                summaries.append({
                    "task": task,
                    "endpoint": endpoint,
                    "condition": mode,
                    "science_axis": rows[0]["science_axis"],
                    "failure_inclusive_score": _mean_sd(values),
                    "candidate_valid_count": sum(row["candidate_valid"] for row in rows),
                    "candidate_invalid_count": sum(
                        not row["candidate_valid"] for row in rows
                    ),
                    "candidate_valid_rate": sum(
                        row["candidate_valid"] for row in rows
                    ) / len(rows),
                    "mean_completed_through_step": statistics.mean(
                        row["completed_through_step"] for row in rows
                    ),
                    "mean_tokens_spent_by_completed_step": statistics.mean(
                        row["tokens_spent_by_completed_step"] for row in rows
                    ),
                })
            for control in EXPECTED_MODES[1:]:
                contrast = independent_welch_contrast(
                    by_mode["normal"], by_mode[control], alpha=design["alpha"]
                )
                contrasts.append({
                    "task": task,
                    "endpoint": endpoint,
                    "contrast": "normal_minus_%s" % control,
                    "inference_scope": (
                        "powered_confirmatory_primary"
                        if task == PRIMARY_TASK
                        and endpoint == PRIMARY_ENDPOINT
                        and control == PRIMARY_CONTROL
                        else "descriptive_secondary_no_multiplicity_claim"
                    ),
                    **contrast,
                })
    return summaries, contrasts


def analyze(
    preregistration_path: Path,
    search_report_path: Path,
    confirmation_report_path: Path,
) -> dict[str, Any]:
    prereg, search, confirmation, design = _validate_inputs(
        preregistration_path, search_report_path, confirmation_report_path
    )
    records = _endpoint_records(confirmation, design)
    summaries, contrasts = _condition_summaries(records, design)
    primary = next(
        row for row in contrasts
        if row["task"] == PRIMARY_TASK
        and row["endpoint"] == PRIMARY_ENDPOINT
        and row["contrast"] == "normal_minus_selection_blind"
    )
    estimate = primary["difference_treatment_minus_control"]
    rejects_null = bool(
        not primary["variance_degenerate"]
        and primary["two_sided_p_value"] is not None
        and primary["two_sided_p_value"] < design["alpha"]
    )
    positive_direction = estimate > 0.0
    specific_feedback_effect = rejects_null and positive_direction
    primary_gate = {
        "risk_set_complete": True,
        "fixed_n_per_condition": len(design["replicates"]),
        "candidate_invalidity_included_at_score_floor": True,
        "independent_provider_draw_analysis": True,
        "two_sided_alpha": design["alpha"],
        "rejects_zero_effect_null": rejects_null,
        "effect_direction_is_preregistered_positive": positive_direction,
        "point_estimate_reaches_design_mde": (
            estimate >= design["minimum_important_difference"]
        ),
        "mde_is_power_target_not_additional_significance_threshold": True,
        "supports_specific_active_law_feedback_effect": specific_feedback_effect,
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE / TRACK_F_CONFIRMATORY_ANALYSIS",
        "evidence_scope": (
            "PREREGISTERED_ACTIVE_LAW_FEEDBACK_PRIMARY_WITH_DIFFRACTION_"
            "SECONDARY_NOT_CROSS_TASK_GENERAL_PHYSICAL_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": design["current_provenance"],
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "scipy": scipy_version,
        },
        "inputs": {
            "preregistration": {
                "path": str(preregistration_path.resolve()),
                "sha256": _sha256(preregistration_path),
            },
            "search_report": {
                "path": str(search_report_path.resolve()),
                "sha256": _sha256(search_report_path),
            },
            "confirmation_report": {
                "path": str(confirmation_report_path.resolve()),
                "sha256": _sha256(confirmation_report_path),
            },
        },
        "fixed_design": {
            "tasks": design["tasks"],
            "feedback_modes": list(EXPECTED_MODES),
            "replicate_identifiers": design["replicates"],
            "provider_draw_assumption": "independent_unpaired",
            "candidate_invalid_score": design["candidate_invalid_score"],
            "minimum_important_difference": design[
                "minimum_important_difference"
            ],
            "two_sided_alpha": design["alpha"],
        },
        "risk_set": {
            "search_cell_count": len(design["tasks"])
            * len(EXPECTED_MODES) * len(design["replicates"]),
            "confirmation_endpoint_count": len(records),
            "candidate_invalid_endpoint_count": sum(
                not row["candidate_valid"] for row in records
            ),
            "candidate_invalid_endpoints_retained": True,
            "stochastic_artifact_count": 0,
            "infrastructure_failed_evaluation_count": 0,
        },
        "condition_summaries": summaries,
        "contrasts": contrasts,
        "primary_result": primary,
        "primary_claim_gate": primary_gate,
        "claims": {
            "preregistered_primary_hypothesis_test_completed": True,
            "specific_active_law_feedback_causal_effect_identified": (
                specific_feedback_effect
            ),
            "active_law_procedural_population_effect_estimated": True,
            "diffraction_confirmatory_significance_claim_supported": False,
            "cross_task_general_scientific_agent_effect_identified": False,
            "independent_laboratory_or_physical_validation_completed": False,
            "autonomous_scientific_discovery_demonstrated": False,
        },
        "limitations": [
            "The primary identifies only the frozen GPT-5.5/algorithm/task/procedural-context treatment effect.",
            "Local replicate identifiers do not pair provider-side model randomness; the primary uses independent draws.",
            "Diffraction is a high-variance descriptive stress test and has no confirmatory significance claim.",
            "No heterogeneous task axes are averaged into a cross-task science or discovery score.",
            "Fresh panels are locally sealed procedural simulations, not independent laboratory or physical validation.",
            "A positive primary would not by itself demonstrate autonomous scientific discovery.",
        ],
    }
    finalize_report_trust(report, True)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--search-report", type=Path, required=True)
    parser.add_argument("--confirmation-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output.expanduser().resolve()
    if output.exists():
        raise SystemExit("refusing to overwrite a Track F analysis report")
    try:
        report = analyze(
            args.preregistration.expanduser().resolve(),
            args.search_report.expanduser().resolve(),
            args.confirmation_report.expanduser().resolve(),
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SystemExit(str(exc)) from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output, json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "output": str(output),
        "execution_passed": report["execution_passed"],
        "trusted_evidence": report["trusted_evidence"],
        "primary_effect": report["primary_result"][
            "difference_treatment_minus_control"
        ],
        "primary_two_sided_p_value": report["primary_result"][
            "two_sided_p_value"
        ],
        "specific_feedback_effect_identified": report["claims"][
            "specific_active_law_feedback_causal_effect_identified"
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
