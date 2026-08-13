#!/usr/bin/env python3
"""Build portable evidence from OceanCurrentInversion-v2 calibrations.

The model conditions are single-run task calibrations.  This analyzer binds
the raw trajectories, checks online and frozen-parent lineage, distinguishes
protocol failures from valid zero-score discovery attempts, and reports
in-library mechanism coverage separately from correct refusal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.protocol import compact_trajectory_snapshot, load_trajectory  # noqa: E402
from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402
from sle.runtime_migration import runtime_source_changes  # noqa: E402


CALIBRATION = "experiments/ocean_current_v2_calibration_2026-07-22.json"
REPORTS = {
    "budget_one": "experiments/gpt55_ocean_v2_b1_2026-07-22.json",
    "normal_budget_three": "experiments/gpt55_ocean_v2_b3_2026-07-22.json",
    "blind_budget_three": "experiments/gpt55_ocean_v2_blind_b3_2026-07-22.json",
}
TASK = "Oceanography/OceanCurrentInversion"
SOURCE_SCOPE = (
    "sle", "scripts", "tests", "benchmarks",
    "requirements-upstream.txt",
)
FIELDS = (
    "combined_score", "mechanism_score", "robustness_score",
    "heldout_mechanism_score", "development_support_f1",
    "heldout_support_f1", "development_velocity_mode_score",
    "heldout_velocity_mode_score", "development_vorticity_score",
    "heldout_vorticity_score", "development_field_prediction_score",
    "heldout_field_prediction_score", "development_field_extrapolation_score",
    "heldout_field_extrapolation_score",
    "development_trajectory_prediction_score",
    "heldout_trajectory_prediction_score",
    "development_trajectory_extrapolation_score",
    "heldout_trajectory_extrapolation_score",
    "development_misspecified_trajectory_score",
    "heldout_misspecified_trajectory_score",
    "development_confidence_calibration_score",
    "heldout_confidence_calibration_score",
    "development_false_discovery_rate", "heldout_false_discovery_rate",
    "development_correct_refusal_rate", "heldout_correct_refusal_rate",
    "mean_experiment_calls", "mean_experiment_budget_units", "valid",
    "error_message",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, SOURCE_SCOPE, root=ROOT)


def _scalar(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in FIELDS}


def _discovery_summary(worlds: list[dict[str, Any]]) -> dict[str, Any]:
    in_library = [world for world in worlds if world.get("kind") == "in_library"]
    unsupported = [world for world in worlds if world.get("kind") != "in_library"]
    claimed = [world for world in in_library if not bool(world.get("abstained"))]
    return {
        "world_count": len(worlds),
        "in_library_world_count": len(in_library),
        "in_library_claim_count": len(claimed),
        "in_library_claim_coverage": (
            len(claimed) / len(in_library) if in_library else None
        ),
        "mean_in_library_mechanism_score": (
            sum(float(world["mechanism_score"]) for world in in_library)
            / len(in_library) if in_library else None
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


def _failure_kind(error: Any) -> str | None:
    if not error:
        return None
    message = str(error)
    if "initial drifters must lie inside the public interior" in message:
        return "invalid_experiment_geometry"
    if "could not convert string to float" in message:
        return "callback_schema_misread"
    return "other_candidate_protocol_error"


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if document.get("trusted_evidence") is not True or document.get("passed") is not True:
        raise ValueError("ocean task calibration is not trusted and passed")
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("ocean task calibration source was dirty")
    dimensions = document.get("task_dimensions") or {}
    baseline = document.get("always_abstain_baseline") or {}
    classical = document.get("truth_blind_classical_fit") or {}
    ranks = document.get("trajectory_identifiability_checks") or []
    misspecified = document.get("misspecified_resolvability_checks") or []
    noise_checks = document.get("noise_label_blind_checks") or []
    if dimensions != {
        "public_mode_count": 30,
        "development_world_count": 6,
        "heldout_world_count": 5,
        "drifter_budget_units": 12,
    }:
        raise ValueError("unexpected ocean task dimensions")
    if baseline.get("combined_score") != 0.0 or baseline.get("robustness_score") != 0.0:
        raise ValueError("ocean always-abstain anchor is not zero")
    if not 0.35 <= float(classical.get("combined_score", -1.0)) <= 0.85:
        raise ValueError("ocean classical development score is outside its gate")
    if not 0.20 <= float(classical.get("robustness_score", -1.0)) <= 0.75:
        raise ValueError("ocean classical held-out score is outside its gate")
    if float(classical["combined_score"]) <= float(classical["robustness_score"]) + 0.15:
        raise ValueError("ocean classical development/held-out gap is absent")
    if len(ranks) != 7 or not all(row.get("passed") for row in ranks):
        raise ValueError("ocean trajectory identifiability checks did not pass")
    if len(misspecified) != 2 or not all(row.get("passed") for row in misspecified):
        raise ValueError("ocean model-mismatch resolvability checks did not pass")
    if len(noise_checks) != 2 or not all(row.get("passed") for row in noise_checks):
        raise ValueError("ocean noise-label blindness checks did not pass")
    if (
        float(classical["development_false_discovery_rate"]) != 0.0
        or float(classical["heldout_false_discovery_rate"]) != 0.0
    ):
        raise ValueError("ocean classical fit has a false discovery")
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
        "maximum_trajectory_condition_number": max(
            float(row["condition_number"]) for row in ranks
        ),
        "minimum_misspecified_nonlinear_reduced_chi2": min(
            float(row["best_nonlinear_trajectory_fit"]["reduced_chi2"])
            for row in misspecified
        ),
    }


def _selected_event(events: list[dict[str, Any]], best: float) -> dict[str, Any]:
    matches = [
        event for event in events if event.get("accepted")
        and abs(float(event["score"]) - float(best)) <= 1e-12
    ]
    if not matches:
        raise ValueError("no accepted event matches ocean run best")
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
        raise ValueError("ocean model report is not trusted and passed: %s" % relative)
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("ocean model report source was dirty: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one successful ocean run: %s" % relative)
    run = runs[0]
    if run.get("task") != TASK or run.get("algorithm") != "greedy_rewrite":
        raise ValueError("unexpected ocean task or algorithm")
    expected_mode = "selection_blind" if label == "blind_budget_three" else "normal"
    if run.get("feedback_mode") != expected_mode:
        raise ValueError("unexpected ocean feedback mode")
    trajectory_path = Path(run["workdir"]) / "trajectory.jsonl"
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("ocean compact snapshot differs from raw trajectory")
    raw_events = load_trajectory(trajectory_path)
    if len(raw_events) != len(snapshot["events"]):
        raise ValueError("ocean raw and compact trajectory lengths differ")
    trajectory = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if int(compact["step"]) != int(raw["step"]):
            raise ValueError("ocean raw and compact trajectory steps differ")
        metrics = raw.get("metrics") or {}
        trajectory.append({
            "step": int(compact["step"]),
            "accepted": bool(compact["accepted"]),
            "candidate_sha256": compact["candidate_sha256"],
            "parent_sha256": compact["parent_sha256"],
            **_scalar(metrics),
            "failure_kind": _failure_kind(metrics.get("error_message")),
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
        raise ValueError("ocean proposal lineage is broken")
    if label == "blind_budget_three" and record["selection_policy"] != "offline_best_of_open_loop_batch":
        raise ValueError("ocean blind run lacks offline-selection semantics")
    if label != "blind_budget_three" and record["selection_policy"] != "online_incumbent":
        raise ValueError("ocean normal run lacks online-incumbent semantics")
    if int(run["evaluated"]) != record["oracle_calls"]:
        raise ValueError("ocean oracle-call count mismatch")
    if sum(event["accepted"] for event in trajectory[1:]) != int(run["accepted"]):
        raise ValueError("ocean accepted count mismatch")
    return record


def _failure_counts(record: dict[str, Any]) -> dict[str, int]:
    return dict(sorted(Counter(
        event["failure_kind"] for event in record["trajectory"][1:]
        if event.get("failure_kind")
    ).items()))


def _analyze_records(calibration: dict[str, Any],
                     records: dict[str, dict[str, Any]],
                     source_equivalent: bool = True) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    normal_valid = [
        event for event in normal["trajectory"][1:] if bool(event.get("valid"))
    ]
    blind_valid = [
        event for event in blind["trajectory"][1:] if bool(event.get("valid"))
    ]
    valid_zero = normal_valid[0] if len(normal_valid) == 1 else None
    classical_summary = calibration["classical_discovery_summary"]
    valid_summary = valid_zero["discovery_summary"] if valid_zero else {}
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
        and all(not event["accepted"] for record in records.values()
                for event in record["trajectory"][1:])
        and one["trajectory"][1]["failure_kind"] == "invalid_experiment_geometry"
        and len(normal_valid) == 1
        and valid_zero is not None
        and valid_zero["combined_score"] == 0.0
        and valid_zero["mean_experiment_calls"] == 2.0
        and valid_zero["mean_experiment_budget_units"] == 12.0
        and valid_summary.get("in_library_claim_coverage") == 0.0
        and valid_summary.get("mean_in_library_mechanism_score") == 0.0
        and valid_summary.get("unsupported_correct_refusal_rate") == 1.0
        and valid_summary.get("unsupported_false_discovery_rate") == 0.0
        and _failure_counts(normal) == {"callback_schema_misread": 2}
        and not blind_valid
        and _failure_counts(blind) == {"callback_schema_misread": 3}
        and classical_summary["in_library_claim_coverage"] == 1.0
        and classical_summary["mean_in_library_mechanism_score"] > 0.5
        and classical_summary["unsupported_correct_refusal_rate"] == 1.0
        and classical_summary["unsupported_false_discovery_rate"] == 0.0
        and calibration["classical_metrics"]["combined_score"] > 0.70
        and calibration["classical_metrics"]["robustness_score"] > 0.40
        and normal["total_tokens"] != blind["total_tokens"]
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": "OCEAN_CURRENT_CALIBRATION_NOT_CAUSAL_POPULATION_FIELD_OR_AUTONOMOUS_DISCOVERY_EVIDENCE",
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
        "protocol_failure_counts": {
            label: _failure_counts(record) for label, record in records.items()
        },
        "normal_valid_zero_score_proposal": valid_zero,
        "normal_minus_blind_diagnostic": {
            "best_score": normal["best_score"] - blind["best_score"],
            "valid_proposal_rate": len(normal_valid) / 3.0 - len(blind_valid) / 3.0,
            "total_tokens": normal["total_tokens"] - blind["total_tokens"],
            "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
        },
        "science_vectors": {
            "classical_truth_blind": {
                "optimization_O": calibration["classical_metrics"]["combined_score"],
                "fidelity_F": calibration["classical_metrics"]["heldout_trajectory_prediction_score"],
                "mechanism_M": classical_summary["mean_in_library_mechanism_score"],
                "validity_V": calibration["classical_metrics"]["robustness_score"],
                "refusal_R": 1.0 - calibration["classical_metrics"]["development_false_discovery_rate"],
                "in_library_discovery_coverage": classical_summary["in_library_claim_coverage"],
            },
            "gpt55_only_valid_nonbaseline_proposal": {
                "optimization_O": valid_zero["combined_score"] if valid_zero else None,
                "fidelity_F": valid_zero["heldout_trajectory_prediction_score"] if valid_zero else None,
                "mechanism_M": valid_summary.get("mean_in_library_mechanism_score"),
                "validity_V": valid_zero["robustness_score"] if valid_zero else None,
                "refusal_R": (
                    1.0 - valid_zero["development_false_discovery_rate"]
                    if valid_zero else None
                ),
                "in_library_discovery_coverage": valid_summary.get("in_library_claim_coverage"),
            },
        },
        "limitations": [
            "Each condition has one run; no confidence interval, model ranking, scaling law or causal feedback estimate is supported.",
            "Normal and selection-blind share a local seed identifier, but the Azure endpoint exposes no server-side model seed, so generation randomness is not paired.",
            "The conditions are oracle-call matched but not token- or context-matched; normal used %d more tokens." % (normal["total_tokens"] - blind["total_tokens"]),
            "Both conditions selected the always-abstain baseline, so the zero normal-minus-blind score contrast contains no feedback-effect information.",
            "The aggregate baseline mechanism fields include credit for correct refusal; in-library mechanism recovery and discovery coverage are therefore reported separately and are both zero for the only valid model proposal.",
            "Held-out mechanism, prediction, false-discovery and per-world metrics remained sealed from proposal and selection state.",
            "The oracle is a controlled synthetic ocean-current simulator; it is not field-oceanography validation or autonomous scientific discovery.",
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
