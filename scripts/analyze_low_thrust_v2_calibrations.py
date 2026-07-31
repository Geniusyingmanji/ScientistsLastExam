#!/usr/bin/env python3
"""Build portable, non-causal evidence from LowThrustTransfer-v2 calibrations.

The model conditions are single-run task calibrations.  This analyzer binds the
three batch reports to their raw trajectories, verifies online and frozen-parent
lineage, and keeps numerical fidelity, nominal utility, terminal feasibility,
phase, held-out transfer, and execution robustness as separate axes.
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


CALIBRATION = "experiments/low_thrust_v2_calibration_2026-07-22.json"
REPORTS = {
    "budget_one": "experiments/gpt55_low_thrust_v2_b1_2026-07-22.json",
    "normal_budget_three": "experiments/gpt55_low_thrust_v2_b3_2026-07-22.json",
    "blind_budget_three": "experiments/gpt55_low_thrust_v2_blind_b3_2026-07-22.json",
}
TASK = "Astrodynamics/LowThrustTransfer"
SOURCE_SCOPE = (
    "frontier_science", "scripts", "tests", "benchmarks",
    "requirements-upstream.txt",
)
FIELDS = (
    "combined_score", "valid", "feasibility_rate", "raw_score",
    "development_score", "robustness_score", "development_validation_gap",
    "heldout_policy_score", "heldout_robustness_score",
    "heldout_artifact_valid_rate",
    "development_mission_feasibility_rate",
    "heldout_mission_feasibility_rate",
    "development_shift_feasibility_rate",
    "heldout_shift_feasibility_rate",
    "mean_development_terminal_accuracy",
    "mean_heldout_terminal_accuracy",
    "mean_development_phase_score", "mean_heldout_phase_score",
    "mean_development_delta_v_m_s", "mean_heldout_delta_v_m_s",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, SOURCE_SCOPE, root=ROOT)


def _scalar(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in FIELDS}


def _mission_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    rows = metrics.get("per_instance") or []
    shifted = [shift for row in rows for shift in (row.get("shifted") or [])]
    terminal_errors = [
        float(row["nominal"]["maximum_scaled_terminal_error"])
        for row in rows
        if isinstance(row.get("nominal"), dict)
        and row["nominal"].get("maximum_scaled_terminal_error") is not None
    ]
    return {
        "instance_count": len(rows),
        "valid_instance_count": sum(bool(row.get("valid")) for row in rows),
        "development_instance_count": sum(
            row.get("split") == "development" for row in rows
        ),
        "heldout_instance_count": sum(row.get("split") == "heldout" for row in rows),
        "nominal_feasible_count": sum(
            bool((row.get("nominal") or {}).get("mission_feasible")) for row in rows
        ),
        "shifted_case_count": len(shifted),
        "shifted_feasible_count": sum(
            bool(row.get("mission_feasible")) for row in shifted
        ),
        "minimum_maximum_scaled_terminal_error": (
            min(terminal_errors) if terminal_errors else None
        ),
        "maximum_maximum_scaled_terminal_error": (
            max(terminal_errors) if terminal_errors else None
        ),
    }


def _integration_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mission_count": len(rows),
        "production_vs_refined_max_scaled_error": max(
            float(row["production_vs_refined_max_scaled_error"]) for row in rows
        ),
        "refined_vs_cartesian_max_scaled_error": max(
            float(row["refined_vs_cartesian_max_scaled_error"]) for row in rows
        ),
        "refined_vs_cartesian_max_abs_mass_error_kg": max(
            abs(float(row["refined_vs_cartesian_mass_error_kg"])) for row in rows
        ),
        "production_vs_refined_max_abs_phase_error_rad": max(
            abs(float(row["production_vs_refined_phase_error_rad"])) for row in rows
        ),
        "refined_vs_cartesian_max_abs_phase_error_rad": max(
            abs(float(row["refined_vs_cartesian_phase_error_rad"])) for row in rows
        ),
    }


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if (
        document.get("trusted_evidence") is not True
        or document.get("passed") is not True
        or document.get("execution_passed") is not True
    ):
        raise ValueError("low-thrust task calibration is not trusted and passed")
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("low-thrust task calibration source was dirty")
    dimensions = document.get("dimensions") or {}
    if dimensions != {
        "public_instance_count": 6,
        "development_instance_count": 4,
        "heldout_instance_count": 2,
        "guidance_segment_count": 4,
        "coefficient_count": 28,
        "shift_count": 3,
    }:
        raise ValueError("unexpected low-thrust task dimensions")
    gauss_newton = document.get("public_input_only_gauss_newton_metrics") or {}
    reachability = document.get("target_construction_reachability_metrics") or {}
    coast = document.get("zero_thrust_baseline_metrics") or {}
    integration = document.get(
        "production_refinement_and_independent_cartesian_checks"
    ) or []
    continuous = document.get("continuous_thrust_bound_checks") or []
    invalid = document.get("invalid_artifact_checks") or []
    point_mass = document.get("point_mass_zero_thrust_invariant_checks") or []
    integration_summary = _integration_summary(integration)
    if not (
        coast.get("combined_score") == 0.0
        and coast.get("valid") == 1
        and coast.get("feasibility_rate") == 0.0
        and float(gauss_newton.get("combined_score", -1.0)) > 0.70
        and float(gauss_newton.get("heldout_policy_score", -1.0)) > 0.70
        and float(gauss_newton.get("robustness_score", -1.0)) > 0.65
        and float(gauss_newton.get("heldout_robustness_score", -1.0)) > 0.65
        and gauss_newton.get("development_mission_feasibility_rate") == 1.0
        and gauss_newton.get("heldout_mission_feasibility_rate") == 1.0
        and abs(
            float(gauss_newton.get("heldout_shift_feasibility_rate", -1.0))
            - 5.0 / 6.0
        ) <= 1.0e-12
        and float(reachability.get("combined_score", -1.0)) > 0.70
        and reachability.get("development_shift_feasibility_rate") == 1.0
        and reachability.get("heldout_shift_feasibility_rate") == 1.0
        and len(integration) == 6 and all(row.get("passed") for row in integration)
        and integration_summary["production_vs_refined_max_scaled_error"] < 0.05
        and integration_summary["refined_vs_cartesian_max_scaled_error"] < 0.003
        and integration_summary["refined_vs_cartesian_max_abs_mass_error_kg"] < 0.00025
        and len(continuous) == 12 and all(row.get("passed") for row in continuous)
        and len(invalid) == 4 and all(row.get("passed") for row in invalid)
        and len(point_mass) == 6 and all(row.get("passed") for row in point_mass)
    ):
        raise ValueError("low-thrust numerical or scientific calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "dimensions": dimensions,
        "zero_thrust_metrics": _scalar(coast),
        "public_gauss_newton_metrics": _scalar(gauss_newton),
        "reachability_metrics": _scalar(reachability),
        "integration_consistency": integration_summary,
        "continuous_thrust_check_count": len(continuous),
        "invalid_artifact_check_count": len(invalid),
        "point_mass_invariant_check_count": len(point_mass),
    }


def _selected_event(events: list[dict[str, Any]], best: float) -> dict[str, Any]:
    matches = [
        event for event in events
        if event.get("accepted")
        and abs(float(event["score"]) - float(best)) <= 1.0e-12
    ]
    if not matches:
        raise ValueError("no accepted event matches low-thrust run best")
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
    if (
        document.get("trusted_evidence") is not True
        or document.get("passed") is not True
        or document.get("execution_passed") is not True
    ):
        raise ValueError("low-thrust model report is not trusted and passed: %s" % relative)
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("low-thrust model report source was dirty: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one successful low-thrust run: %s" % relative)
    run = runs[0]
    if run.get("task") != TASK or run.get("algorithm") != "greedy_rewrite":
        raise ValueError("unexpected low-thrust task or algorithm")
    expected_mode = "selection_blind" if label == "blind_budget_three" else "normal"
    expected_budget = 1 if label == "budget_one" else 3
    expected_seed = 0 if label == "budget_one" else 1
    if (
        run.get("feedback_mode") != expected_mode
        or document.get("config", {}).get("budget") != expected_budget
        or run.get("seed") != expected_seed
        or document.get("config", {}).get("llm", {}).get("model") != "gpt-5.5"
    ):
        raise ValueError("unexpected low-thrust calibration condition")
    trajectory_path = Path(run["workdir"]) / "trajectory.jsonl"
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("low-thrust compact snapshot differs from raw trajectory")
    raw_events = load_trajectory(trajectory_path)
    if len(raw_events) != len(snapshot["events"]):
        raise ValueError("low-thrust raw and compact trajectory lengths differ")
    trajectory = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if (
            int(compact["step"]) != int(raw["step"])
            or compact["candidate_sha256"] != raw["candidate_sha256"]
            or compact["parent_sha256"] != raw["parent_sha256"]
        ):
            raise ValueError("low-thrust raw and compact trajectory lineage differs")
        metrics = raw.get("metrics") or {}
        trajectory.append({
            "step": int(compact["step"]),
            "accepted": bool(compact["accepted"]),
            "candidate_sha256": compact["candidate_sha256"],
            "parent_sha256": compact["parent_sha256"],
            **_scalar(metrics),
            "mission_summary": _mission_summary(metrics),
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
        "selected_mission_summary": _mission_summary(
            selected_raw.get("metrics") or {}
        ),
        "trajectory": trajectory,
    }
    if not _lineage_is_valid(record):
        raise ValueError("low-thrust proposal lineage is broken")
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if label == "blind_budget_three" else "online_incumbent"
    )
    if record["selection_policy"] != expected_policy:
        raise ValueError("low-thrust selection policy metadata is wrong")
    if int(run["evaluated"]) != record["oracle_calls"]:
        raise ValueError("low-thrust oracle-call count mismatch")
    if sum(event["accepted"] for event in trajectory[1:]) != int(run["accepted"]):
        raise ValueError("low-thrust accepted count mismatch")
    return record


def _axis_vector(record: dict[str, Any]) -> dict[str, Any]:
    metrics = record["selected_metrics"]
    return {
        "nominal_development_utility": metrics["development_score"],
        "nominal_terminal_feasibility": metrics[
            "development_mission_feasibility_rate"
        ],
        "sealed_phase_diagnostic": metrics["mean_development_phase_score"],
        "heldout_nominal_utility": metrics["heldout_policy_score"],
        "sealed_development_execution_robustness": metrics["robustness_score"],
        "sealed_heldout_execution_robustness": metrics[
            "heldout_robustness_score"
        ],
        "heldout_terminal_feasibility": metrics[
            "heldout_mission_feasibility_rate"
        ],
        "mean_development_delta_v_m_s": metrics[
            "mean_development_delta_v_m_s"
        ],
        "mean_heldout_delta_v_m_s": metrics["mean_heldout_delta_v_m_s"],
    }


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    source_equivalent: bool = True,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    proposals = [
        event for record in records.values() for event in record["trajectory"][1:]
    ]
    phase_values = [
        float(event["mean_development_phase_score"]) for event in proposals
    ] + [float(event["mean_heldout_phase_score"]) for event in proposals]
    gauss_newton = calibration["public_gauss_newton_metrics"]
    all_terminal_infeasible = all(
        event["development_mission_feasibility_rate"] == 0.0
        and event["heldout_mission_feasibility_rate"] == 0.0
        and event["development_shift_feasibility_rate"] == 0.0
        and event["heldout_shift_feasibility_rate"] == 0.0
        and event["mission_summary"]["nominal_feasible_count"] == 0
        and event["mission_summary"]["shifted_feasible_count"] == 0
        for event in proposals
    )
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
        and len(proposals) == 7
        and all(bool(event["valid"]) for event in proposals)
        and all(event["mission_summary"]["instance_count"] == 6 for event in proposals)
        and all(event["mission_summary"]["valid_instance_count"] == 6 for event in proposals)
        and all_terminal_infeasible
        and all(0.0 < float(event["development_score"]) < 0.01 for event in proposals)
        and all(float(event["heldout_policy_score"]) < 1.0e-8 for event in proposals)
        and all(float(event["mean_development_delta_v_m_s"]) > 500.0 for event in proposals)
        and max(phase_values) > 0.3 and min(phase_values) < 1.0e-6
        and one["best_score"] > normal["best_score"] > 0.0
        and blind["best_score"] > normal["best_score"]
        and sum(event["accepted"] for event in normal["trajectory"][1:]) == 1
        and sum(event["accepted"] for event in blind["trajectory"][1:]) == 2
        and float(gauss_newton["development_score"]) > 0.70
        and gauss_newton["development_mission_feasibility_rate"] == 1.0
        and gauss_newton["heldout_mission_feasibility_rate"] == 1.0
        and normal["total_tokens"] != blind["total_tokens"]
    )
    normal_minus_blind = {
        field: float(normal["selected_metrics"][field])
        - float(blind["selected_metrics"][field])
        for field in (
            "development_score", "robustness_score", "heldout_policy_score",
            "heldout_robustness_score",
            "development_mission_feasibility_rate",
            "heldout_mission_feasibility_rate",
            "mean_development_phase_score", "mean_heldout_phase_score",
        )
    }
    normal_minus_blind.update({
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
    })
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": "LOW_THRUST_CALIBRATION_NOT_CAUSAL_POPULATION_GLOBAL_OPTIMALITY_FLIGHT_OR_AUTONOMOUS_DISCOVERY_EVIDENCE",
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
        "observed_model_proposal_pattern": {
            "proposal_count": len(proposals),
            "valid_artifact_count": sum(bool(event["valid"]) for event in proposals),
            "nominal_terminal_feasible_proposal_count": sum(
                event["development_mission_feasibility_rate"] > 0.0
                or event["heldout_mission_feasibility_rate"] > 0.0
                for event in proposals
            ),
            "execution_shift_feasible_proposal_count": sum(
                event["development_shift_feasibility_rate"] > 0.0
                or event["heldout_shift_feasibility_rate"] > 0.0
                for event in proposals
            ),
            "minimum_development_score": min(
                float(event["development_score"]) for event in proposals
            ),
            "maximum_development_score": max(
                float(event["development_score"]) for event in proposals
            ),
            "maximum_heldout_score": max(
                float(event["heldout_policy_score"]) for event in proposals
            ),
            "minimum_phase_diagnostic": min(phase_values),
            "maximum_phase_diagnostic": max(phase_values),
            "all_terminal_infeasible": all_terminal_infeasible,
        },
        "normal_minus_blind_diagnostic": normal_minus_blind,
        "science_axis_separation": {
            "numerical_fidelity": calibration["integration_consistency"],
            "public_gauss_newton": {
                "nominal_development_utility": gauss_newton["development_score"],
                "nominal_terminal_feasibility": gauss_newton[
                    "development_mission_feasibility_rate"
                ],
                "sealed_phase_diagnostic": gauss_newton[
                    "mean_development_phase_score"
                ],
                "heldout_nominal_utility": gauss_newton["heldout_policy_score"],
                "sealed_development_execution_robustness": gauss_newton[
                    "robustness_score"
                ],
                "sealed_heldout_execution_robustness": gauss_newton[
                    "heldout_robustness_score"
                ],
                "heldout_terminal_feasibility": gauss_newton[
                    "heldout_mission_feasibility_rate"
                ],
            },
            "gpt55_budget_one_selected": _axis_vector(one),
            "gpt55_normal_budget_three_selected": _axis_vector(normal),
            "gpt55_blind_budget_three_selected": _axis_vector(blind),
        },
        "limitations": [
            "Each condition has one run; no confidence interval, model ranking, scaling law or causal feedback estimate is supported.",
            "Normal and selection-blind share a local seed label, but the Azure endpoint exposes no server-side model seed, so generation randomness is not paired.",
            "The budget-three conditions are oracle-call matched but not token- or context-matched; normal used %d more tokens." % (normal["total_tokens"] - blind["total_tokens"]),
            "Budget-one uses a different local seed label and is an independent calibration, not a prefix of the budget-three trajectory.",
            "Terminal phase is a sealed diagnostic and is not part of the first-five-MEE utility or hard terminal-feasibility gate; it must not be reinterpreted as a failed scored objective.",
            "The six missions are deterministic public instances; server-held procedural missions are still required.",
            "The controlled model omits third bodies, drag, eclipse, power, thermal and attitude constraints and is not flight validation.",
            "The public Gauss--Newton witness establishes solvability, not global optimality; no result supports autonomous scientific discovery.",
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
