#!/usr/bin/env python3
"""Build portable, non-causal evidence from HartreeFockSCF-v2 model runs."""

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


TASK = "QuantumChemistry/HartreeFockSCF"
CALIBRATION = "experiments/hartree_fock_v2_calibration_2026-07-23_v2.json"
REPORTS = {
    "budget_one": "experiments/gpt55_hartree_fock_v2_b1_2026-07-23.json",
    "normal_budget_three": (
        "experiments/gpt55_hartree_fock_v2_b3_2026-07-23.json"
    ),
    "blind_budget_three": (
        "experiments/gpt55_hartree_fock_v2_blind_b3_2026-07-23.json"
    ),
}
EXPECTED_MODEL_SOURCE_REVISION = (
    "746dff077a58e4c9a4afea821b5a3015d70cc378"
)
TASK_RUNTIME_SCOPE = (
    "frontier_science",
    "benchmarks/Chemistry/HartreeFockSCF",
    "requirements-upstream.txt",
)
MATERIAL_SELECTION_EPSILON = 1.0e-12
MATERIAL_SCIENCE_AXIS_DELTA = 1.0e-3
SCALAR_FIELDS = (
    "combined_score", "valid", "feasibility_rate", "raw_score",
    "robustness_score", "heldout_policy_score",
    "heldout_robustness_score", "heldout_feasibility_rate",
    "development_shifted_score", "heldout_shifted_score",
    "development_representation_invariance_score",
    "heldout_representation_invariance_score",
    "development_stability_rate", "heldout_stability_rate",
    "development_mean_energy_error_hartree",
    "heldout_mean_energy_error_hartree",
    "development_maximum_scf_residual",
    "heldout_maximum_scf_residual",
    "candidate_problem_call_count", "candidate_instance_valid_rate",
    "infrastructure_failure", "candidate_failure_kind",
)
SCIENCE_AXES = (
    "raw_score", "heldout_policy_score", "robustness_score",
    "heldout_robustness_score", "development_shifted_score",
    "heldout_shifted_score",
    "development_representation_invariance_score",
    "heldout_representation_invariance_score",
    "development_stability_rate", "heldout_stability_rate",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, TASK_RUNTIME_SCOPE, root=ROOT)


def _scalar(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in SCALAR_FIELDS}


def _instance_axes(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    rows = metrics.get("per_instance")
    if not isinstance(rows, list) or len(rows) != 7:
        raise ValueError("selected Hartree--Fock event lacks seven instances")
    retained = []
    for row in rows:
        retained.append({
            "name": row["name"],
            "split": row["split"],
            "valid": bool(row["valid"]),
            "nominal_score": float(row["score"]),
            "energy_error_hartree": float(row["energy_error_hartree"]),
            "scf_residual": float(row["scf_residual"]),
            "shifted_valid": bool(row["shifted_valid"]),
            "shifted_score": float(row["shifted_score"]),
            "shifted_energy_error_hartree": row.get(
                "shifted_energy_error_hartree"
            ),
            "representation_invariance_score": float(
                row["representation_invariance_score"]
            ),
            "minimum_stability_curvature": float(
                row["minimum_stability_curvature"]
            ),
            "internally_stable": bool(row["internally_stable"]),
            "robustness_score": float(row["robustness_score"]),
        })
    if not all(row["valid"] for row in retained):
        raise ValueError("selected Hartree--Fock artifact has an invalid instance")
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
    sensitivity = document.get("baseline_thread_sensitivity") or {}
    comparison = document.get(
        "secure_vs_authoritative_direct_axis_comparison"
    ) or {}
    sensitive_axes = sensitivity.get("materially_sensitive_axes") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and document.get("archive_hash_passed") is True
        and document.get("independent_equations_passed") is True
        and document.get("difficulty_passed") is True
        and document.get("invalid_artifacts_passed") is True
        and document.get("metric_sealing_passed") is True
        and comparison.get("passed") is True
        and sensitivity.get("authoritative_thread_count") == 1
        and sensitivity.get("material_sensitivity_detected") is True
        and "heldout_shifted_score" in sensitive_axes
        and sensitive_axes["heldout_shifted_score"]["span"] > 0.30
        and document["secure_sandbox_baseline"][
            "heldout_shifted_score"
        ] < 0.70
        and document["reference"]["combined_score"] > 0.999
        and document["reference"]["heldout_robustness_score"] > 0.99
    ):
        raise ValueError("Hartree--Fock v2 task calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "dataset_sha256": document["dataset_sha256"],
        "authoritative_one_thread_direct_baseline": document[
            "authoritative_one_thread_direct_baseline"
        ],
        "secure_sandbox_baseline": document["secure_sandbox_baseline"],
        "secure_vs_authoritative_direct_axis_comparison": comparison,
        "baseline_thread_sensitivity": sensitivity,
        "reference": document["reference"],
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
        raise ValueError("unexpected Hartree--Fock calibration condition")

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

    trajectory = []
    raw_by_step = {}
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            int(compact["step"]) == int(raw["step"])
            and compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
        ):
            raise ValueError("raw and compact trajectory lineage differs")
        metrics = raw.get("metrics") or {}
        raw_by_step[int(raw["step"])] = raw
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
    best_program = workdir / "best_program.py"
    if _sha256(best_program) != selected["candidate_sha256"]:
        raise ValueError("best program hash differs from selected candidate")
    if abs(float(selected["best_score"]) - float(run["best"])) > 1.0e-12:
        raise ValueError("selected event differs from run best")

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
        "selected_instance_axes": _instance_axes(selected_metrics),
        "best_program": str(relative_workdir / "best_program.py"),
        "proposal_valid_count": sum(event["valid"] for event in trajectory[1:]),
        "infrastructure_failure_count": sum(
            bool(event.get("infrastructure_failure"))
            for event in trajectory[1:]
        ),
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
        raise ValueError("Hartree--Fock lineage or accounting gate failed")
    return record


def _epsilon_selected_event(record: dict[str, Any], epsilon: float) -> dict[str, Any]:
    selected = record["trajectory"][0]
    current = float(selected["score"])
    for event in record["trajectory"][1:]:
        if event["valid"] and float(event["score"]) > current + epsilon:
            selected = event
            current = float(event["score"])
    return selected


def _material_acceptance_audit(record: dict[str, Any]) -> dict[str, Any]:
    strict = next(
        event for event in record["trajectory"]
        if int(event["step"]) == record["selected_step"]
    )
    epsilon = _epsilon_selected_event(record, MATERIAL_SELECTION_EPSILON)
    deltas = {
        field: float(strict[field]) - float(epsilon[field])
        for field in SCIENCE_AXES
    }
    positive_material = [
        field for field, value in deltas.items()
        if value > MATERIAL_SCIENCE_AXIS_DELTA
    ]
    negative_material = [
        field for field, value in deltas.items()
        if value < -MATERIAL_SCIENCE_AXIS_DELTA
    ]
    return {
        "selection_epsilon": MATERIAL_SELECTION_EPSILON,
        "science_axis_materiality_threshold": MATERIAL_SCIENCE_AXIS_DELTA,
        "strict_selected_step": int(strict["step"]),
        "epsilon_selected_step": int(epsilon["step"]),
        "strict_selected_candidate_sha256": strict["candidate_sha256"],
        "epsilon_selected_candidate_sha256": epsilon["candidate_sha256"],
        "strict_selection_score_gain": (
            float(strict["score"]) - float(epsilon["score"])
        ),
        "strict_minus_epsilon_science_axes": deltas,
        "materially_improved_axes": positive_material,
        "materially_regressed_axes": negative_material,
        "epsilon_changes_selected_artifact": (
            strict["candidate_sha256"] != epsilon["candidate_sha256"]
        ),
        "scientifically_material_tradeoff": bool(
            positive_material and negative_material
        ),
        "strict_artifact_pareto_dominates_epsilon_artifact": bool(
            positive_material and not negative_material
        ),
        "epsilon_artifact_pareto_dominates_strict_artifact": bool(
            negative_material and not positive_material
        ),
    }


def _selected_contrast(normal: dict[str, Any], blind: dict[str, Any]) -> dict[str, Any]:
    result = {
        field: (
            float(normal["selected_metrics"][field])
            - float(blind["selected_metrics"][field])
        )
        for field in SCIENCE_AXES
    }
    result.update({
        "selection_score": normal["best_score"] - blind["best_score"],
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "wall_seconds": normal["wall_seconds"] - blind["wall_seconds"],
    })
    return result


def _analyze_records(
    calibration: dict[str, Any], records: dict[str, dict[str, Any]],
    runtime_source_equivalent: bool = True,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    llm_conditions = {
        record["llm_condition_sha256"] for record in records.values()
    }
    audit = _material_acceptance_audit(normal)
    contrast = _selected_contrast(normal, blind)
    normal_steps = {event["step"]: event for event in normal["trajectory"]}
    step_two = normal_steps[2]
    step_three = normal_steps[3]

    execution_passed = bool(
        runtime_source_equivalent
        and revisions == {EXPECTED_MODEL_SOURCE_REVISION}
        and len(scopes) == 1
        and len(llm_conditions) == 1
        and None not in llm_conditions
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
        and one["selected_step"] == 1
        and normal["selected_step"] == 3
        and blind["selected_step"] == 2
        and one["best_score"] > 0.999
        and one["selected_metrics"]["robustness_score"] > 0.999
        and one["selected_metrics"]["heldout_robustness_score"] > 0.999
        and normal["infrastructure_failure_count"] == 1
        and step_two["accepted"] and step_three["accepted"]
        and audit["epsilon_changes_selected_artifact"]
        and 0.0 < audit["strict_selection_score_gain"] < MATERIAL_SELECTION_EPSILON
        and audit["scientifically_material_tradeoff"]
        and audit["strict_minus_epsilon_science_axes"][
            "robustness_score"
        ] < -0.25
        and audit["strict_minus_epsilon_science_axes"][
            "heldout_robustness_score"
        ] > 0.05
        and blind["best_score"] > 0.999
        and blind["proposal_valid_count"] == 3
        and contrast["oracle_calls"] == 0
        and contrast["total_tokens"] != 0
        and calibration["secure_vs_authoritative_direct_axis_comparison"][
            "passed"
        ]
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "HARTREE_FOCK_SINGLE_RUN_CALIBRATION_NOT_CAUSAL_POPULATION_OR_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_model_source_revision": (
            next(iter(revisions)) if len(revisions) == 1 else None
        ),
        "input_task_runtime_source_equivalent": bool(runtime_source_equivalent),
        "input_source_scope_equivalent": len(scopes) == 1,
        "input_llm_condition_equivalent": len(llm_conditions) == 1,
        "task_calibration": calibration,
        "records": records,
        "normal_material_acceptance_audit": audit,
        "normal_minus_blind_selected_contrast": contrast,
        "observed_proposal_pattern": {
            "budget_one_near_ceiling": one["best_score"] > 0.999,
            "blind_open_loop_near_ceiling": blind["best_score"] > 0.999,
            "normal_valid_proposal_count": normal["proposal_valid_count"],
            "normal_infrastructure_failure_count": normal[
                "infrastructure_failure_count"
            ],
            "normal_step_two_selection_score": step_two["score"],
            "normal_step_three_selection_score": step_three["score"],
            "normal_step_two_development_robustness": step_two[
                "robustness_score"
            ],
            "normal_step_three_development_robustness": step_three[
                "robustness_score"
            ],
            "normal_step_two_heldout_robustness": step_two[
                "heldout_robustness_score"
            ],
            "normal_step_three_heldout_robustness": step_three[
                "heldout_robustness_score"
            ],
        },
        "descriptive_findings": {
            "known_algorithm_synthesis_saturates_at_budget_one": (
                one["best_score"] > 0.999
                and one["selected_metrics"]["robustness_score"] > 0.999
            ),
            "feedback_not_shown_necessary_by_open_loop_calibration": (
                blind["best_score"] > 0.999
            ),
            "strict_positive_acceptance_changes_selected_artifact_below_epsilon": (
                audit["epsilon_changes_selected_artifact"]
            ),
            "sub_epsilon_visible_gain_crosses_material_science_tradeoff": (
                audit["scientifically_material_tradeoff"]
            ),
            "normal_and_blind_are_oracle_call_matched": (
                contrast["oracle_calls"] == 0
            ),
            "normal_and_blind_are_not_token_matched": (
                contrast["total_tokens"] != 0
            ),
        },
        "limitations": [
            "Each condition has one run; no confidence interval, population estimate, leaderboard or scaling-law claim is supported.",
            "The Azure endpoint exposes no server-side generation seed, so equal local seed labels do not pair model randomness.",
            "Normal and selection-blind are oracle-call matched but not token-, context- or wall-time-matched; their contrast is descriptive, not causal.",
            "Budget one uses a different local seed label and is an independent calibration, not a prefix of budget three.",
            "The epsilon replay changes endpoint selection only; it does not reconstruct the counterfactual proposals a different online parent policy would have generated.",
            "Held-out, geometry-shift, representation, stability and per-instance metrics were sealed from proposal and selection state.",
            "Near-ceiling programs synthesize known multistart/stability-search methods; these runs do not establish novel chemistry, feedback learning or autonomous scientific discovery.",
            "The task remains a public finite-basis RHF benchmark without external instability, basis convergence, correlated-method or physical validation.",
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
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
