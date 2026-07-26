#!/usr/bin/env python3
"""Bind and analyze the three RANSCalibration-v2 GPT-5.5 calibrations.

These are single-run task calibrations.  The report keeps nominal fitting,
higher-Re transfer, coordinate-shift robustness and raw closure error separate;
it is not a feedback-causal, population, universal-RANS or discovery result.
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
from frontier_science.runtime_migration import runtime_migration_status  # noqa: E402


TASK = "Turbulence/RANSCalibration"
CALIBRATION = "experiments/rans_v2_calibration_2026-07-24.json"
REPORTS = {
    "budget_one": "experiments/gpt55_rans_v2_b1_2026-07-24.json",
    "normal_budget_three": "experiments/gpt55_rans_v2_b3_2026-07-24.json",
    "blind_budget_three": (
        "experiments/gpt55_rans_v2_blind_b3_2026-07-24.json"
    ),
}
EXPECTED_MODEL_SOURCE_REVISION = (
    "458cdf8357977c04d3d3dc14fd83cdc99794fd08"
)
TASK_RUNTIME_SCOPE = (
    "frontier_science/evaluate.py",
    "frontier_science/secure_eval.py",
    "frontier_science/candidate_worker.py",
    "frontier_science/rpc_codec.py",
    "frontier_science/spec.py",
    "frontier_science/registry.py",
    "benchmarks/Turbulence/RANSCalibration/Task.md",
    "benchmarks/Turbulence/RANSCalibration/solution.py",
    "benchmarks/Turbulence/RANSCalibration/frontier_eval",
    "benchmarks/Turbulence/RANSCalibration/verification",
    "requirements-upstream.txt",
)
SCALAR_FIELDS = (
    "combined_score", "valid", "feasibility_rate", "raw_score",
    "robustness_score", "heldout_policy_score",
    "heldout_robustness_score", "heldout_feasibility_rate",
    "development_raw_loss", "heldout_raw_loss",
    "development_worst_shift_loss", "heldout_worst_shift_loss",
    "development_velocity_rmse_plus", "heldout_velocity_rmse_plus",
    "development_reynolds_shear_rmse_plus",
    "heldout_reynolds_shear_rmse_plus", "candidate_parameter_count",
    "physics_gate_passed", "candidate_failure_kind",
)
SCIENCE_AXES = (
    "raw_score", "heldout_policy_score", "robustness_score",
    "heldout_robustness_score", "development_raw_loss",
    "heldout_raw_loss", "development_worst_shift_loss",
    "heldout_worst_shift_loss",
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
    return (
        isinstance(value, (int, float)) and not isinstance(value, bool)
        and value == value and abs(float(value)) != float("inf")
    )


def _selected_event(events: list[dict[str, Any]], best: float) -> dict[str, Any]:
    matches = [
        event for event in events
        if bool(event.get("accepted"))
        and abs(float(event["score"]) - float(best)) <= 1.0e-12
    ]
    if not matches:
        raise ValueError("no accepted RANS event matches run best")
    # First valid tied maximum matches the greedy selector's strict > rule.
    return min(matches, key=lambda event: int(event["step"]))


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
    witnesses = document.get("witness_metrics") or {}
    data = document.get("data_provenance_checks") or {}
    identifiability = document.get("identifiability") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and data.get("passed") is True
        and data.get("aggregate_sha256")
        == "0f70ce507fa65175f044538b41a266d42347cdf9c1bf2e7fafd8f630f47ed9bf"
        and data.get("doi") == "10.5281/zenodo.5749302"
        and data.get("license") == "CC-BY-4.0"
        and identifiability.get("jacobian_rank") == 4
        and identifiability.get("parameter_count") == 4
        and identifiability.get("passed") is True
        and document.get("invalid_artifact_checks_passed") is True
        and document.get("physics_checks_passed") is True
        and document.get("witness_checks_passed") is True
        and document.get("optimizer_rebuild_checks_passed") is True
        and witnesses.get("baseline", {}).get("combined_score") == 0.0
        and witnesses.get("nominal", {}).get("combined_score") > 0.999999
        and witnesses.get("robust", {}).get("robustness_score") > 0.999999
    ):
        raise ValueError("RANS-v2 task calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "data_provenance_checks": data,
        "identifiability": identifiability,
        "witness_metrics": {
            label: _scalar(metrics) for label, metrics in witnesses.items()
        },
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
        raise ValueError("RANS model report is not trusted: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one successful RANS run")
    run = runs[0]
    config = document.get("config") or {}
    expected_mode = (
        "selection_blind" if label == "blind_budget_three" else "normal"
    )
    expected_budget = 1 if label == "budget_one" else 3
    if not (
        run.get("task") == TASK
        and run.get("algorithm") == "greedy_rewrite"
        and run.get("feedback_mode") == expected_mode
        and run.get("seed") == 1
        and config.get("budget") == expected_budget
        and config.get("llm", {}).get("model") == "gpt-5.5"
    ):
        raise ValueError("unexpected RANS calibration condition")

    workdir = Path(run["workdir"]).resolve()
    try:
        relative_workdir = workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("RANS workdir is outside repository") from exc
    trajectory_path = workdir / "trajectory.jsonl"
    raw_events = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("RANS portable snapshot differs from raw trajectory")
    if len(raw_events) != expected_budget + 1:
        raise ValueError("RANS trajectory does not contain every proposal")
    trajectory = []
    raw_by_step = {}
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            int(compact["step"]) == int(raw["step"])
            and compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
        ):
            raise ValueError("RANS raw and compact lineage differs")
        metrics = raw.get("metrics") or {}
        step = int(raw["step"])
        raw_by_step[step] = raw
        parameters = metrics.get("candidate_parameter_vector")
        if not (
            isinstance(parameters, list) and len(parameters) == 4
            and all(_finite_number(value) for value in parameters)
        ):
            raise ValueError("RANS event lacks four finite parameters")
        trajectory.append({
            "step": step,
            "accepted": bool(compact["accepted"]),
            "valid": bool(metrics.get("valid")),
            "score": float(compact["score"]),
            "best_score": float(compact["best_score"]),
            "candidate_sha256": compact["candidate_sha256"],
            "parent_sha256": compact["parent_sha256"],
            "candidate_parameter_vector": [float(value) for value in parameters],
            **_scalar(metrics),
        })
    selected = _selected_event(snapshot["events"], float(run["best"]))
    selected_raw = raw_by_step[int(selected["step"])]
    selected_metrics = selected_raw.get("metrics") or {}
    if _sha256(workdir / "best_program.py") != selected["candidate_sha256"]:
        raise ValueError("RANS best program hash differs from selected event")
    manifest_path = workdir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not (
        manifest.get("task_id") == TASK
        and manifest.get("algorithm") == "greedy_rewrite"
        and manifest.get("feedback_mode") == expected_mode
        and manifest.get("seed") == 1
        and manifest.get("llm_condition_sha256")
        == config.get("llm_condition_sha256")
    ):
        raise ValueError("RANS run manifest differs from report")
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
        "feedback_mode": expected_mode,
        "feedback_scope": summary.get("feedback_scope"),
        "selection_policy": summary.get("selection_policy"),
        "seed": int(run["seed"]),
        "proposal_budget": expected_budget,
        "oracle_calls": int(summary["oracle_calls"]),
        "budget_units": int(summary["budget_units"]),
        "llm_calls": int(summary["llm"]["calls"]),
        "provider_usage_records": int(
            summary["llm"]["provider_usage_records"]
        ),
        "total_tokens": summary["llm"].get("total_tokens"),
        "wall_seconds": float(summary["wall_seconds"]),
        "best_score": float(run["best"]),
        "selected_step": int(selected["step"]),
        "selected_candidate_sha256": selected["candidate_sha256"],
        "selected_metrics": _scalar(selected_metrics),
        "selected_parameters": [
            float(value)
            for value in selected_metrics["candidate_parameter_vector"]
        ],
        "best_program": str(relative_workdir / "best_program.py"),
        "terminal_proposal_sha256": trajectory[-1]["candidate_sha256"],
        "terminal_proposal_score": trajectory[-1]["score"],
        "terminal_differs_from_selected": (
            trajectory[-1]["candidate_sha256"] != selected["candidate_sha256"]
        ),
        "proposal_valid_count": sum(event["valid"] for event in trajectory[1:]),
        "trajectory": trajectory,
    }
    record["integrity_passed"] = bool(
        _lineage_is_valid(record)
        and record["selection_policy"] == expected_policy
        and record["oracle_calls"] == expected_budget + 1
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
        raise ValueError("RANS lineage or accounting gate failed")
    return record


def _endpoint(record: dict[str, Any]) -> dict[str, Any]:
    metrics = record["selected_metrics"]
    return {
        "selected_step": record["selected_step"],
        "parameters": record["selected_parameters"],
        "development_nominal_score": metrics["raw_score"],
        "development_robustness_score": metrics["robustness_score"],
        "heldout_nominal_score": metrics["heldout_policy_score"],
        "heldout_robustness_score": metrics["heldout_robustness_score"],
        "development_raw_loss": metrics["development_raw_loss"],
        "development_worst_shift_loss": metrics["development_worst_shift_loss"],
        "heldout_raw_loss": metrics["heldout_raw_loss"],
        "heldout_worst_shift_loss": metrics["heldout_worst_shift_loss"],
        "development_to_heldout_nominal_gap": (
            float(metrics["raw_score"])
            - float(metrics["heldout_policy_score"])
        ),
        "development_to_heldout_robustness_gap": (
            float(metrics["robustness_score"])
            - float(metrics["heldout_robustness_score"])
        ),
        "nominal_to_robustness_gap_development": (
            float(metrics["raw_score"])
            - float(metrics["robustness_score"])
        ),
        "nominal_to_robustness_gap_heldout": (
            float(metrics["heldout_policy_score"])
            - float(metrics["heldout_robustness_score"])
        ),
        "terminal_differs_from_selected": record["terminal_differs_from_selected"],
        "terminal_proposal_score": record["terminal_proposal_score"],
        "oracle_calls": record["oracle_calls"],
        "total_tokens": record["total_tokens"],
        "wall_seconds": record["wall_seconds"],
    }


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    runtime_source_equivalent: bool = True,
    expected_model_source_revision: str = EXPECTED_MODEL_SOURCE_REVISION,
    runtime_migration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    conditions = {
        record["llm_condition_sha256"] for record in records.values()
    }
    execution_passed = bool(
        runtime_source_equivalent
        and revisions == {expected_model_source_revision}
        and len(scopes) == 1
        and len(conditions) == 1 and None not in conditions
        and all(record["integrity_passed"] for record in records.values())
        and all(record["model"] == "gpt-5.5" for record in records.values())
        and all(not record["server_side_seed_control"] for record in records.values())
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["feedback_mode"] == normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and one["seed"] == normal["seed"] == blind["seed"] == 1
    )
    endpoints = {label: _endpoint(record) for label, record in records.items()}
    accepted_normal = [
        event for event in normal["trajectory"][1:] if event["accepted"]
    ]
    regressions = [
        {
            "step": event["step"],
            "score": event["score"],
            "incumbent_best_score": event["best_score"],
            "regression": float(event["best_score"] - event["score"]),
        }
        for event in normal["trajectory"][1:]
        if float(event["score"]) < float(event["best_score"])
    ]
    normal_minus_blind = {
        field: (
            float(normal["selected_metrics"][field])
            - float(blind["selected_metrics"][field])
        )
        for field in SCIENCE_AXES
    }
    normal_minus_blind.update({
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
        "total_tokens": (
            normal["total_tokens"] - blind["total_tokens"]
            if _finite_number(normal["total_tokens"])
            and _finite_number(blind["total_tokens"]) else None
        ),
        "wall_seconds": normal["wall_seconds"] - blind["wall_seconds"],
    })
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "RANS_SINGLE_RUN_TASK_CALIBRATION_NOT_CAUSAL_POPULATION_"
            "UNIVERSAL_CLOSURE_CFD_OR_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_task_source_revision": calibration["source_revision"],
        "input_model_source_revision": (
            next(iter(revisions)) if len(revisions) == 1 else None
        ),
        "expected_model_source_revision": expected_model_source_revision,
        "input_task_runtime_source_equivalent": bool(runtime_source_equivalent),
        "input_task_runtime_source_migration": runtime_migration,
        "input_source_scope_equivalent": len(scopes) == 1,
        "input_llm_condition_equivalent": len(conditions) == 1,
        "task_calibration": calibration,
        "records": records,
        "condition_endpoints": endpoints,
        "normal_accepted_events": accepted_normal,
        "normal_raw_regressions": regressions,
        "normal_minus_blind_selected_contrast": normal_minus_blind,
        "descriptive_findings": {
            "budget_one_improves_visible_baseline": one["best_score"] > 0.0,
            "normal_budget_three_improves_visible_baseline": normal["best_score"] > 0.0,
            "blind_budget_three_improves_visible_baseline": blind["best_score"] > 0.0,
            "normal_selected_transfers_above_development_score": (
                float(normal["selected_metrics"]["heldout_policy_score"])
                > float(normal["selected_metrics"]["raw_score"])
            ),
            "normal_selected_robustness_below_nominal_on_both_splits": (
                float(normal["selected_metrics"]["robustness_score"])
                < float(normal["selected_metrics"]["raw_score"])
                and float(normal["selected_metrics"]["heldout_robustness_score"])
                < float(normal["selected_metrics"]["heldout_policy_score"])
            ),
            "normal_has_rejected_regression_after_improvement": bool(regressions),
            "normal_rollback_preserves_selected_incumbent": (
                normal["terminal_differs_from_selected"]
                and normal["selected_step"] < normal["trajectory"][-1]["step"]
            ),
            "normal_and_blind_are_oracle_call_matched": (
                normal_minus_blind["oracle_calls"] == 0
            ),
            "normal_and_blind_are_token_matched": (
                normal_minus_blind["total_tokens"] == 0
            ),
            "feedback_necessity_identified": False,
        },
        "limitations": [
            "Each condition has one run; no confidence interval, population, leaderboard or scaling-law estimate is supported.",
            "The Azure endpoint exposes no server-side generation seed, so equal local seed labels do not pair model randomness.",
            "Normal and selection-blind are descriptive single runs; equal oracle calls cannot identify a feedback effect because token usage, wall time and generation randomness differ.",
            "Budget one and budget three are independent model calls, not nested prefixes, even though they share a local seed label.",
            "Selection-blind accepted flags denote offline best-of-batch updates only; every proposal parent is the frozen baseline.",
            "Only the development nominal score was visible to proposal and selection; higher-Re transfer, coordinate-shift robustness and profile diagnostics were sealed.",
            "The four-parameter algebraic closure is not a transport-equation RANS model or a universal turbulence closure.",
            "Re_tau 590/950 tests transfer inside plane channel flow, not separated flows, new geometries or engineering deployment.",
            "No result supports a new turbulence mechanism, high-fidelity CFD validation or autonomous scientific discovery.",
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
    current_revision = source_provenance(ROOT).get("git_revision")
    current_changes = _source_changes(EXPECTED_MODEL_SOURCE_REVISION, current_revision)
    migration = runtime_migration_status(
        EXPECTED_MODEL_SOURCE_REVISION, current_revision, current_changes,
    ) if current_changes else None
    runtime_source_equivalent = bool(
        runtime_source_equivalent
        and (not current_changes or (migration or {}).get("accepted") is True)
    )
    runtime_changes = sorted(set(runtime_changes + current_changes))
    report = _analyze_records(
        calibration, records, runtime_source_equivalent,
        expected_model_source_revision=EXPECTED_MODEL_SOURCE_REVISION,
        runtime_migration=migration,
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
