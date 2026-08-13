#!/usr/bin/env python3
"""Bind and analyze EnergyBalanceModel-v2 GPT-5.5 calibrations.

The three model conditions are single-run task calibrations, not population or
causal evidence.  This analyzer verifies report/raw-trajectory hashes and
proposal lineage, separates parameter mechanism from response prediction and
model-inadequacy refusal, and runs the selected open-loop program on post-hoc
procedural worlds.  Those worlds were chosen after the model runs and are not
preregistered hidden-test evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
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
from sle.runtime_migration import runtime_source_changes  # noqa: E402
from sle.secure_eval import CandidateProxy  # noqa: E402


CALIBRATION = "experiments/climate_response_v2_calibration_2026-07-22.json"
REPORTS = {
    "budget_one": "experiments/gpt55_climate_v2_b1_2026-07-22.json",
    "normal_budget_three": "experiments/gpt55_climate_v2_b3_2026-07-22.json",
    "blind_budget_three": "experiments/gpt55_climate_v2_blind_b3_2026-07-22.json",
}
TASK = "ClimateScience/EnergyBalanceModel"
TASK_RUNTIME_SCOPE = (
    "sle",
    "benchmarks/EarthScience/EnergyBalanceModel",
    "requirements-upstream.txt",
)
PROBE_SPECS = (
    *tuple({
        "name": "posthoc_supported_%d" % (index + 1),
        "seed": 6101 + index,
        "kind": "in_library",
    } for index in range(6)),
    {"name": "posthoc_null_1", "seed": 6111, "kind": "null"},
    {"name": "posthoc_null_2", "seed": 6112, "kind": "null"},
    {
        "name": "posthoc_feedback_drift_1",
        "seed": 6121,
        "kind": "feedback_drift",
    },
    {
        "name": "posthoc_feedback_drift_2",
        "seed": 6122,
        "kind": "feedback_drift",
    },
    {
        "name": "posthoc_three_layer_1",
        "seed": 6131,
        "kind": "three_layer",
    },
    {
        "name": "posthoc_three_layer_2",
        "seed": 6132,
        "kind": "three_layer",
    },
)
FIELDS = (
    "combined_score", "valid", "feasibility_rate", "raw_score",
    "development_mechanism_score", "robustness_score",
    "development_validation_gap", "heldout_policy_score",
    "heldout_robustness_score", "development_prediction_score",
    "heldout_prediction_score", "development_supported_claim_coverage",
    "heldout_supported_claim_coverage",
    "development_false_discovery_rate", "heldout_false_discovery_rate",
    "development_unsupported_refusal_rate",
    "heldout_unsupported_refusal_rate", "development_confidence_score",
    "heldout_confidence_score", "development_mean_budget_used",
    "heldout_mean_budget_used", "development_mean_experiment_calls",
    "heldout_mean_experiment_calls", "heldout_feasibility_rate",
    "candidate_world_call_count", "candidate_world_valid_rate",
    "error_message",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, TASK_RUNTIME_SCOPE, root=ROOT)


def _scalar(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in FIELDS}


def _load_oracle():
    path = ROOT / "benchmarks/EarthScience/EnergyBalanceModel/verification/evaluator.py"
    spec = importlib.util.spec_from_file_location(
        "climate_v2_analysis_oracle", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load EnergyBalanceModel-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mean(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    return sum(values) / len(values) if values else None


def _world_summary(worlds: list[dict[str, Any]]) -> dict[str, Any]:
    supported = [row for row in worlds if row.get("kind") == "in_library"]
    unsupported = [row for row in worlds if row.get("kind") != "in_library"]
    false_discoveries = [row for row in unsupported if row.get("false_discovery")]
    by_kind = {}
    for kind in sorted({str(row.get("kind")) for row in worlds}):
        rows = [row for row in worlds if row.get("kind") == kind]
        claimed_rows = [
            row for row in rows if bool(row.get("claimed_public_model"))
        ]
        by_kind[kind] = {
            "world_count": len(rows),
            "valid_rate": sum(bool(row.get("valid")) for row in rows) / len(rows),
            "claim_rate": sum(bool(row.get("claimed_public_model")) for row in rows)
            / len(rows),
            "correct_refusal_rate": sum(bool(row.get("correct_refusal")) for row in rows)
            / len(rows),
            "false_discovery_rate": sum(bool(row.get("false_discovery")) for row in rows)
            / len(rows),
            "mean_mechanism_quality": _mean(rows, "mechanism_quality"),
            "mean_nominal_prediction_quality": _mean(
                rows, "nominal_prediction_quality"
            ),
            "mean_claimed_model_shift_fit": _mean(
                claimed_rows, "claimed_model_shift_fit"
            ),
            "mean_confidence": _mean(rows, "confidence"),
        }

    parameter_error_rows = [
        row["parameter_absolute_errors"] for row in supported
        if row.get("parameter_absolute_errors") is not None
    ]
    maximum_parameter_errors = None
    if parameter_error_rows:
        maximum_parameter_errors = [
            max(float(row[column]) for row in parameter_error_rows)
            for column in range(len(parameter_error_rows[0]))
        ]
    return {
        "world_count": len(worlds),
        "valid_world_count": sum(bool(row.get("valid")) for row in worlds),
        "supported_world_count": len(supported),
        "supported_claim_coverage": (
            sum(bool(row.get("supported_claim")) for row in supported)
            / len(supported) if supported else None
        ),
        "mean_supported_mechanism_quality": _mean(
            supported, "mechanism_quality"
        ),
        "minimum_supported_mechanism_quality": (
            min(float(row["mechanism_quality"]) for row in supported)
            if supported else None
        ),
        "mean_supported_parameter_quality": _mean(
            supported, "parameter_quality"
        ),
        "mean_supported_nominal_prediction_quality": _mean(
            supported, "nominal_prediction_quality"
        ),
        "mean_supported_claimed_model_shift_fit": _mean(
            supported, "claimed_model_shift_fit"
        ),
        "maximum_supported_parameter_absolute_errors": maximum_parameter_errors,
        "unsupported_world_count": len(unsupported),
        "unsupported_correct_refusal_rate": (
            sum(bool(row.get("correct_refusal")) for row in unsupported)
            / len(unsupported) if unsupported else None
        ),
        "unsupported_false_discovery_rate": (
            sum(bool(row.get("false_discovery")) for row in unsupported)
            / len(unsupported) if unsupported else None
        ),
        "false_discovery_count": len(false_discoveries),
        "mean_false_discovery_confidence": _mean(
            false_discoveries, "confidence"
        ),
        "mean_false_discovery_claimed_nominal_fit": _mean(
            false_discoveries, "claimed_model_nominal_fit"
        ),
        "mean_false_discovery_claimed_shift_fit": _mean(
            false_discoveries, "claimed_model_shift_fit"
        ),
        "mean_budget_used": _mean(worlds, "budget_used"),
        "mean_experiment_calls": _mean(worlds, "experiment_calls"),
        "by_kind": by_kind,
    }


def _split_world_summaries(metrics: dict[str, Any]) -> dict[str, Any] | None:
    worlds = metrics.get("per_world") or []
    if not worlds:
        return None
    return {
        "all": _world_summary(worlds),
        "development": _world_summary([
            row for row in worlds if row.get("split") == "development"
        ]),
        "heldout": _world_summary([
            row for row in worlds if row.get("split") == "heldout"
        ]),
    }


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if not (
        document.get("trusted_evidence") is True
        and document.get("passed") is True
        and document.get("execution_passed") is True
        and provenance.get("source_tree_dirty") is False
    ):
        raise ValueError("climate task calibration is not trusted and passed")
    dimensions = document.get("task_dimensions") or {}
    expected_dimensions = {
        "parameter_count": 5,
        "development_world_count": 6,
        "heldout_world_count": 5,
        "experiment_budget_units": 8,
        "maximum_experiment_years": 160,
        "surface_noise_std_k": 0.06,
        "toa_noise_std_w_m2": 0.14,
    }
    baseline = document.get("always_abstain_baseline") or {}
    classical = document.get("truth_blind_long_multiscale_fit") or {}
    short = document.get("underinformative_short_fit") or {}
    reference = document.get("exact_reference") or {}
    ranks = document.get("forcing_identifiability_checks") or []
    mismatch = document.get("misspecified_resolvability_checks") or []
    physics = document.get("physics_checks") or {}
    if dimensions != expected_dimensions:
        raise ValueError("unexpected climate task dimensions")
    if not (
        baseline.get("combined_score") == 0.0
        and baseline.get("heldout_policy_score") == 0.0
        and 0.70 <= float(classical.get("combined_score", -1.0)) <= 0.90
        and 0.80 <= float(classical.get("heldout_policy_score", -1.0)) <= 0.99
        and float(short.get("combined_score", 2.0)) <= 0.10
        and float(short.get("heldout_policy_score", 2.0)) <= 0.10
        and reference.get("combined_score") == 1.0
        and reference.get("heldout_policy_score") == 1.0
        and classical.get("development_unsupported_refusal_rate") == 1.0
        and classical.get("heldout_unsupported_refusal_rate") == 1.0
        and classical.get("development_false_discovery_rate") == 0.0
        and classical.get("heldout_false_discovery_rate") == 0.0
        and len(ranks) == 7 and all(row.get("passed") for row in ranks)
        and len(mismatch) == 4 and all(row.get("passed") for row in mismatch)
        and all(
            len(rows) == 4 and all(row.get("passed") for row in rows)
            for rows in physics.values()
        )
        and (document.get("determinism_and_budget_check") or {}).get("passed")
        is True
    ):
        raise ValueError("climate scientific calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "dimensions": dimensions,
        "always_abstain_metrics": _scalar(baseline),
        "classical_metrics": _scalar(classical),
        "classical_world_summary": _split_world_summaries(classical),
        "short_design_metrics": _scalar(short),
        "short_design_world_summary": _split_world_summaries(short),
        "exact_reference_metrics": _scalar(reference),
        "maximum_identifiability_condition_number": max(
            float(row["condition_number"]) for row in ranks
        ),
        "minimum_misspecification_expected_reduced_chi2": min(
            float(row["expected_noisy_reduced_chi2"]) for row in mismatch
        ),
    }


def _selected_event(events: list[dict[str, Any]], best: float) -> dict[str, Any]:
    matches = [
        event for event in events if event.get("accepted")
        and abs(float(event["score"]) - float(best)) <= 1e-12
    ]
    if not matches:
        raise ValueError("no accepted event matches climate run best")
    return min(matches, key=lambda event: int(event["step"]))


def _lineage_is_valid(record: dict[str, Any]) -> bool:
    events = record["trajectory"]
    baseline_hash = events[0]["candidate_sha256"]
    if record["feedback_mode"] == "selection_blind":
        return all(
            event["parent_sha256"] == baseline_hash for event in events[1:]
        )
    parent = baseline_hash
    for event in events[1:]:
        if event["parent_sha256"] != parent:
            return False
        if event["accepted"]:
            parent = event["candidate_sha256"]
    return True


def _load(label: str, relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if not (
        document.get("trusted_evidence") is True
        and document.get("passed") is True
        and document.get("execution_passed") is True
        and provenance.get("source_tree_dirty") is False
    ):
        raise ValueError("climate model report is not trusted and passed: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one successful climate run: %s" % relative)
    run = runs[0]
    expected_mode = "selection_blind" if label == "blind_budget_three" else "normal"
    expected_budget = 1 if label == "budget_one" else 3
    expected_seed = 0 if label == "budget_one" else 1
    config = document.get("config") or {}
    llm = config.get("llm") or {}
    if not (
        run.get("task") == TASK
        and run.get("algorithm") == "greedy_rewrite"
        and run.get("feedback_mode") == expected_mode
        and run.get("seed") == expected_seed
        and config.get("budget") == expected_budget
        and llm.get("model") == "gpt-5.5"
        and llm.get("wire") == "responses"
        and llm.get("server_side_seed_control") is False
    ):
        raise ValueError("unexpected climate calibration condition")

    trajectory_path = Path(run["workdir"]) / "trajectory.jsonl"
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("climate compact snapshot differs from raw trajectory")
    raw_events = load_trajectory(trajectory_path)
    if len(raw_events) != len(snapshot["events"]):
        raise ValueError("climate raw and compact trajectory lengths differ")
    trajectory = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            int(compact["step"]) == int(raw["step"])
            and compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
        ):
            raise ValueError("climate raw and compact trajectory lineage differs")
        metrics = raw.get("metrics") or {}
        trajectory.append({
            "step": int(compact["step"]),
            "accepted": bool(compact["accepted"]),
            "candidate_sha256": compact["candidate_sha256"],
            "parent_sha256": compact["parent_sha256"],
            **_scalar(metrics),
            "world_summary": (
                _split_world_summaries(metrics) if metrics.get("valid") else None
            ),
        })

    selected = _selected_event(snapshot["events"], float(run["best"]))
    selected_raw = next(
        row for row in raw_events if int(row["step"]) == int(selected["step"])
    )
    candidate_path = Path(run["workdir"]) / "best_program.py"
    candidate_hash = _sha256(candidate_path)
    if candidate_hash != selected["candidate_sha256"]:
        raise ValueError("selected climate candidate differs from best_program.py")
    record = {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(path),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "source_revision": provenance["git_revision"],
        "feedback_mode": run["feedback_mode"],
        "feedback_scope": run["summary"].get("feedback_scope"),
        "selection_policy": run["summary"].get("selection_policy"),
        "seed": int(run["seed"]),
        "proposal_budget": int(config["budget"]),
        "server_side_seed_control": False,
        "oracle_calls": int(run["summary"]["oracle_calls"]),
        "total_tokens": int(run["summary"]["llm"]["total_tokens"]),
        "best_score": float(run["best"]),
        "selected_step": int(selected["step"]),
        "selected_candidate_sha256": candidate_hash,
        "selected_candidate_path": str(candidate_path),
        "selected_candidate_line_count": len(
            candidate_path.read_text(encoding="utf-8").splitlines()
        ),
        "selected_metrics": _scalar(selected_raw.get("metrics") or {}),
        "selected_world_summary": _split_world_summaries(
            selected_raw.get("metrics") or {}
        ),
        "trajectory": trajectory,
    }
    if not _lineage_is_valid(record):
        raise ValueError("climate proposal lineage is broken")
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if label == "blind_budget_three" else "online_incumbent"
    )
    if record["selection_policy"] != expected_policy:
        raise ValueError("climate selection policy metadata is wrong")
    if int(run["evaluated"]) != record["oracle_calls"]:
        raise ValueError("climate oracle-call count mismatch")
    if sum(event["accepted"] for event in trajectory[1:]) != int(run["accepted"]):
        raise ValueError("climate accepted count mismatch")
    return record


def _run_posthoc_probes(record: dict[str, Any]) -> list[dict[str, Any]]:
    oracle = _load_oracle()
    candidate = Path(record["selected_candidate_path"])
    if _sha256(candidate) != record["selected_candidate_sha256"]:
        raise ValueError("post-hoc climate candidate hash changed")
    results = []
    for index, probe in enumerate(PROBE_SPECS):
        with CandidateProxy(
            candidate, "identify_climate_response", timeout_s=180
        ) as proxy:
            row = oracle._evaluate_world(
                proxy,
                (int(probe["seed"]), str(probe["kind"])),
                "posthoc",
                index,
            )
        results.append({
            **probe,
            "candidate_sha256": record["selected_candidate_sha256"],
            **row,
        })
    return results


def _invalid_proposal_count(record: dict[str, Any]) -> int:
    return sum(not bool(event.get("valid")) for event in record["trajectory"][1:])


def _failure_kinds(record: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for event in record["trajectory"][1:]:
        message = event.get("error_message")
        if message:
            result[str(message)] = result.get(str(message), 0) + 1
    return result


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    probes: list[dict[str, Any]],
    source_equivalent: bool = True,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    model_revisions = {record["source_revision"] for record in records.values()}
    all_proposals = [
        event for record in records.values() for event in record["trajectory"][1:]
    ]
    blind_selected = blind["selected_metrics"]
    blind_worlds = blind["selected_world_summary"] or {}
    fixed_all = blind_worlds.get("all") or {}
    fixed_dev = blind_worlds.get("development") or {}
    fixed_held = blind_worlds.get("heldout") or {}
    probe_summary = _world_summary(probes)
    probe_by_kind = probe_summary["by_kind"]

    execution_passed = bool(
        source_equivalent
        and len(model_revisions) == 1
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["oracle_calls"] == 2
        and normal["oracle_calls"] == blind["oracle_calls"] == 4
        and one["feedback_mode"] == normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and all(not record["server_side_seed_control"] for record in records.values())
        and all(_lineage_is_valid(record) for record in records.values())
        and one["selected_step"] == normal["selected_step"] == 0
        and blind["selected_step"] == 3
        and one["best_score"] == normal["best_score"] == 0.0
        and 0.60 < blind["best_score"] < 0.65
        and _invalid_proposal_count(one) == 1
        and _invalid_proposal_count(normal) == 3
        and _invalid_proposal_count(blind) == 1
        and _failure_kinds(one) == {
            "candidate invalid: invalid_return_artifact": 1
        }
        and _failure_kinds(normal) == {
            "candidate invalid: invalid_return_artifact": 3
        }
        and _failure_kinds(blind) == {
            "candidate invalid: invalid_return_artifact": 1
        }
        and len(all_proposals) == 7
        and blind_selected["valid"] == 1.0
        and blind_selected["development_supported_claim_coverage"] == 1.0
        and blind_selected["heldout_supported_claim_coverage"] == 1.0
        and blind_selected["development_unsupported_refusal_rate"] == 0.5
        and blind_selected["heldout_unsupported_refusal_rate"] == 0.5
        and blind_selected["development_false_discovery_rate"] == 0.2
        and blind_selected["heldout_false_discovery_rate"] == 0.25
        and blind_selected["development_prediction_score"] > 0.95
        and blind_selected["heldout_prediction_score"] > 0.95
        and blind_selected["development_mean_budget_used"] == 8.0
        and blind_selected["heldout_mean_budget_used"] == 8.0
        and float(fixed_dev["mean_supported_mechanism_quality"]) > 0.80
        and float(fixed_held["mean_supported_mechanism_quality"]) < 0.70
        and float(fixed_all["mean_false_discovery_confidence"]) > 0.90
        and calibration["classical_metrics"]["combined_score"]
        > blind_selected["combined_score"]
        and calibration["classical_metrics"]["heldout_policy_score"]
        > blind_selected["heldout_policy_score"] + 0.60
        and calibration["classical_metrics"][
            "development_unsupported_refusal_rate"
        ] == 1.0
        and calibration["classical_metrics"][
            "heldout_unsupported_refusal_rate"
        ] == 1.0
        and len(probes) == len(PROBE_SPECS) == 12
        and probe_summary["valid_world_count"] == 12
        and probe_summary["supported_claim_coverage"] == 1.0
        and 0.30 < float(probe_summary["mean_supported_mechanism_quality"]) < 0.45
        and float(probe_summary[
            "mean_supported_nominal_prediction_quality"
        ]) > 0.98
        and probe_summary["unsupported_correct_refusal_rate"] == 1.0 / 3.0
        and probe_summary["unsupported_false_discovery_rate"] == 2.0 / 3.0
        and probe_by_kind["null"]["correct_refusal_rate"] == 1.0
        and probe_by_kind["feedback_drift"]["correct_refusal_rate"] == 0.0
        and probe_by_kind["three_layer"]["correct_refusal_rate"] == 0.0
        and float(probe_by_kind["feedback_drift"]["mean_confidence"]) > 0.90
        and float(probe_by_kind["three_layer"]["mean_confidence"]) > 0.90
        and float(probe_by_kind["three_layer"][
            "mean_nominal_prediction_quality"
        ]) > 0.99
        and all(row.get("budget_used") == 8 for row in probes)
        and all(row.get("experiment_calls") == 3 for row in probes)
        and normal["total_tokens"] != blind["total_tokens"]
    )
    normal_minus_blind = {
        field: float(normal["selected_metrics"][field])
        - float(blind_selected[field])
        for field in (
            "combined_score", "robustness_score", "heldout_policy_score",
            "heldout_robustness_score", "development_prediction_score",
            "heldout_prediction_score",
            "development_supported_claim_coverage",
            "heldout_supported_claim_coverage",
            "development_unsupported_refusal_rate",
            "heldout_unsupported_refusal_rate",
            "development_false_discovery_rate",
            "heldout_false_discovery_rate",
        )
    }
    normal_minus_blind.update({
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
    })
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "CLIMATE_RESPONSE_CALIBRATION_NOT_CAUSAL_POPULATION_EARTH_SYSTEM_"
            "OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_task_source_revision": calibration["source_revision"],
        "input_model_source_revision": (
            next(iter(model_revisions)) if len(model_revisions) == 1 else None
        ),
        "input_source_scope_equivalent": bool(source_equivalent),
        "task_calibration": calibration,
        "records": records,
        "observed_model_proposal_pattern": {
            "proposal_count": len(all_proposals),
            "valid_proposal_count": sum(
                bool(event.get("valid")) for event in all_proposals
            ),
            "invalid_return_artifact_count": sum(
                event.get("error_message")
                == "candidate invalid: invalid_return_artifact"
                for event in all_proposals
            ),
            "budget_one_selected_baseline": one["selected_step"] == 0,
            "normal_budget_three_selected_baseline": normal["selected_step"] == 0,
            "blind_budget_three_selected_step": blind["selected_step"],
            "blind_selected_fixed_world_summary": blind_worlds,
        },
        "normal_minus_blind_diagnostic": normal_minus_blind,
        "prediction_mechanism_refusal_separation": {
            "classical_truth_blind": {
                "development_mechanism": calibration["classical_metrics"][
                    "combined_score"
                ],
                "heldout_mechanism": calibration["classical_metrics"][
                    "heldout_policy_score"
                ],
                "heldout_prediction": calibration["classical_metrics"][
                    "heldout_prediction_score"
                ],
                "development_false_discovery_rate": calibration[
                    "classical_metrics"
                ]["development_false_discovery_rate"],
                "heldout_false_discovery_rate": calibration[
                    "classical_metrics"
                ]["heldout_false_discovery_rate"],
            },
            "underinformative_short_classical": {
                "development_mechanism": calibration["short_design_metrics"][
                    "combined_score"
                ],
                "heldout_mechanism": calibration["short_design_metrics"][
                    "heldout_policy_score"
                ],
                "heldout_prediction": calibration["short_design_metrics"][
                    "heldout_prediction_score"
                ],
                "development_false_discovery_rate": calibration[
                    "short_design_metrics"
                ]["development_false_discovery_rate"],
                "heldout_false_discovery_rate": calibration[
                    "short_design_metrics"
                ]["heldout_false_discovery_rate"],
            },
            "gpt55_blind_selected": {
                "development_mechanism": blind_selected["combined_score"],
                "heldout_mechanism": blind_selected["heldout_policy_score"],
                "heldout_prediction": blind_selected["heldout_prediction_score"],
                "development_false_discovery_rate": blind_selected[
                    "development_false_discovery_rate"
                ],
                "heldout_false_discovery_rate": blind_selected[
                    "heldout_false_discovery_rate"
                ],
                "fixed_world_summary": blind_worlds,
            },
            "gpt55_blind_selected_posthoc": probe_summary,
        },
        "posthoc_procedural_probe_protocol": {
            "preregistered": False,
            "selected_after_model_runs": True,
            "world_count": len(PROBE_SPECS),
            "supported_world_count": 6,
            "null_world_count": 2,
            "feedback_drift_world_count": 2,
            "three_layer_world_count": 2,
            "candidate_process_isolation": (
                "fresh secure sandbox for every procedural world"
            ),
            "search_feedback": False,
            "same_oracle_family": True,
        },
        "posthoc_procedural_probe_results": probes,
        "posthoc_procedural_probe_summary": probe_summary,
        "interpretation": {
            "model_calibration": (
                "The only nonzero GPT-5.5 proposal recovered useful supported-world "
                "parameters but did not reliably detect state-dependent feedback or a "
                "third ocean reservoir."
            ),
            "science_axis_result": (
                "Near-unit response prediction coexists with weak parameter mechanism "
                "recovery and confident false model claims; predictive adequacy is not "
                "mechanism discovery."
            ),
            "experiment_design_result": (
                "The truth-blind long multiscale design substantially outperforms the "
                "underinformative short design and the selected model program while "
                "maintaining zero false discovery on the fixed worlds."
            ),
            "feedback_result": (
                "The one-run open-loop best exceeds the one-run normal best, but the "
                "conditions are not generation-seed or token matched and support no "
                "causal feedback conclusion."
            ),
        },
        "limitations": [
            "Each condition has one run; no confidence interval, model ranking, scaling law or causal feedback estimate is supported.",
            "Normal and selection-blind share a local seed label, but the Azure endpoint exposes no server-side model seed, so generation randomness is not paired.",
            "The budget-three conditions are oracle-call matched but not token- or context-matched; normal used %d fewer tokens." % (blind["total_tokens"] - normal["total_tokens"]),
            "Selection-blind uses offline best-of-batch selection while normal uses online incumbent selection; the normal run never accepted a proposal and all three proposals were invalid return artifacts.",
            "The procedural worlds were selected after the model runs and use the same synthetic oracle family; they diagnose transfer but are not preregistered hidden or independent GCM/observational validation.",
            "The evaluator deliberately strengthens model mismatch so it is resolvable within 160 benchmark years and uses independent annual noise rather than correlated internal climate variability.",
            "Response prediction, forcing shift, held-out mechanism, confidence, refusal and per-world metrics remained sealed from proposal and selection state.",
            "This global-mean synthetic emulator does not estimate Earth's climate sensitivity, validate a climate model, or establish autonomous scientific discovery.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def analyze() -> dict[str, Any]:
    calibration = _load_calibration(CALIBRATION)
    records = {
        label: _load(label, relative) for label, relative in REPORTS.items()
    }
    model_revisions = {record["source_revision"] for record in records.values()}
    source_changes: list[str] = []
    source_equivalent = False
    if len(model_revisions) == 1:
        source_changes = _source_changes(
            calibration["source_revision"], next(iter(model_revisions))
        )
        source_equivalent = not source_changes
    probes = _run_posthoc_probes(records["blind_budget_three"])
    report = _analyze_records(
        calibration, records, probes, source_equivalent
    )
    report["input_source_scope_changes"] = source_changes
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
