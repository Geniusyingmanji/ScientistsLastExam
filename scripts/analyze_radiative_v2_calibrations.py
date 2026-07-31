#!/usr/bin/env python3
"""Build portable evidence from RadiativeTransferFit-v2 calibrations.

The three model conditions are single-run task calibrations.  This analyzer
binds each report to its raw trajectory, validates online and frozen-parent
lineage, and separates legal execution, supported-world discovery coverage,
mechanism recovery, radiance prediction, held-out transfer and refusal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.protocol import compact_trajectory_snapshot, load_trajectory  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402
from frontier_science.runtime_migration import runtime_source_changes  # noqa: E402


CALIBRATION = "experiments/radiative_transfer_v2_calibration_2026-07-22.json"
REPORTS = {
    "budget_one": "experiments/gpt55_radiative_v2_b1_2026-07-22.json",
    "normal_budget_three": "experiments/gpt55_radiative_v2_b3_2026-07-22.json",
    "blind_budget_three": "experiments/gpt55_radiative_v2_blind_b3_2026-07-22.json",
}
TASK = "AtmosphericScience/RadiativeTransferFit"
SOURCE_SCOPE = (
    "frontier_science", "scripts", "tests", "benchmarks",
    "requirements-upstream.txt",
)
FIELDS = (
    "combined_score", "mechanism_score", "robustness_score",
    "development_supported_mechanism_score",
    "heldout_supported_mechanism_score",
    "development_discovery_coverage", "heldout_discovery_coverage",
    "development_support_f1", "heldout_support_f1",
    "development_parameter_score", "heldout_parameter_score",
    "development_profile_score", "heldout_profile_score",
    "development_optical_depth_score", "heldout_optical_depth_score",
    "development_radiance_prediction_score",
    "heldout_radiance_prediction_score",
    "development_radiance_view_shift_score",
    "heldout_radiance_view_shift_score",
    "development_misspecified_radiance_score",
    "heldout_misspecified_radiance_score",
    "development_confidence_calibration_score",
    "heldout_confidence_calibration_score",
    "development_false_discovery_rate", "heldout_false_discovery_rate",
    "development_correct_refusal_rate", "heldout_correct_refusal_rate",
    "mean_experiment_calls", "mean_experiment_budget_units", "valid",
    "error_message", "candidate_failure_kind",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, SOURCE_SCOPE, root=ROOT)


def _scalar(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in FIELDS}


def _discovery_summary(worlds: list[dict[str, Any]]) -> dict[str, Any]:
    supported = [world for world in worlds if world.get("kind") == "in_library"]
    unsupported = [world for world in worlds if world.get("kind") != "in_library"]
    claims = [world for world in supported if not bool(world.get("abstained"))]
    return {
        "world_count": len(worlds),
        "supported_world_count": len(supported),
        "supported_claim_count": len(claims),
        "supported_discovery_coverage": (
            len(claims) / len(supported) if supported else None
        ),
        "mean_supported_mechanism_score": (
            sum(float(world["mechanism_score"]) for world in supported)
            / len(supported) if supported else None
        ),
        "mean_supported_radiance_prediction_score": (
            sum(float(world["radiance_prediction_score"]) for world in supported)
            / len(supported) if supported else None
        ),
        "unsupported_world_count": len(unsupported),
        "unsupported_correct_refusal_rate": (
            sum(bool(world.get("correct_refusal")) for world in unsupported)
            / len(unsupported) if unsupported else None
        ),
        "unsupported_false_discovery_rate": (
            sum(bool(world.get("false_discovery")) for world in unsupported)
            / len(unsupported) if unsupported else None
        ),
    }


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if document.get("trusted_evidence") is not True or document.get("passed") is not True:
        raise ValueError("radiative task calibration is not trusted and passed")
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("radiative task calibration source was dirty")
    dimensions = document.get("task_dimensions") or {}
    baseline = document.get("always_abstain_baseline") or {}
    classical = document.get("truth_blind_classical_fit") or {}
    ranks = document.get("sounding_identifiability_checks") or []
    misspecified = document.get("misspecified_resolvability_checks") or []
    noise_checks = document.get("noise_label_blind_checks") or []
    physics = document.get("physics_checks") or {}
    if dimensions != {
        "layer_count": 16,
        "channel_count": 24,
        "parameter_count": 5,
        "development_world_count": 6,
        "heldout_world_count": 5,
        "measurement_budget_units": 18,
    }:
        raise ValueError("unexpected radiative task dimensions")
    if baseline.get("combined_score") != 0.0 or baseline.get("robustness_score") != 0.0:
        raise ValueError("radiative always-abstain anchor is not zero")
    if not 0.30 <= float(classical.get("combined_score", -1.0)) <= 0.80:
        raise ValueError("radiative classical development score is outside its gate")
    if not 0.20 <= float(classical.get("robustness_score", -1.0)) <= 0.75:
        raise ValueError("radiative classical held-out score is outside its gate")
    if len(ranks) != 7 or not all(row.get("passed") for row in ranks):
        raise ValueError("radiative identifiability checks did not pass")
    if len(misspecified) != 2 or not all(row.get("passed") for row in misspecified):
        raise ValueError("radiative model-mismatch checks did not pass")
    if len(noise_checks) != 2 or not all(row.get("passed") for row in noise_checks):
        raise ValueError("radiative noise-label-blind checks did not pass")
    if not all(
        isinstance(value, dict) and value.get("passed") is True
        for value in (
            physics.get("independent_public_equation"),
            physics.get("isothermal_recurrence"),
        )
    ):
        raise ValueError("radiative independent physics checks did not pass")
    if (
        float(classical.get("development_false_discovery_rate", -1.0)) != 0.0
        or float(classical.get("heldout_false_discovery_rate", -1.0)) != 0.0
    ):
        raise ValueError("radiative classical fit has a false discovery")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "dimensions": dimensions,
        "always_abstain_metrics": _scalar(baseline),
        "classical_metrics": _scalar(classical),
        "classical_discovery_summary": _discovery_summary(
            classical.get("per_world") or []
        ),
        "maximum_identifiability_condition_number": max(
            float(row["condition_number"]) for row in ranks
        ),
        "minimum_misspecified_reduced_chi2": min(
            float(row["reduced_chi2"]) for row in misspecified
        ),
    }


def _selected_event(events: list[dict[str, Any]], best: float) -> dict[str, Any]:
    matches = [
        event for event in events if event.get("accepted")
        and abs(float(event["score"]) - float(best)) <= 1e-12
    ]
    if not matches:
        raise ValueError("no accepted event matches radiative run best")
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
    if document.get("trusted_evidence") is not True or document.get("passed") is not True:
        raise ValueError("radiative model report is not trusted and passed: %s" % relative)
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("radiative model report source was dirty: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one successful radiative run: %s" % relative)
    run = runs[0]
    if run.get("task") != TASK or run.get("algorithm") != "greedy_rewrite":
        raise ValueError("unexpected radiative task or algorithm")
    expected_mode = "selection_blind" if label == "blind_budget_three" else "normal"
    if run.get("feedback_mode") != expected_mode:
        raise ValueError("unexpected radiative feedback mode")
    if document.get("config", {}).get("llm", {}).get("model") != "gpt-5.5":
        raise ValueError("unexpected radiative calibration model")
    trajectory_path = Path(run["workdir"]) / "trajectory.jsonl"
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("radiative compact snapshot differs from raw trajectory")
    raw_events = load_trajectory(trajectory_path)
    if len(raw_events) != len(snapshot["events"]):
        raise ValueError("radiative raw and compact trajectory lengths differ")
    trajectory = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if int(compact["step"]) != int(raw["step"]):
            raise ValueError("radiative raw and compact trajectory steps differ")
        metrics = raw.get("metrics") or {}
        trajectory.append({
            "step": int(compact["step"]),
            "accepted": bool(compact["accepted"]),
            "candidate_sha256": compact["candidate_sha256"],
            "parent_sha256": compact["parent_sha256"],
            **_scalar(metrics),
            "discovery_summary": (
                _discovery_summary(metrics.get("per_world") or [])
                if metrics.get("valid") else None
            ),
        })
    selected = _selected_event(snapshot["events"], float(run["best"]))
    selected_raw = next(
        row for row in raw_events if int(row["step"]) == int(selected["step"])
    )
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
        "proposal_budget": int(document["config"]["budget"]),
        "server_side_seed_control": bool(
            document["config"]["llm"].get("server_side_seed_control")
        ),
        "oracle_calls": int(run["summary"]["oracle_calls"]),
        "total_tokens": int(run["summary"]["llm"]["total_tokens"]),
        "best_score": float(run["best"]),
        "selected_step": int(selected["step"]),
        "selected_candidate_sha256": selected["candidate_sha256"],
        "selected_metrics": _scalar(selected_raw.get("metrics") or {}),
        "selected_discovery_summary": _discovery_summary(
            (selected_raw.get("metrics") or {}).get("per_world") or []
        ),
        "trajectory": trajectory,
    }
    if not _lineage_is_valid(record):
        raise ValueError("radiative proposal lineage is broken")
    if label == "blind_budget_three" and record["selection_policy"] != "offline_best_of_open_loop_batch":
        raise ValueError("radiative blind run lacks offline-selection semantics")
    if label != "blind_budget_three" and record["selection_policy"] != "online_incumbent":
        raise ValueError("radiative normal run lacks online-incumbent semantics")
    if int(run["evaluated"]) != record["oracle_calls"]:
        raise ValueError("radiative oracle-call count mismatch")
    if sum(event["accepted"] for event in trajectory[1:]) != int(run["accepted"]):
        raise ValueError("radiative accepted count mismatch")
    return record


def _all_zero_discovery(events: list[dict[str, Any]]) -> bool:
    for event in events:
        summary = event.get("discovery_summary") or {}
        if (
            not bool(event.get("valid"))
            or float(event.get("combined_score", -1.0)) != 0.0
            or summary.get("supported_discovery_coverage") != 0.0
            or summary.get("mean_supported_mechanism_score") != 0.0
            or summary.get("unsupported_correct_refusal_rate") != 1.0
            or summary.get("unsupported_false_discovery_rate") != 0.0
        ):
            return False
    return True


def _proposal_usage(record: dict[str, Any]) -> dict[str, Any]:
    events = record["trajectory"][1:]
    budgets = [float(event["mean_experiment_budget_units"]) for event in events]
    calls = [float(event["mean_experiment_calls"]) for event in events]
    return {
        "proposal_count": len(events),
        "valid_proposal_count": sum(bool(event["valid"]) for event in events),
        "zero_experiment_proposal_count": sum(value == 0.0 for value in budgets),
        "full_budget_proposal_count": sum(value == 18.0 for value in budgets),
        "mean_experiment_calls_by_proposal": calls,
        "mean_experiment_budget_units_by_proposal": budgets,
    }


def _analyze_records(calibration: dict[str, Any],
                     records: dict[str, dict[str, Any]],
                     source_equivalent: bool = True) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    proposals = {
        label: record["trajectory"][1:] for label, record in records.items()
    }
    classical_summary = calibration["classical_discovery_summary"]
    all_model_proposals = [event for events in proposals.values() for event in events]
    execution_passed = bool(
        source_equivalent
        and len(revisions) == 1
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["oracle_calls"] == 2
        and normal["oracle_calls"] == blind["oracle_calls"] == 4
        and one["feedback_mode"] == normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and all(not record["server_side_seed_control"] for record in records.values())
        and all(_lineage_is_valid(record) for record in records.values())
        and all(record["best_score"] == 0.0 for record in records.values())
        and all(record["selected_step"] == 0 for record in records.values())
        and all(not event["accepted"] for event in all_model_proposals)
        and len(all_model_proposals) == 7
        and _all_zero_discovery(all_model_proposals)
        and all(event.get("error_message") is None for event in all_model_proposals)
        and all(event.get("candidate_failure_kind") is None for event in all_model_proposals)
        and _proposal_usage(one)["full_budget_proposal_count"] == 1
        and _proposal_usage(normal)["full_budget_proposal_count"] == 2
        and _proposal_usage(normal)["zero_experiment_proposal_count"] == 1
        and _proposal_usage(blind)["full_budget_proposal_count"] == 2
        and _proposal_usage(blind)["zero_experiment_proposal_count"] == 1
        and classical_summary["supported_discovery_coverage"] == 1.0
        and classical_summary["mean_supported_mechanism_score"] > 0.50
        and classical_summary["mean_supported_radiance_prediction_score"] > 0.80
        and classical_summary["unsupported_correct_refusal_rate"] == 1.0
        and classical_summary["unsupported_false_discovery_rate"] == 0.0
        and normal["total_tokens"] != blind["total_tokens"]
    )
    model_reference = all_model_proposals[0] if all_model_proposals else {}
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": "RADIATIVE_TRANSFER_CALIBRATION_NOT_CAUSAL_POPULATION_SATELLITE_OR_AUTONOMOUS_DISCOVERY_EVIDENCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_task_source_revision": calibration["source_revision"],
        "input_model_source_revision": (
            next(iter(revisions)) if len(revisions) == 1 else None
        ),
        "input_source_scope_equivalent": bool(source_equivalent),
        "task_calibration": calibration,
        "records": records,
        "proposal_usage": {
            label: _proposal_usage(record) for label, record in records.items()
        },
        "normal_minus_blind_diagnostic": {
            "best_score": normal["best_score"] - blind["best_score"],
            "supported_discovery_coverage": 0.0,
            "mean_supported_mechanism_score": 0.0,
            "total_tokens": normal["total_tokens"] - blind["total_tokens"],
            "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
        },
        "science_vectors": {
            "classical_truth_blind": {
                "optimization_O": calibration["classical_metrics"]["combined_score"],
                "fidelity_F": calibration["classical_metrics"]["heldout_radiance_prediction_score"],
                "mechanism_M": classical_summary["mean_supported_mechanism_score"],
                "validity_V": calibration["classical_metrics"]["robustness_score"],
                "refusal_R": 1.0 - float(
                    calibration["classical_metrics"]["development_false_discovery_rate"]
                ),
                "supported_discovery_coverage": classical_summary[
                    "supported_discovery_coverage"
                ],
            },
            "all_gpt55_nonbaseline_proposals": {
                "proposal_count": len(all_model_proposals),
                "optimization_O": model_reference.get("combined_score"),
                "fidelity_F": model_reference.get("heldout_radiance_prediction_score"),
                "mechanism_M": 0.0,
                "validity_V": model_reference.get("robustness_score"),
                "refusal_R": 1.0,
                "supported_discovery_coverage": 0.0,
            },
        },
        "limitations": [
            "Each condition has one run; no confidence interval, model ranking, scaling law or causal feedback estimate is supported.",
            "Normal and selection-blind share a local seed identifier, but the Azure endpoint exposes no server-side model seed, so generation randomness is not paired.",
            "The conditions are oracle-call matched but not token- or context-matched; normal used %d more tokens." % (normal["total_tokens"] - blind["total_tokens"]),
            "No proposal improved the baseline, so normal never changed its incumbent; the zero normal-minus-blind contrast contains no feedback-effect information.",
            "All seven nonbaseline proposals were protocol-valid, yet every proposal refused every supported atmosphere. Correct unsupported-world refusal and zero false discovery therefore do not establish scientific discovery.",
            "Held-out mechanism, radiance prediction, view-shift, confidence, refusal and per-world metrics remained sealed from proposal and selection state.",
            "The oracle is a controlled low-dimensional, non-scattering thermal-emission emulator; it is not line-by-line, satellite or autonomous scientific discovery evidence.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def analyze() -> dict[str, Any]:
    calibration = _load_calibration(CALIBRATION)
    records = {
        label: _load(label, relative) for label, relative in REPORTS.items()
    }
    revisions = {record["source_revision"] for record in records.values()}
    source_changes: list[str] = []
    source_equivalent = False
    if len(revisions) == 1:
        source_changes = _source_changes(
            calibration["source_revision"], next(iter(revisions))
        )
        source_equivalent = not source_changes
    report = _analyze_records(calibration, records, source_equivalent)
    report["input_source_scope_changes"] = source_changes
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze()
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
