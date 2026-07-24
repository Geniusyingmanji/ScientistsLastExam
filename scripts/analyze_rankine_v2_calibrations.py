#!/usr/bin/env python3
"""Bind and analyze the three RankineCycleOpt-v2 GPT-5.5 calibrations.

The conditions are preregistered single-run task calibrations, not population,
feedback-causal, plant-validation, or autonomous-discovery evidence.  Integrity
and lineage determine whether this analysis executes successfully; no model
score or desired scientific conclusion is an execution gate.
"""

from __future__ import annotations

import argparse
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

from frontier_science.protocol import (  # noqa: E402
    compact_trajectory_snapshot,
    load_trajectory,
)
from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


TASK = "Thermodynamics/RankineCycleOpt"
CALIBRATION = "experiments/rankine_v2_calibration_2026-07-24.json"
REPORTS = {
    "budget_one": "experiments/gpt55_rankine_v2_b1_2026-07-24.json",
    "normal_budget_three": "experiments/gpt55_rankine_v2_b3_2026-07-24.json",
    "blind_budget_three": (
        "experiments/gpt55_rankine_v2_blind_b3_2026-07-24.json"
    ),
}
# Pinned after the preregistered runner source is committed and before the
# derived report is generated.  Unit tests inject a synthetic expected revision.
EXPECTED_MODEL_SOURCE_REVISION = (
    "4b019e5699f03e1c025a5537ca4ffb56b56672cd"
)
TASK_RUNTIME_SCOPE = (
    "frontier_science",
    "benchmarks/Thermodynamics/RankineCycleOpt",
    "requirements-upstream.txt",
)
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
    "development_mean_front_efficiency",
    "heldout_mean_front_efficiency",
    "development_mean_front_specific_net_work_kj_kg",
    "heldout_mean_front_specific_net_work_kj_kg",
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
    "development_mean_front_efficiency",
    "heldout_mean_front_efficiency",
    "development_mean_front_specific_net_work_kj_kg",
    "heldout_mean_front_specific_net_work_kj_kg",
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
    return {field: metrics.get(field) for field in SCALAR_FIELDS}


def _finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    return value == value and abs(float(value)) != float("inf")


def _instance_axes(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    rows = metrics.get("per_instance")
    if not isinstance(rows, list) or len(rows) != 6:
        raise ValueError("selected Rankine event lacks six instance records")
    retained = []
    for row in rows:
        shifted_scores = row.get("shifted_scores")
        shifted_hypervolumes = row.get("raw_shifted_hypervolumes")
        shift_feasibility = row.get("shift_feasibility_rates")
        if not (
            isinstance(shifted_scores, list) and len(shifted_scores) == 5
            and isinstance(shifted_hypervolumes, list)
            and len(shifted_hypervolumes) == 5
            and isinstance(shift_feasibility, list)
            and len(shift_feasibility) == 5
        ):
            raise ValueError("Rankine instance lacks five sealed-shift axes")
        retained.append({
            "name": str(row["name"]),
            "split": str(row["split"]),
            "valid": bool(row["valid"]),
            "nominal_score": float(row["score"]),
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
            "shift_feasibility_rates": [
                float(value) for value in shift_feasibility
            ],
            "mean_front_efficiency": float(row["mean_front_efficiency"]),
            "maximum_front_efficiency": float(
                row["maximum_front_efficiency"]
            ),
            "mean_front_specific_net_work_kj_kg": float(
                row["mean_front_specific_net_work_kj_kg"]
            ),
            "maximum_front_specific_net_work_kj_kg": float(
                row["maximum_front_specific_net_work_kj_kg"]
            ),
            "minimum_front_hp_exit_quality": float(
                row["minimum_front_hp_exit_quality"]
            ),
            "minimum_front_lp_exit_quality": float(
                row["minimum_front_lp_exit_quality"]
            ),
            "maximum_front_energy_balance_residual_kj_kg": float(
                row["maximum_front_energy_balance_residual_kj_kg"]
            ),
        })
    expected = {
        "dev_temperate_reference",
        "dev_warm_sink",
        "dev_cold_sink",
        "dev_aged_turbomachinery",
        "heldout_hot_humid_sink",
        "heldout_derated_retrofit",
    }
    if {row["name"] for row in retained} != expected:
        raise ValueError("Rankine instance identity set differs from task contract")
    if not all(row["valid"] for row in retained):
        raise ValueError("selected Rankine artifact contains an invalid instance")
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
    independent = document.get("independent_iapws_1_5_4_check") or {}
    instances = document.get("instances") or []
    dimensions = document.get("task_dimensions") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and document.get("task") == TASK
        and dimensions.get("development_instance_count") == 4
        and dimensions.get("heldout_instance_count") == 2
        and dimensions.get("shift_count") == 5
        and dimensions.get("sobol_power") == 11
        and dimensions.get("sobol_pool_size_per_instance") == 2048
        and dimensions.get("archive_size") == 16
        and len(instances) == 6
        and all(row.get("passed") is True for row in instances)
        and document.get("committed_literals_checked") is True
        and document.get("committed_literals_match") is True
        and independent.get("performed") is True
        and independent.get("required") is True
        and independent.get("observed_version") == "1.5.4"
        and independent.get("state_count") == 32
        and independent.get("passed") is True
        and document.get("reference_claim", {}).get(
            "global_optimality_claimed"
        ) is False
    ):
        raise ValueError("Rankine-v2 task calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "if97_release_sha256": document["if97_release_sha256"],
        "task_source_sha256": document["task_source_sha256"],
        "task_dimensions": dimensions,
        "reference_method": document["reference_method"],
        "reference_claim": document["reference_claim"],
        "independent_iapws_1_5_4_check": {
            key: value for key, value in independent.items()
            if key not in {"region_checks", "saturation_checks"}
        },
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
        raise ValueError("unexpected Rankine calibration condition")

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

    raw_by_step = {}
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
        raise ValueError("Rankine lineage or accounting gate failed")
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

    # Crucially, scientific outcomes are absent from this gate.  A complete,
    # lineage-valid zero-score calibration is valid evidence of failure.
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
            "RANKINE_SINGLE_RUN_CALIBRATION_NOT_CAUSAL_POPULATION_PLANT_"
            "VALIDATION_OR_DISCOVERY_EVIDENCE"
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
            "budget_one_one_step_near_nominal_ceiling": (
                float(one["selected_metrics"]["raw_score"]) >= 0.95
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
            "Normal and selection-blind are descriptive single runs; even equal oracle calls cannot identify a feedback effect when tokens, wall time and generation randomness differ.",
            "Budget one uses a different local seed label and is an independent calibration, not a prefix of budget three.",
            "Selection-blind accepted flags denote offline best-of-batch updates only; every proposal parent is the frozen baseline and no evaluated score enters later prompts.",
            "Held-out regimes, physical shifts, efficiency/work diagnostics and per-instance axes were sealed from proposal and selection state.",
            "The fixed repository regimes require server-held procedural conditions before leakage-resistant population claims.",
            "The Sobol references are strong normalization witnesses, not global Pareto-optimality certificates.",
            "The equilibrium IF97 Regions 1/2/4 cycle omits regeneration, combustion, capital cost, emissions, transient stress, water chemistry and detailed off-design component maps.",
            "The selected artifact is a simulator-specific cycle-design policy, not plant validation, a novel thermodynamic mechanism or autonomous scientific discovery.",
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
    runtime_changes = []
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
