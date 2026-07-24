#!/usr/bin/env python3
"""Bind and analyze SeismicWaveInversion-v2 GPT-5.5 calibrations.

The formal conditions use the documented dictionary returned by ``acquire``.
Three earlier conditions are retained only as superseded contract diagnostics:
their prompts predate that public return-schema documentation and therefore do
not constitute model-performance observations under the current task contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from collections import Counter
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


TASK = "WavePropagation/SeismicWaveInversion"
CALIBRATION = "experiments/seismic_wave_v2_calibration_2026-07-24_v2.json"
REPORTS = {
    "budget_one": "experiments/gpt55_seismic_wave_v2_b1_2026-07-24.json",
    "normal_budget_three": "experiments/gpt55_seismic_wave_v2_b3_2026-07-24.json",
    "blind_budget_three": (
        "experiments/gpt55_seismic_wave_v2_blind_b3_2026-07-24.json"
    ),
}
SUPERSEDED_REPORTS = {
    "underspecified_budget_one": (
        "experiments/gpt55_seismic_wave_v2_underspecified_b1_2026-07-24.json"
    ),
    "underspecified_normal_budget_three": (
        "experiments/gpt55_seismic_wave_v2_underspecified_b3_2026-07-24.json"
    ),
    "underspecified_blind_budget_three": (
        "experiments/gpt55_seismic_wave_v2_underspecified_blind_b3_2026-07-24.json"
    ),
}
EXPECTED_MODEL_SOURCE_REVISION = "e59e7bb7d46a8a5aeb3787ea7af18f01fceee295"
EXPECTED_UNDERSPECIFIED_SOURCE_REVISION = (
    "2ae6725209a77d1d5ad032e9c76054c652786521"
)
TASK_RUNTIME_SCOPE = (
    "frontier_science",
    "benchmarks/WavePropagation/SeismicWaveInversion",
    "requirements-upstream.txt",
)
FIELDS = (
    "combined_score", "valid", "feasibility_rate", "raw_score",
    "mechanism_score", "development_prediction_score",
    "development_far_offset_prediction_score",
    "development_observed_fit_score",
    "development_experiment_information_score", "robustness_score",
    "development_validation_gap", "heldout_policy_score",
    "heldout_mechanism_score", "heldout_prediction_score",
    "heldout_far_offset_prediction_score", "heldout_observed_fit_score",
    "heldout_experiment_information_score", "heldout_robustness_score",
    "development_supported_claim_coverage",
    "heldout_supported_claim_coverage",
    "development_false_discovery_rate", "heldout_false_discovery_rate",
    "development_correct_refusal_rate", "heldout_correct_refusal_rate",
    "development_confidence_calibration_score",
    "heldout_confidence_calibration_score",
    "development_mean_acquisition_calls", "heldout_mean_acquisition_calls",
    "development_mean_budget_units", "heldout_mean_budget_units",
    "development_mean_acquired_traces", "heldout_mean_acquired_traces",
    "heldout_feasibility_rate", "candidate_world_call_count",
    "candidate_world_valid_rate", "candidate_failure_kind", "error_message",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_changes(left: str, right: str) -> list[str]:
    output = subprocess.check_output(
        ["git", "diff", "--name-only", left, right, "--", *TASK_RUNTIME_SCOPE],
        cwd=str(ROOT), text=True, stderr=subprocess.DEVNULL,
    )
    return [line for line in output.splitlines() if line.strip()]


def _scalar(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in FIELDS}


def _world_summary(worlds: Any) -> dict[str, Any] | None:
    if not isinstance(worlds, list) or len(worlds) != 11:
        return None
    supported = [row for row in worlds if row.get("kind") == "in_library"]
    unsupported = [row for row in worlds if row.get("kind") != "in_library"]
    claims = [row for row in supported if not bool(row.get("abstain"))]
    return {
        "world_count": len(worlds),
        "valid_world_count": sum(bool(row.get("valid")) for row in worlds),
        "supported_world_count": len(supported),
        "supported_claim_count": len(claims),
        "supported_claim_coverage": len(claims) / len(supported),
        "development_supported_claim_count": sum(
            row.get("split") == "development" and not bool(row.get("abstain"))
            for row in supported
        ),
        "heldout_supported_claim_count": sum(
            row.get("split") == "heldout" and not bool(row.get("abstain"))
            for row in supported
        ),
        "mean_supported_information": (
            sum(float(row.get("experiment_information_score", 0.0))
                for row in supported) / len(supported)
        ),
        "minimum_supported_information": min(
            float(row.get("experiment_information_score", 0.0))
            for row in supported
        ),
        "supported_full_rank_count": sum(
            int(row.get("experiment_jacobian_rank", 0)) == 9
            for row in supported
        ),
        "supported_full_budget_count": sum(
            float(row.get("acquisition_budget_units", 0.0)) == 12.0
            for row in supported
        ),
        "mean_claimed_mechanism_quality": (
            sum(float(row.get("mechanism_quality", 0.0)) for row in claims)
            / len(claims) if claims else None
        ),
        "unsupported_world_count": len(unsupported),
        "unsupported_correct_refusal_rate": (
            sum(bool(row.get("correct_refusal")) for row in unsupported)
            / len(unsupported)
        ),
        "unsupported_false_discovery_rate": (
            sum(bool(row.get("false_discovery")) for row in unsupported)
            / len(unsupported)
        ),
        "all_supported_worlds_abstained": not claims,
        "all_worlds_abstained": all(bool(row.get("abstain")) for row in worlds),
    }


def _failure_kind(metrics: dict[str, Any], error: Any) -> str | None:
    if metrics.get("candidate_failure_kind"):
        return str(metrics["candidate_failure_kind"])
    message = str(error or metrics.get("error_message") or "")
    return "other_candidate_protocol_error" if message else None


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    baseline = document.get("weak_baseline") or {}
    classical = document.get("truth_blind_nmo_dix_waveform_policy") or {}
    reference = document.get("reference_policy") or {}
    identifiability = document.get("identifiability_checks") or []
    narrow = document.get("narrow_information_checks") or []
    misspecified = document.get("misspecified_resolvability_checks") or []
    independent = document.get("independent_equation_checks") or []
    expected_dimensions = {
        "development_worlds": 6,
        "heldout_worlds": 5,
        "parameters": [
            "v1_m_s", "v2_m_s", "v3_m_s", "h1_center_m",
            "h1_slope_m", "h1_curvature_m", "h2_center_m",
            "h2_slope_m", "h2_curvature_m",
        ],
        "acquisition_budget_units": 12,
        "trace_shape_per_offset": 501,
    }
    if not (
        document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and provenance.get("git_revision") == EXPECTED_MODEL_SOURCE_REVISION
        and document.get("task_dimensions") == expected_dimensions
        and baseline.get("combined_score") == 0.0
        and float(classical.get("combined_score", 0.0)) > 0.997
        and float(classical.get("heldout_policy_score", 0.0)) > 0.994
        and float(classical.get("robustness_score", 0.0)) > 0.998
        and float(classical.get("heldout_robustness_score", 0.0)) > 0.996
        and classical.get("development_supported_claim_coverage") == 1.0
        and classical.get("heldout_supported_claim_coverage") == 1.0
        and classical.get("development_false_discovery_rate") == 0.0
        and classical.get("heldout_false_discovery_rate") == 0.0
        and reference.get("combined_score") == 1.0
        and reference.get("heldout_policy_score") == 1.0
        and len(identifiability) == 7
        and all(row.get("passed") is True and row.get("jacobian_rank") == 9
                for row in identifiability)
        and len(narrow) == 7
        and all(row.get("passed") is True and row.get("narrow_rank") == 5
                and row.get("narrow_information_score") == 0.0 for row in narrow)
        and len(misspecified) == 2
        and min(float(row["best_public_model_reduced_chi_squared"])
                for row in misspecified) > 33.0
        and len(independent) == 7
        and all(row.get("passed") is True for row in independent)
    ):
        raise ValueError("SeismicWaveInversion-v2 task calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "task_dimensions": document["task_dimensions"],
        "weak_baseline_metrics": _scalar(baseline),
        "classical_policy_metrics": _scalar(classical),
        "reference_policy_metrics": _scalar(reference),
        "supported_reference_rank": min(
            int(row["jacobian_rank"]) for row in identifiability
        ),
        "worst_reference_condition_number": max(
            float(row["condition_number"]) for row in identifiability
        ),
        "narrow_design_rank": max(int(row["narrow_rank"]) for row in narrow),
        "narrow_design_information_score": max(
            float(row["narrow_information_score"]) for row in narrow
        ),
        "misspecified_reduced_chi_squared": [
            float(row["best_public_model_reduced_chi_squared"])
            for row in misspecified
        ],
        "maximum_independent_forward_error": max(
            float(row["maximum_absolute_error"]) for row in independent
        ),
    }


def _lineage_is_valid(record: dict[str, Any]) -> bool:
    events = record["trajectory"]
    baseline_hash = events[0]["candidate_sha256"]
    if record["feedback_mode"] == "selection_blind":
        return all(event["parent_sha256"] == baseline_hash for event in events[1:])
    parent = baseline_hash
    for event in events[1:]:
        if event["parent_sha256"] != parent:
            return False
        if event["accepted"]:
            parent = event["candidate_sha256"]
    return True


def _condition_for_label(label: str) -> tuple[str, int, int]:
    blind = "blind" in label
    budget_one = "budget_one" in label and "budget_three" not in label
    return (
        "selection_blind" if blind else "normal",
        1 if budget_one else 3,
        0 if budget_one else 1,
    )


def _load_model(
    label: str,
    relative: str,
    *,
    expected_revision: str = EXPECTED_MODEL_SOURCE_REVISION,
) -> dict[str, Any]:
    report_path = ROOT / relative
    document = json.loads(report_path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and provenance.get("git_revision") == expected_revision
    ):
        raise ValueError("model report is not trusted at expected source: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one completed model run: %s" % relative)
    run = runs[0]
    config = document.get("config") or {}
    expected_mode, expected_budget, expected_seed = _condition_for_label(label)
    llm = config.get("llm") or {}
    if not (
        run.get("task") == TASK
        and run.get("algorithm") == "greedy_rewrite"
        and run.get("feedback_mode") == expected_mode
        and config.get("budget") == expected_budget
        and run.get("seed") == expected_seed
        and llm.get("wire") == "responses"
        and llm.get("model") == "gpt-5.5"
        and llm.get("server_side_seed_control") is False
    ):
        raise ValueError("unexpected model condition: %s" % relative)

    workdir = Path(run["workdir"]).resolve()
    try:
        relative_workdir = workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("model workdir is outside repository") from exc
    trajectory_path = workdir / "trajectory.jsonl"
    raw_events = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable snapshot differs from raw trajectory: %s" % relative)
    if len(raw_events) != expected_budget + 1:
        raise ValueError("trajectory length disagrees with condition budget")

    trajectory = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            int(compact["step"]) == int(raw["step"])
            and compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
        ):
            raise ValueError("raw/compact trajectory lineage differs")
        metrics = raw.get("metrics") or {}
        trajectory.append({
            "step": int(raw["step"]),
            "score": float(raw["score"]),
            "best_score": float(raw["best_score"]),
            "valid": bool(raw["valid"]),
            "accepted": bool(raw["accepted"]),
            "candidate_sha256": raw["candidate_sha256"],
            "parent_sha256": raw["parent_sha256"],
            "failure_kind": _failure_kind(metrics, raw.get("error")),
            "world_summary": _world_summary(metrics.get("per_world")),
            **_scalar(metrics),
        })

    record = {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(report_path),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "llm_condition_sha256": config.get("llm_condition_sha256"),
        "model": llm.get("model"),
        "server_side_seed_control": llm.get("server_side_seed_control"),
        "feedback_mode": run["feedback_mode"],
        "feedback_scope": (run.get("summary") or {}).get("feedback_scope"),
        "selection_policy": (run.get("summary") or {}).get("selection_policy"),
        "seed": int(run["seed"]),
        "proposal_budget": int(config["budget"]),
        "oracle_calls": int(run["summary"]["oracle_calls"]),
        "total_tokens": int(run["summary"]["llm"]["total_tokens"]),
        "wall_seconds": float(run["summary"]["wall_seconds"]),
        "best_score": float(run["best"]),
        "selected_step": max(
            int(event["step"]) for event in trajectory if event["accepted"]
        ),
        "best_program": str(relative_workdir / "best_program.py"),
        "trajectory": trajectory,
    }
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if expected_mode == "selection_blind" else "online_incumbent"
    )
    selected = next(
        event for event in trajectory if event["step"] == record["selected_step"]
    )
    if not (
        _lineage_is_valid(record)
        and record["selection_policy"] == expected_policy
        and int(run["evaluated"]) == record["oracle_calls"]
        and int(raw_events[-1]["oracle_calls"]) == record["oracle_calls"]
        and abs(selected["score"] - record["best_score"]) <= 1.0e-12
        and _sha256(workdir / "best_program.py") == selected["candidate_sha256"]
    ):
        raise ValueError("model lineage, accounting or selected artifact gate failed")
    return record


def _proposal_summary(record: dict[str, Any]) -> dict[str, Any]:
    proposals = record["trajectory"][1:]
    valid = [event for event in proposals if event["valid"]]
    all_supported_abstain = [
        event for event in valid
        if (event.get("world_summary") or {}).get(
            "all_supported_worlds_abstained"
        ) is True
    ]
    claims = [
        event for event in valid
        if (event.get("world_summary") or {}).get("supported_claim_count", 0) > 0
    ]
    return {
        "proposal_count": len(proposals),
        "valid_proposal_count": len(valid),
        "invalid_proposal_count": len(proposals) - len(valid),
        "failure_counts": dict(Counter(
            event["failure_kind"] for event in proposals if event["failure_kind"]
        )),
        "all_supported_worlds_abstained_count": len(all_supported_abstain),
        "supported_claiming_proposal_count": len(claims),
        "supported_claim_count": sum(
            event["world_summary"]["supported_claim_count"] for event in claims
        ),
        "valid_proposal_information_scores": [
            event["development_experiment_information_score"] for event in valid
        ],
        "valid_proposal_budget_units": [
            event["development_mean_budget_units"] for event in valid
        ],
    }


def _valid_supported_abstention(event: dict[str, Any]) -> bool:
    worlds = event.get("world_summary") or {}
    return bool(
        event.get("valid")
        and event.get("combined_score") == 0.0
        and event.get("mechanism_score") == 0.0
        and event.get("development_supported_claim_coverage") == 0.0
        and event.get("heldout_supported_claim_coverage") == 0.0
        and event.get("development_false_discovery_rate") == 0.0
        and event.get("heldout_false_discovery_rate") == 0.0
        and event.get("development_correct_refusal_rate") == 1.0
        and event.get("heldout_correct_refusal_rate") == 1.0
        and worlds.get("supported_claim_count") == 0
        and worlds.get("unsupported_correct_refusal_rate") == 1.0
        and worlds.get("unsupported_false_discovery_rate") == 0.0
    )


def _load_superseded_diagnostics() -> dict[str, Any]:
    records = {
        label: _load_model(
            label, relative,
            expected_revision=EXPECTED_UNDERSPECIFIED_SOURCE_REVISION,
        )
        for label, relative in SUPERSEDED_REPORTS.items()
    }
    failures = Counter(
        event["failure_kind"]
        for record in records.values()
        for event in record["trajectory"][1:]
        if event["failure_kind"]
    )
    passed = bool(
        {record["source_revision"] for record in records.values()}
        == {EXPECTED_UNDERSPECIFIED_SOURCE_REVISION}
        and len({record["llm_condition_sha256"] for record in records.values()}) == 1
        and all(_lineage_is_valid(record) for record in records.values())
        and failures == {"candidate_callback_schema_error": 4}
    )
    if not passed:
        raise ValueError("superseded contract-diagnostic gate failed")
    return {
        "classification": "SUPERSEDED_UNDERSPECIFIED_CONTRACT_DIAGNOSTIC",
        "included_in_formal_model_performance": False,
        "reason": (
            "The acquire() return dictionary was not documented in the public "
            "task contract at this source revision; callback-schema failures "
            "therefore diagnose benchmark underspecification, not current-contract "
            "model performance."
        ),
        "source_revision": EXPECTED_UNDERSPECIFIED_SOURCE_REVISION,
        "report_count": len(records),
        "proposal_count": sum(
            len(record["trajectory"]) - 1 for record in records.values()
        ),
        "callback_schema_failure_count": failures[
            "candidate_callback_schema_error"
        ],
        "records": records,
    }


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    superseded: dict[str, Any],
    runtime_source_equivalent: bool = True,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    conditions = {record["llm_condition_sha256"] for record in records.values()}
    all_proposals = [
        event for record in records.values() for event in record["trajectory"][1:]
    ]
    valid = [event for event in all_proposals if event["valid"]]
    invalid = [event for event in all_proposals if not event["valid"]]
    abstentions = [event for event in valid if _valid_supported_abstention(event)]
    claims = [event for event in valid if event not in abstentions]
    summaries = {
        label: _proposal_summary(record) for label, record in records.items()
    }
    classical = calibration["classical_policy_metrics"]
    one_claim = claims[0] if len(claims) == 1 else {}
    execution_passed = bool(
        runtime_source_equivalent
        and revisions == {EXPECTED_MODEL_SOURCE_REVISION}
        and len(scopes) == 1
        and len(conditions) == 1
        and None not in conditions
        and all(record["model"] == "gpt-5.5" for record in records.values())
        and all(record["server_side_seed_control"] is False
                for record in records.values())
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["seed"] == 0
        and normal["seed"] == blind["seed"] == 1
        and one["feedback_mode"] == normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and one["oracle_calls"] == 2
        and normal["oracle_calls"] == blind["oracle_calls"] == 4
        and all(record["best_score"] == 0.0 for record in records.values())
        and all(record["selected_step"] == 0 for record in records.values())
        and all(_lineage_is_valid(record) for record in records.values())
        and all(not event["accepted"] for event in all_proposals)
        and len(all_proposals) == 7
        and len(valid) == 6
        and len(invalid) == 1
        and invalid[0]["failure_kind"] == "candidate_timeout"
        and len(abstentions) == 5
        and len(claims) == 1
        and one_claim.get("development_supported_claim_coverage") == 0.0
        and one_claim.get("heldout_supported_claim_coverage") == 1.0 / 3.0
        and one_claim.get("heldout_policy_score") > 0.10
        and one_claim.get("development_experiment_information_score") == 1.0
        and all(event.get("development_false_discovery_rate") == 0.0
                and event.get("heldout_false_discovery_rate") == 0.0
                for event in valid)
        and all(
            float(event.get("development_experiment_information_score", 0.0))
            >= 0.974 for event in blind["trajectory"][1:]
        )
        and normal["total_tokens"] == 16749
        and blind["total_tokens"] == 17007
        and superseded["included_in_formal_model_performance"] is False
        and float(classical["combined_score"]) > 0.997
        and float(classical["heldout_policy_score"]) > 0.994
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "SEISMIC_WAVE_SINGLE_RUN_CALIBRATION_NOT_CAUSAL_POPULATION_FIELD_"
            "GEOLOGY_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_task_source_revision": calibration["source_revision"],
        "input_model_source_revision": (
            next(iter(revisions)) if len(revisions) == 1 else None
        ),
        "input_task_runtime_source_equivalent": bool(runtime_source_equivalent),
        "input_source_scope_equivalent": len(scopes) == 1,
        "input_llm_condition_equivalent": len(conditions) == 1,
        "task_calibration": calibration,
        "records": records,
        "superseded_contract_diagnostics": superseded,
        "proposal_summary": {
            **summaries,
            "formal_total": {
                "proposal_count": len(all_proposals),
                "valid_proposal_count": len(valid),
                "invalid_proposal_count": len(invalid),
                "supported_abstention_count": len(abstentions),
                "supported_claiming_proposal_count": len(claims),
                "failure_counts": dict(Counter(
                    event["failure_kind"] for event in invalid
                )),
            },
        },
        "normal_minus_blind_diagnostic": {
            "best_score": normal["best_score"] - blind["best_score"],
            "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
            "total_tokens": normal["total_tokens"] - blind["total_tokens"],
            "wall_seconds": normal["wall_seconds"] - blind["wall_seconds"],
            "valid_proposals": (
                summaries["normal_budget_three"]["valid_proposal_count"]
                - summaries["blind_budget_three"]["valid_proposal_count"]
            ),
        },
        "science_vectors": {
            "truth_blind_classical_policy": {
                "optimization_O": classical["combined_score"],
                "fidelity_F": classical["heldout_prediction_score"],
                "mechanism_M": classical["heldout_mechanism_score"],
                "validity_V": classical["heldout_robustness_score"],
                "information_I": classical[
                    "heldout_experiment_information_score"
                ],
                "refusal_R": 1.0 - float(
                    classical["heldout_false_discovery_rate"]
                ),
                "supported_discovery_coverage": classical[
                    "heldout_supported_claim_coverage"
                ],
            },
            "formal_gpt55_nonbaseline_proposals": {
                "proposal_count": len(all_proposals),
                "valid_proposal_count": len(valid),
                "optimization_best_O": max(float(event["combined_score"])
                                             for event in valid),
                "heldout_fidelity_best_F": max(
                    float(event["heldout_prediction_score"]) for event in valid
                ),
                "heldout_mechanism_best_M": max(
                    float(event["heldout_mechanism_score"]) for event in valid
                ),
                "information_min_I": min(
                    float(event["development_experiment_information_score"])
                    for event in valid
                ),
                "information_max_I": max(
                    float(event["development_experiment_information_score"])
                    for event in valid
                ),
                "refusal_R": 1.0,
                "development_supported_discovery_coverage_best": max(
                    float(event["development_supported_claim_coverage"])
                    for event in valid
                ),
                "heldout_supported_discovery_coverage_best": max(
                    float(event["heldout_supported_claim_coverage"])
                    for event in valid
                ),
            },
        },
        "descriptive_findings": {
            "formal_proposals_are_mostly_executable": len(valid) == 6,
            "five_valid_proposals_over_refuse_supported_worlds": (
                len(abstentions) == 5
            ),
            "budget_one_claims_only_one_heldout_supported_world": bool(
                one_claim.get("development_supported_claim_coverage") == 0.0
                and one_claim.get("heldout_supported_claim_coverage") == 1.0 / 3.0
            ),
            "high_information_does_not_imply_mechanism_recovery": bool(
                all(float(event["development_experiment_information_score"])
                    >= 0.974 for event in blind["trajectory"][1:])
                and all(event["mechanism_score"] == 0.0
                        for event in blind["trajectory"][1:])
            ),
            "scalar_zero_conflates_distinct_failure_states": True,
            "formal_valid_proposals_make_no_false_discoveries": all(
                event["development_false_discovery_rate"] == 0.0
                and event["heldout_false_discovery_rate"] == 0.0
                for event in valid
            ),
            "normal_and_blind_are_oracle_call_matched": (
                normal["oracle_calls"] == blind["oracle_calls"]
            ),
            "normal_and_blind_are_not_token_or_wall_time_matched": bool(
                normal["total_tokens"] != blind["total_tokens"]
                and normal["wall_seconds"] != blind["wall_seconds"]
            ),
            "zero_score_contrast_contains_no_feedback_effect_information": (
                normal["best_score"] == blind["best_score"] == 0.0
            ),
        },
        "limitations": [
            "Each formal condition has one run; no confidence interval, model ranking, scaling law or causal feedback estimate is supported.",
            "Normal and selection-blind share a local seed identifier, but Azure exposes no server-side generation seed, so generation randomness is not paired.",
            "Normal and selection-blind are oracle-call matched but differ by 258 tokens and 528.34 seconds; their contrast is descriptive, not causal.",
            "No proposal improved the baseline, so normal never changed its incumbent; the equal zero normal-minus-blind score contains no feedback-effect information.",
            "A zero scalar score covers timeout, high-information over-refusal and a weak held-out-only claim; these states must be inspected on separate protocol, information, mechanism, coverage and refusal axes.",
            "The three earlier reports are superseded contract diagnostics because acquire() returned an undocumented dictionary at that revision; they are excluded from formal model-performance counts.",
            "Held-out mechanism, prediction, far-offset, robustness, confidence, refusal and per-world metrics remained sealed from proposal and selection state.",
            "The oracle is a deterministic synthetic acoustic ray/reflection laboratory, not elastic FWI, a field survey, geological validation or autonomous scientific discovery.",
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
    superseded = _load_superseded_diagnostics()
    revisions = {record["source_revision"] for record in records.values()}
    runtime_changes: list[str] = []
    runtime_source_equivalent = False
    if len(revisions) == 1:
        runtime_changes = _source_changes(
            calibration["source_revision"], next(iter(revisions))
        )
        runtime_source_equivalent = not runtime_changes
    report = _analyze_records(
        calibration, records, superseded, runtime_source_equivalent
    )
    report["input_task_runtime_source_changes"] = runtime_changes
    return report


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
