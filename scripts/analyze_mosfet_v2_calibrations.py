#!/usr/bin/env python3
"""Bind and analyze the three MOSFETDoping-v2 GPT-5.5 calibrations.

The inputs are single-run task calibrations.  They are not feedback-causal,
population, TCAD, fabricated-device, or autonomous-discovery evidence.  The
execution gate checks provenance, immutable artifacts, accounting, lineage and
science-axis completeness; it deliberately does not require a desired score.
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

from frontier_science.protocol import (  # noqa: E402
    compact_trajectory_snapshot,
    load_trajectory,
)
from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)
from frontier_science.runtime_migration import runtime_source_changes  # noqa: E402


TASK = "Semiconductor/MOSFETDoping"
CALIBRATION = "experiments/mosfet_doping_v2_calibration_2026-07-24.json"
REPORTS = {
    "budget_one": "experiments/gpt55_mosfet_v2_b1_2026-07-24.json",
    "normal_budget_three": "experiments/gpt55_mosfet_v2_b3_2026-07-24.json",
    "blind_budget_three": (
        "experiments/gpt55_mosfet_v2_blind_b3_2026-07-24.json"
    ),
}
# Pinned after this analyzer and its tests are committed.  Tests pass their own
# synthetic revision, so the production constant can safely be updated once.
EXPECTED_MODEL_SOURCE_REVISION = "3bebc21a5091dd1d69aef0c130511edd588cb947"
TASK_RUNTIME_SCOPE = (
    "frontier_science",
    "benchmarks/Engineering/MOSFETDoping",
    "requirements-upstream.txt",
)
EXPECTED_INSTANCE_NAMES = {
    "dev_reference_40nm",
    "heldout_short_low_v",
    "dev_thin_oxide_32nm",
    "heldout_long_hot",
    "dev_long_warm",
    "dev_cold_operation",
}
SCALAR_FIELDS = (
    "combined_score",
    "valid",
    "feasibility_rate",
    "raw_score",
    "robustness_score",
    "heldout_policy_score",
    "heldout_robustness_score",
    "heldout_feasibility_rate",
    "development_shift_feasibility_rate",
    "heldout_shift_feasibility_rate",
    "development_mean_nominal_feasible_rate",
    "heldout_mean_nominal_feasible_rate",
    "candidate_instance_call_count",
    "candidate_instance_valid_rate",
    "infrastructure_failure",
    "candidate_failure_kind",
)
SCIENCE_AXES = (
    "raw_score",
    "heldout_policy_score",
    "robustness_score",
    "heldout_robustness_score",
    "feasibility_rate",
    "heldout_feasibility_rate",
    "development_shift_feasibility_rate",
    "heldout_shift_feasibility_rate",
    "development_mean_nominal_feasible_rate",
    "heldout_mean_nominal_feasible_rate",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, TASK_RUNTIME_SCOPE, root=ROOT)


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value == value
        and abs(float(value)) != float("inf")
    )


def _scalar(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in SCALAR_FIELDS}


def _instance_axes(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    rows = metrics.get("per_instance")
    if not isinstance(rows, list) or len(rows) != 6:
        raise ValueError("selected MOSFET event lacks six instance records")
    retained = []
    for row in rows:
        shifted_scores = row.get("shifted_scores")
        shifted_hypervolumes = row.get("raw_shifted_hypervolumes")
        shift_feasibility = row.get("shift_feasibility_rates")
        shift_counts = row.get("shift_feasible_counts")
        if not (
            isinstance(shifted_scores, list) and len(shifted_scores) == 6
            and isinstance(shifted_hypervolumes, list)
            and len(shifted_hypervolumes) == 6
            and isinstance(shift_feasibility, list)
            and len(shift_feasibility) == 6
            and isinstance(shift_counts, list) and len(shift_counts) == 6
        ):
            raise ValueError("MOSFET instance lacks six sealed-shift axes")
        anchors = row.get("anchors") or {}
        if not (
            _finite_number(anchors.get("baseline_nominal_hypervolume"))
            and _finite_number(anchors.get("reference_nominal_hypervolume"))
            and len(anchors.get("baseline_shifted_hypervolumes") or []) == 6
            and len(anchors.get("reference_shifted_hypervolumes") or []) == 6
        ):
            raise ValueError("MOSFET instance lacks complete normalization anchors")
        retained.append({
            "name": str(row["name"]),
            "split": str(row["split"]),
            "valid": bool(row["valid"]),
            "nominal_score": float(row["nominal_score"]),
            "robustness_score": float(row["robustness_score"]),
            "archive_size": int(row["archive_size"]),
            "nominal_feasible_count": int(row["nominal_feasible_count"]),
            "nominal_feasibility_rate": float(
                row["nominal_feasibility_rate"]
            ),
            "pareto_front_size": int(row["pareto_front_size"]),
            "raw_nominal_hypervolume": float(
                row["raw_nominal_hypervolume"]
            ),
            "raw_shifted_hypervolumes": [
                float(value) for value in shifted_hypervolumes
            ],
            "shifted_scores": [float(value) for value in shifted_scores],
            "shift_feasible_counts": [int(value) for value in shift_counts],
            "shift_feasibility_rates": [
                float(value) for value in shift_feasibility
            ],
            "minimum_threshold_voltage_v": float(
                row["minimum_threshold_voltage_v"]
            ),
            "maximum_dibl_v": float(row["maximum_dibl_v"]),
            "minimum_on_current_ma_per_um": float(
                row["minimum_on_current_ma_per_um"]
            ),
            "minimum_log10_on_off_ratio": float(
                row["minimum_log10_on_off_ratio"]
            ),
            "maximum_subthreshold_swing_mv_dec": float(
                row["maximum_subthreshold_swing_mv_dec"]
            ),
            "maximum_random_dopant_sigma_v": float(
                row["maximum_random_dopant_sigma_v"]
            ),
            "anchors": anchors,
        })
    if {row["name"] for row in retained} != EXPECTED_INSTANCE_NAMES:
        raise ValueError("MOSFET instance identity set differs from task contract")
    if sum(row["split"] == "development" for row in retained) != 4:
        raise ValueError("MOSFET development instance count differs")
    if sum(row["split"] == "heldout" for row in retained) != 2:
        raise ValueError("MOSFET held-out instance count differs")
    if not all(row["valid"] for row in retained):
        raise ValueError("selected MOSFET artifact contains an invalid instance")
    return retained


def _selected_event(events: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [event for event in events if bool(event.get("accepted"))]
    if not accepted:
        raise ValueError("trajectory contains no accepted artifact")
    return max(accepted, key=lambda event: int(event["step"]))


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


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    dimensions = document.get("task_dimensions") or {}
    instances = document.get("instances") or []
    if not (
        document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and document.get("task") == TASK
        and dimensions.get("development_instance_count") == 4
        and dimensions.get("heldout_instance_count") == 2
        and dimensions.get("shift_count") == 6
        and dimensions.get("sobol_power") == 11
        and dimensions.get("sobol_pool_size_per_instance") == 2048
        and dimensions.get("archive_size") == 16
        and len(instances) == 6
        and {row.get("name") for row in instances} == EXPECTED_INSTANCE_NAMES
        and all(row.get("passed") is True for row in instances)
        and all(row.get("pool_size") == 2048 for row in instances)
        and document.get("committed_literals_checked") is True
        and document.get("committed_literals_match") is True
        and set(document.get("directional_checks") or []) == {
            "higher_doping_raises_threshold",
            "higher_doping_reduces_effective_mobility",
            "higher_temperature_increases_subthreshold_swing",
            "higher_temperature_increases_off_current",
            "all_finite",
        }
        and set(document.get("witness_tradeoff_checks") or []) == {
            "baseline_is_zero_valid_witness",
            "nominal_witness_reaches_nominal_anchors",
            "nominal_witness_exposes_shift_failure",
            "robust_witness_reaches_worst_shift_anchors",
            "robust_witness_trades_nominal_hypervolume",
        }
        and document.get("reference_claim", {}).get(
            "global_optimality_claimed"
        ) is False
    ):
        raise ValueError("MOSFET-v2 task calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "model_scope": document["model_scope"],
        "task_source_sha256": document["task_source_sha256"],
        "task_dimensions": dimensions,
        "reference_claim": document["reference_claim"],
        "directional_checks": document["directional_checks"],
        "witness_tradeoff_checks": document["witness_tradeoff_checks"],
        "instance_calibrations": instances,
        "limitations": document["limitations"],
    }


def _load_model(label: str, relative: str) -> dict[str, Any]:
    report_path = ROOT / relative
    document = json.loads(report_path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
    ):
        raise ValueError("model report is not trusted and passed: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one successful run: %s" % relative)
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
        and config.get("budget") == expected_budget
        and run.get("seed") == expected_seed
        and config.get("llm", {}).get("model") == "gpt-5.5"
    ):
        raise ValueError("unexpected MOSFET calibration condition")

    workdir = Path(run["workdir"]).resolve()
    try:
        relative_workdir = workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("model workdir is outside repository") from exc
    trajectory_path = workdir / "trajectory.jsonl"
    raw_events = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable snapshot differs from raw trajectory")
    if len(raw_events) != expected_budget + 1:
        raise ValueError("trajectory does not contain baseline plus every proposal")

    raw_by_step: dict[int, dict[str, Any]] = {}
    trajectory = []
    valid_proposal_axes = []
    proposal_failure_counts: dict[str, int] = {}
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            int(compact["step"]) == int(raw["step"])
            and compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
        ):
            raise ValueError("raw and compact trajectory lineage differs")
        metrics = raw.get("metrics") or {}
        step = int(raw["step"])
        raw_by_step[step] = raw
        kind = metrics.get("candidate_failure_kind")
        if step > 0 and kind:
            proposal_failure_counts[str(kind)] = (
                proposal_failure_counts.get(str(kind), 0) + 1
            )
        if step > 0 and bool(metrics.get("valid")):
            valid_proposal_axes.append({
                "step": step,
                "candidate_sha256": raw["candidate_sha256"],
                "accepted": bool(raw["accepted"]),
                "metrics": _scalar(metrics),
                "instance_axes": _instance_axes(metrics),
            })
        trajectory.append({
            "step": step,
            "accepted": bool(compact["accepted"]),
            "valid": bool(metrics.get("valid")),
            "score": float(compact["score"]),
            "best_score": float(compact["best_score"]),
            "candidate_sha256": compact["candidate_sha256"],
            "parent_sha256": compact["parent_sha256"],
            **_scalar(metrics),
        })

    selected = _selected_event(snapshot["events"])
    selected_raw = raw_by_step[int(selected["step"])]
    selected_metrics = selected_raw.get("metrics") or {}
    if _sha256(workdir / "best_program.py") != selected["candidate_sha256"]:
        raise ValueError("best program hash differs from selected candidate")
    if abs(float(selected["best_score"]) - float(run["best"])) > 1.0e-12:
        raise ValueError("selected event differs from run best")
    selected_axes = _instance_axes(selected_metrics)

    manifest_path = workdir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not (
        manifest.get("task_id") == TASK
        and manifest.get("algorithm") == "greedy_rewrite"
        and manifest.get("feedback_mode") == expected_mode
        and manifest.get("seed") == expected_seed
        and manifest.get("llm_condition_sha256")
        == config.get("llm_condition_sha256")
    ):
        raise ValueError("run manifest differs from outer report condition")

    summary = run.get("summary") or {}
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if expected_mode == "selection_blind" else "online_incumbent"
    )
    record = {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(report_path),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "run_manifest_sha256": _sha256(manifest_path),
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "llm_condition_sha256": config.get("llm_condition_sha256"),
        "model": config.get("llm", {}).get("model"),
        "server_side_seed_control": bool(
            config.get("llm", {}).get("server_side_seed_control")
        ),
        "feedback_mode": run["feedback_mode"],
        "feedback_scope": summary.get("feedback_scope"),
        "selection_policy": summary.get("selection_policy"),
        "seed": int(run["seed"]),
        "proposal_budget": int(config["budget"]),
        "oracle_calls": int(summary["oracle_calls"]),
        "budget_units": int(summary["budget_units"]),
        "llm_calls": int(summary["llm"]["calls"]),
        "provider_usage_records": int(
            summary["llm"]["provider_usage_records"]
        ),
        "total_tokens": summary["llm"].get("total_tokens"),
        "wall_seconds": float(summary["wall_seconds"]),
        "valid_rate": float(summary["valid_rate"]),
        "best_score": float(run["best"]),
        "selected_step": int(selected["step"]),
        "selected_candidate_sha256": selected["candidate_sha256"],
        "selected_metrics": _scalar(selected_metrics),
        "selected_instance_axes": selected_axes,
        "best_program": str(relative_workdir / "best_program.py"),
        "proposal_valid_count": sum(
            event["valid"] for event in trajectory[1:]
        ),
        "proposal_failure_counts": proposal_failure_counts,
        "infrastructure_failure_count": sum(
            bool(event.get("infrastructure_failure"))
            for event in trajectory[1:]
        ),
        "valid_proposal_axes": valid_proposal_axes,
        "trajectory": trajectory,
    }
    record["integrity_passed"] = bool(
        _lineage_is_valid(record)
        and record["selection_policy"] == expected_policy
        and record["budget_units"] == expected_budget + 1
        and record["llm_calls"] == expected_budget
        and int(run["evaluated"]) == record["oracle_calls"]
        and int(raw_events[-1]["oracle_calls"]) == record["oracle_calls"]
        and sum(event["accepted"] for event in trajectory[1:])
        == int(run["accepted"])
        and all(
            _finite_number(record["selected_metrics"].get(field))
            for field in SCIENCE_AXES
        )
    )
    if not record["integrity_passed"]:
        raise ValueError("MOSFET lineage or accounting gate failed")
    return record


def _accepted_transitions(record: dict[str, Any]) -> list[dict[str, Any]]:
    events = record["trajectory"]
    incumbent = events[0]
    transitions = []
    for event in events[1:]:
        if not event["accepted"]:
            continue
        deltas = {
            field: float(event[field]) - float(incumbent[field])
            for field in SCIENCE_AXES
        }
        transitions.append({
            "from_step": int(incumbent["step"]),
            "to_step": int(event["step"]),
            "from_candidate_sha256": incumbent["candidate_sha256"],
            "to_candidate_sha256": event["candidate_sha256"],
            "science_axis_deltas": deltas,
            "nominal_improvement_with_development_robustness_regression": bool(
                deltas["raw_score"] > 0.0
                and deltas["robustness_score"] < 0.0
            ),
            "nominal_improvement_with_heldout_robustness_regression": bool(
                deltas["raw_score"] > 0.0
                and deltas["heldout_robustness_score"] < 0.0
            ),
        })
        incumbent = event
    return transitions


def _selected_contrast(
    normal: dict[str, Any], blind: dict[str, Any]
) -> dict[str, Any]:
    result = {
        field: (
            float(normal["selected_metrics"][field])
            - float(blind["selected_metrics"][field])
        )
        for field in SCIENCE_AXES
    }
    normal_tokens = normal.get("total_tokens")
    blind_tokens = blind.get("total_tokens")
    result.update({
        "selection_score": normal["best_score"] - blind["best_score"],
        "proposal_valid_rate": (
            normal["proposal_valid_count"] / normal["proposal_budget"]
            - blind["proposal_valid_count"] / blind["proposal_budget"]
        ),
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
        "total_tokens": (
            normal_tokens - blind_tokens
            if _finite_number(normal_tokens) and _finite_number(blind_tokens)
            else None
        ),
        "wall_seconds": normal["wall_seconds"] - blind["wall_seconds"],
    })
    return result


def _endpoint_summary(record: dict[str, Any]) -> dict[str, Any]:
    metrics = record["selected_metrics"]
    return {
        "selected_step": record["selected_step"],
        "selected_candidate_sha256": record["selected_candidate_sha256"],
        "development_nominal_score": metrics["raw_score"],
        "heldout_nominal_score": metrics["heldout_policy_score"],
        "development_robustness_score": metrics["robustness_score"],
        "heldout_robustness_score": metrics["heldout_robustness_score"],
        "development_nominal_minus_robustness": (
            float(metrics["raw_score"])
            - float(metrics["robustness_score"])
        ),
        "heldout_nominal_minus_robustness": (
            float(metrics["heldout_policy_score"])
            - float(metrics["heldout_robustness_score"])
        ),
        "development_to_heldout_nominal_gap": (
            float(metrics["raw_score"])
            - float(metrics["heldout_policy_score"])
        ),
        "development_to_heldout_robustness_gap": (
            float(metrics["robustness_score"])
            - float(metrics["heldout_robustness_score"])
        ),
        "development_shift_feasibility_rate": metrics[
            "development_shift_feasibility_rate"
        ],
        "heldout_shift_feasibility_rate": metrics[
            "heldout_shift_feasibility_rate"
        ],
        "development_mean_nominal_feasible_rate": metrics[
            "development_mean_nominal_feasible_rate"
        ],
        "heldout_mean_nominal_feasible_rate": metrics[
            "heldout_mean_nominal_feasible_rate"
        ],
        "proposal_valid_count": record["proposal_valid_count"],
        "proposal_failure_counts": record["proposal_failure_counts"],
        "oracle_calls": record["oracle_calls"],
        "total_tokens": record["total_tokens"],
        "wall_seconds": record["wall_seconds"],
    }


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    runtime_source_equivalent: bool = True,
    expected_model_source_revision: str = EXPECTED_MODEL_SOURCE_REVISION,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    conditions = {
        record["llm_condition_sha256"] for record in records.values()
    }
    contrast = _selected_contrast(normal, blind)
    endpoints = {
        label: _endpoint_summary(record) for label, record in records.items()
    }
    transitions = {
        label: _accepted_transitions(record)
        for label, record in records.items()
    }

    execution_passed = bool(
        runtime_source_equivalent
        and revisions == {expected_model_source_revision}
        and len(scopes) == 1
        and len(conditions) == 1
        and None not in conditions
        and all(record["integrity_passed"] for record in records.values())
        and all(record["model"] == "gpt-5.5" for record in records.values())
        and all(
            not record["server_side_seed_control"]
            for record in records.values()
        )
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["seed"] == 0
        and normal["seed"] == blind["seed"] == 1
        and one["feedback_mode"] == normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "MOSFET_SINGLE_RUN_CALIBRATION_NOT_CAUSAL_POPULATION_TCAD_"
            "FABRICATED_DEVICE_OR_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_model_source_revision": (
            next(iter(revisions)) if len(revisions) == 1 else None
        ),
        "expected_model_source_revision": expected_model_source_revision,
        "input_task_runtime_source_equivalent": bool(
            runtime_source_equivalent
        ),
        "input_source_scope_equivalent": len(scopes) == 1,
        "input_llm_condition_equivalent": len(conditions) == 1,
        "task_calibration": calibration,
        "records": records,
        "condition_endpoints": endpoints,
        "accepted_transition_audit": transitions,
        "normal_minus_blind_selected_contrast": contrast,
        "descriptive_findings": {
            "budget_one_improves_visible_baseline": (
                one["best_score"] > float(one["trajectory"][0]["best_score"])
            ),
            "normal_budget_three_improves_visible_baseline": (
                normal["best_score"]
                > float(normal["trajectory"][0]["best_score"])
            ),
            "blind_budget_three_improves_visible_baseline": (
                blind["best_score"]
                > float(blind["trajectory"][0]["best_score"])
            ),
            "normal_selected_nominal_exceeds_robustness": (
                float(normal["selected_metrics"]["raw_score"])
                > float(normal["selected_metrics"]["robustness_score"])
            ),
            "blind_selected_nominal_exceeds_robustness": (
                float(blind["selected_metrics"]["raw_score"])
                > float(blind["selected_metrics"]["robustness_score"])
            ),
            "normal_contains_nominal_robustness_reversal": any(
                row[
                    "nominal_improvement_with_development_robustness_regression"
                ] or row[
                    "nominal_improvement_with_heldout_robustness_regression"
                ]
                for row in transitions["normal_budget_three"]
            ),
            "normal_and_blind_are_oracle_call_matched": (
                contrast["oracle_calls"] == 0
            ),
            "normal_and_blind_are_token_matched": (
                contrast["total_tokens"] == 0
            ),
            "feedback_necessity_identified": False,
        },
        "limitations": [
            "Each condition has one run; no confidence interval, population, leaderboard or scaling-law estimate is supported.",
            "The Azure endpoint exposes no server-side generation seed, so equal local seed labels do not pair model randomness.",
            "Normal and selection-blind are descriptive single runs; equal oracle calls cannot identify a feedback effect because token usage, wall time and generation randomness differ.",
            "Budget one uses a different local seed label and is an independent calibration, not a prefix of budget three.",
            "Selection-blind accepted flags denote offline best-of-batch updates only; every proposal parent is the frozen baseline and no evaluated score enters later prompts.",
            "Held-out devices, process and operating shifts, robustness and per-instance axes were sealed from proposal and selection state.",
            "The fixed repository devices and shifts require server-held procedural conditions before leakage-resistant population claims.",
            "The Sobol references are strong reproducible normalization witnesses, not global Pareto-optimality certificates.",
            "The compact model omits self-consistent multidimensional drift-diffusion, quantum corrections, detailed junctions, leakage, traps and implant or anneal chemistry.",
            "The selected artifacts are compact-model doping-profile optimizers, not commercial TCAD validation, fabricated-device results, new semiconductor mechanisms or autonomous scientific discovery.",
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
    revisions = {record["source_revision"] for record in records.values()}
    runtime_changes: list[str] = []
    runtime_source_equivalent = False
    if len(revisions) == 1:
        runtime_changes = _source_changes(
            calibration["source_revision"], next(iter(revisions))
        )
        runtime_source_equivalent = not runtime_changes
    report = _analyze_records(
        calibration,
        records,
        runtime_source_equivalent,
        expected_model_source_revision=EXPECTED_MODEL_SOURCE_REVISION,
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
