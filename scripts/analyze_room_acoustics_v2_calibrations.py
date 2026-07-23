#!/usr/bin/env python3
"""Build portable, non-causal evidence from RoomImpulseResponse-v2 runs."""

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


TASK = "Acoustics/RoomImpulseResponse"
CALIBRATION = "experiments/room_acoustics_v2_calibration_2026-07-23_v2.json"
REPORTS = {
    "budget_one": "experiments/gpt55_room_acoustics_v2_b1_2026-07-23.json",
    "normal_budget_three": "experiments/gpt55_room_acoustics_v2_b3_2026-07-23.json",
    "blind_budget_three": (
        "experiments/gpt55_room_acoustics_v2_blind_b3_2026-07-23.json"
    ),
}
EXPECTED_MODEL_SOURCE_REVISION = (
    "4bd362e6b96217389176fcc0da216596cde41eaf"
)
TASK_RUNTIME_SCOPE = (
    "frontier_science",
    "benchmarks/Acoustics/RoomImpulseResponse",
    "requirements-upstream.txt",
)
SCALAR_FIELDS = (
    "combined_score", "valid", "feasibility_rate", "raw_score",
    "robustness_score", "development_validation_gap",
    "heldout_policy_score", "heldout_robustness_score",
    "heldout_feasibility_rate", "development_nominal_utility",
    "heldout_nominal_utility", "development_robust_utility",
    "heldout_robust_utility", "development_proxy_utility",
    "heldout_proxy_utility", "development_proxy_exact_gap",
    "heldout_proxy_exact_gap", "candidate_instance_call_count",
    "candidate_instance_valid_rate", "candidate_failure_kind",
    "infrastructure_failure",
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


def _instance_axes(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    rows = metrics.get("per_instance")
    if not isinstance(rows, list) or len(rows) != 6:
        raise ValueError("selected room-acoustics event lacks six instances")
    retained = []
    for row in rows:
        shifted = row.get("shifted")
        nominal = row.get("nominal") or {}
        proxy = row.get("proxy") or {}
        if not isinstance(shifted, list) or len(shifted) != 5:
            raise ValueError("room-acoustics instance lacks five shifts")
        retained.append({
            "name": row["name"],
            "split": row["split"],
            "valid": bool(row["valid"]),
            "nominal_score": float(row["score"]),
            "robustness_score": float(row["robustness_score"]),
            "nominal_utility": float(row["nominal_utility"]),
            "robust_utility": float(row["robust_utility"]),
            "proxy_utility": float(row["proxy_utility"]),
            "proxy_exact_utility_gap": float(row["proxy_exact_utility_gap"]),
            "treatment_area_m2": float(row["treatment_area_m2"]),
            "design": row["design"],
            "clarity_utility": float(nominal["clarity_utility"]),
            "reverberation_utility": float(nominal["reverberation_utility"]),
            "uniformity_utility": float(nominal["uniformity_utility"]),
            "mean_c50_db": float(nominal["mean_c50_db"]),
            "twentieth_percentile_c50_db": float(
                nominal["twentieth_percentile_c50_db"]
            ),
            "mean_absolute_log_rt_error": float(
                nominal["mean_absolute_log_rt_error"]
            ),
            "mean_spatial_level_std_db": float(
                nominal["mean_spatial_level_std_db"]
            ),
            "proxy_mean_c50_db": float(proxy["mean_c50_db"]),
            "minimum_shift_utility": min(
                float(shift["utility"]) for shift in shifted
            ),
            "higher_order_combined_shift_utility": float(next(
                shift["utility"] for shift in shifted
                if shift["name"] == "higher_order_combined_shift"
            )),
            "all_shift_geometry_feasible": all(
                bool(shift["geometry_feasible"]) for shift in shifted
            ),
        })
    if not all(row["valid"] for row in retained):
        raise ValueError("selected room-acoustics artifact has an invalid instance")
    return retained


def _selected_event(events: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [event for event in events if bool(event.get("accepted"))]
    if not accepted:
        raise ValueError("trajectory has no accepted artifact")
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
    recalibration = document.get("reference_recalibration") or {}
    checks = document.get("independent_equation_and_reference_checks")
    if not (
        document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and document.get("preflight_passed") is True
        and document.get("difficulty_gate", {}).get("passed") is True
        and document.get("determinism_check", {}).get("passed") is True
        and recalibration.get("performed") is True
        and recalibration.get("passed") is True
        and isinstance(checks, list) and len(checks) == 6
        and all(row.get("passed") is True for row in checks)
    ):
        raise ValueError("RoomImpulseResponse-v2 task calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "task_dimensions": document["task_dimensions"],
        "weak_baseline": document["weak_baseline"],
        "nominal_reference_policy": document["nominal_reference_policy"],
        "robust_reference_policy": document["robust_reference_policy"],
        "difficulty_gate": document["difficulty_gate"],
        "reference_recalibration": recalibration,
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
    expected_mode = "selection_blind" if label == "blind_budget_three" else "normal"
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
        raise ValueError("unexpected room-acoustics calibration condition")

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
    if len(raw_events) != len(snapshot["events"]):
        raise ValueError("raw and compact trajectory lengths differ")

    raw_by_step = {}
    trajectory = []
    proposal_failure_counts: dict[str, int] = {}
    valid_proposal_axes = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            int(compact["step"]) == int(raw["step"])
            and compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
        ):
            raise ValueError("raw and compact trajectory lineage differs")
        metrics = raw.get("metrics") or {}
        raw_by_step[int(raw["step"])] = raw
        kind = metrics.get("candidate_failure_kind")
        if int(raw["step"]) > 0 and kind:
            proposal_failure_counts[str(kind)] = (
                proposal_failure_counts.get(str(kind), 0) + 1
            )
        if int(raw["step"]) > 0 and bool(metrics.get("valid")):
            valid_proposal_axes.append({
                "step": int(raw["step"]),
                "candidate_sha256": raw["candidate_sha256"],
                "metrics": _scalar(metrics),
                "instance_axes": _instance_axes(metrics),
            })
        trajectory.append({
            "step": int(compact["step"]),
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

    record = {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(report_path),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "llm_condition_sha256": config.get("llm_condition_sha256"),
        "model": config.get("llm", {}).get("model"),
        "server_side_seed_control": bool(
            config.get("llm", {}).get("server_side_seed_control")
        ),
        "feedback_mode": run["feedback_mode"],
        "feedback_scope": run["summary"].get("feedback_scope"),
        "selection_policy": run["summary"].get("selection_policy"),
        "seed": int(run["seed"]),
        "proposal_budget": int(config["budget"]),
        "oracle_calls": int(run["summary"]["oracle_calls"]),
        "total_tokens": int(run["summary"]["llm"]["total_tokens"]),
        "wall_seconds": float(run["summary"]["wall_seconds"]),
        "valid_rate": float(run["summary"]["valid_rate"]),
        "best_score": float(run["best"]),
        "selected_step": int(selected["step"]),
        "selected_candidate_sha256": selected["candidate_sha256"],
        "selected_metrics": _scalar(selected_metrics),
        "selected_instance_axes": selected_axes,
        "best_program": str(relative_workdir / "best_program.py"),
        "proposal_valid_count": sum(event["valid"] for event in trajectory[1:]),
        "proposal_failure_counts": proposal_failure_counts,
        "valid_proposal_axes": valid_proposal_axes,
        "trajectory": trajectory,
    }
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if expected_mode == "selection_blind" else "online_incumbent"
    )
    if not (
        _lineage_is_valid(record)
        and record["selection_policy"] == expected_policy
        and int(run["evaluated"]) == record["oracle_calls"]
        and int(raw_events[-1]["oracle_calls"]) == record["oracle_calls"]
        and sum(event["accepted"] for event in trajectory[1:])
        == int(run["accepted"])
    ):
        raise ValueError("room-acoustics lineage or accounting gate failed")
    return record


def _selected_contrast(normal: dict[str, Any], blind: dict[str, Any]) -> dict[str, Any]:
    result = {
        field: (
            float(normal["selected_metrics"][field])
            - float(blind["selected_metrics"][field])
        )
        for field in (
            "raw_score", "robustness_score", "heldout_policy_score",
            "heldout_robustness_score", "development_nominal_utility",
            "heldout_nominal_utility", "development_robust_utility",
            "heldout_robust_utility", "development_proxy_exact_gap",
            "heldout_proxy_exact_gap",
        )
    }
    result.update({
        "selection_score": normal["best_score"] - blind["best_score"],
        "proposal_valid_rate": (
            normal["proposal_valid_count"] / normal["proposal_budget"]
            - blind["proposal_valid_count"] / blind["proposal_budget"]
        ),
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "wall_seconds": normal["wall_seconds"] - blind["wall_seconds"],
    })
    return result


def _analyze_records(calibration: dict[str, Any],
                     records: dict[str, dict[str, Any]],
                     runtime_source_equivalent=True) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    conditions = {record["llm_condition_sha256"] for record in records.values()}
    contrast = _selected_contrast(normal, blind)
    one_proposal = one["valid_proposal_axes"][0]
    blind_steps = {row["step"]: row for row in blind["valid_proposal_axes"]}

    execution_passed = bool(
        runtime_source_equivalent
        and revisions == {EXPECTED_MODEL_SOURCE_REVISION}
        and len(scopes) == 1
        and len(conditions) == 1
        and None not in conditions
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
        and one["oracle_calls"] == 2
        and normal["oracle_calls"] == blind["oracle_calls"] == 4
        and one["selected_step"] == normal["selected_step"] == 0
        and blind["selected_step"] == 3
        and one["proposal_valid_count"] == 1
        and normal["proposal_valid_count"] == 0
        and blind["proposal_valid_count"] == 2
        and normal["proposal_failure_counts"] == {
            "candidate_runtime_error": 3
        }
        and blind["proposal_failure_counts"] == {
            "candidate_runtime_error": 1
        }
        and one_proposal["metrics"]["raw_score"] == 0.0
        and one_proposal["metrics"]["heldout_policy_score"] > 0.40
        and blind_steps[2]["metrics"]["raw_score"] > 0.10
        and blind_steps[3]["metrics"]["raw_score"] > 0.70
        and blind["selected_metrics"]["robustness_score"] > 0.60
        and blind["selected_metrics"]["heldout_policy_score"] > 0.70
        and blind["selected_metrics"]["heldout_robustness_score"] > 0.75
        and all(
            row["all_shift_geometry_feasible"]
            for row in blind["selected_instance_axes"]
        )
        and contrast["oracle_calls"] == 0
        and contrast["total_tokens"] != 0
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "ROOM_ACOUSTICS_SINGLE_RUN_CALIBRATION_NOT_CAUSAL_POPULATION_"
            "ENGINEERING_OR_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_model_source_revision": (
            next(iter(revisions)) if len(revisions) == 1 else None
        ),
        "input_task_runtime_source_equivalent": bool(runtime_source_equivalent),
        "input_source_scope_equivalent": len(scopes) == 1,
        "input_llm_condition_equivalent": len(conditions) == 1,
        "task_calibration": calibration,
        "records": records,
        "normal_minus_blind_selected_contrast": contrast,
        "observed_proposal_pattern": {
            "budget_one_valid_but_not_development_improving": (
                one_proposal["metrics"]["raw_score"] == 0.0
            ),
            "budget_one_heldout_nominal_score": one_proposal["metrics"][
                "heldout_policy_score"
            ],
            "budget_one_development_nominal_utility": one_proposal[
                "metrics"
            ]["development_nominal_utility"],
            "budget_one_heldout_nominal_utility": one_proposal["metrics"][
                "heldout_nominal_utility"
            ],
            "normal_runtime_error_count": normal["proposal_failure_counts"].get(
                "candidate_runtime_error", 0
            ),
            "blind_runtime_error_count": blind["proposal_failure_counts"].get(
                "candidate_runtime_error", 0
            ),
            "blind_step_two_score": blind_steps[2]["metrics"]["raw_score"],
            "blind_step_three_score": blind_steps[3]["metrics"]["raw_score"],
            "blind_selected_development_robustness": blind[
                "selected_metrics"
            ]["robustness_score"],
            "blind_selected_heldout_nominal_score": blind[
                "selected_metrics"
            ]["heldout_policy_score"],
            "blind_selected_heldout_robustness": blind[
                "selected_metrics"
            ]["heldout_robustness_score"],
        },
        "descriptive_findings": {
            "budget_one_preserves_optimization_headroom": (
                one["best_score"] == 0.0
            ),
            "budget_one_exposes_development_heldout_conflict": (
                one_proposal["metrics"]["raw_score"] == 0.0
                and one_proposal["metrics"]["heldout_policy_score"] > 0.40
            ),
            "open_loop_batch_finds_non_saturated_improvement": (
                0.70 < blind["best_score"] < 0.90
            ),
            "selected_open_loop_artifact_transfers_to_heldout_and_shifts": (
                blind["selected_metrics"]["heldout_policy_score"] > 0.70
                and blind["selected_metrics"]["heldout_robustness_score"] > 0.75
            ),
            "normal_and_blind_are_oracle_call_matched": (
                contrast["oracle_calls"] == 0
            ),
            "normal_and_blind_are_not_token_matched": (
                contrast["total_tokens"] != 0
            ),
            "feedback_not_shown_necessary_by_open_loop_calibration": (
                blind["best_score"] > 0.70
            ),
        },
        "limitations": [
            "Each condition has one run; no confidence interval, population estimate, leaderboard or scaling-law claim is supported.",
            "The Azure endpoint exposes no server-side generation seed, so equal local seed labels do not pair model randomness.",
            "Normal and selection-blind are oracle-call matched but not exactly token- or wall-time-matched; their contrast is descriptive, not causal.",
            "Budget one uses a different local seed label and is an independent calibration, not a prefix of budget three.",
            "Selection-blind accepted flags denote offline best-of-batch updates only; every proposal parent is the frozen baseline and no score enters later prompts.",
            "Held-out, proxy-gap, per-instance and five shifted robustness axes were sealed from proposal and selection state.",
            "The reduced-order shoebox energy model omits phase, diffraction, scattering and structural coupling; hybrid wave/ray and measured-RIR replication remain required.",
            "The selected artifact is an optimization policy, not a novel acoustic mechanism, building validation or autonomous scientific discovery.",
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
        calibration, records, runtime_source_equivalent
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
