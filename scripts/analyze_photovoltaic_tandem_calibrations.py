#!/usr/bin/env python3
"""Bind and analyze the three PhotovoltaicTandemDesign GPT-5.5 runs.

Each condition is one descriptive calibration. Equal local seed labels do not
control Azure generation randomness, so normal versus selection-blind
differences are not feedback effects, model rankings or scaling-law evidence.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
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


TASK = "Photovoltaics/PhotovoltaicTandemDesign"
CALIBRATION = "experiments/photovoltaic_tandem_v1_calibration_2026-07-25.json"
REPORTS = {
    "budget_one": (
        "experiments/gpt55_photovoltaic_tandem_v1_b1_2026-07-25.json"
    ),
    "normal_budget_three": (
        "experiments/gpt55_photovoltaic_tandem_v1_b3_2026-07-25.json"
    ),
    "blind_budget_three": (
        "experiments/gpt55_photovoltaic_tandem_v1_blind_b3_2026-07-25.json"
    ),
}
INPUT_SOURCE_REVISION = "e57bb682930d65c39699b2153e8743063587b97e"
CALIBRATION_SOURCE_REVISION = "0c0ca5ea21e6be5a58929e336b4c5dfbf0eddb55"
TASK_RUNTIME_SCOPE = (
    ":(glob)sle/**/*.py",
    "benchmarks/Chemistry/PhotovoltaicTandemDesign",
    "requirements-upstream.txt",
)
SCIENCE_FIELDS = (
    "combined_score",
    "raw_score",
    "robustness_score",
    "heldout_policy_score",
    "heldout_robustness_score",
    "feasibility_rate",
    "heldout_feasibility_rate",
    "development_mean_nominal_efficiency",
    "heldout_mean_nominal_efficiency",
    "development_minimum_shift_efficiency",
    "heldout_minimum_shift_efficiency",
    "development_mean_current_matching_ratio",
    "heldout_mean_current_matching_ratio",
    "development_mean_cost_utilization",
    "heldout_mean_cost_utilization",
    "development_mean_junction_count",
    "heldout_mean_junction_count",
    "candidate_instance_call_count",
    "candidate_instance_valid_rate",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _science(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in SCIENCE_FIELDS}


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, TASK_RUNTIME_SCOPE, root=ROOT)


def _failure_kind(event: dict[str, Any]) -> str | None:
    metrics = event.get("metrics") or {}
    value = metrics.get("candidate_failure_kind")
    return str(value) if isinstance(value, str) and value else None


def _shortcut_scan(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    strings = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Str)
    }
    forbidden_literals = {
        "5101", "5102", "5103", "5104", "5105",
        "6101", "6102", "6103",
    }
    literal_hits = sorted(forbidden_literals & strings)
    forbidden_terms = sorted(term for term in (
        "verification", "evaluator", "NOMINAL_REFERENCE_DESIGNS",
        "ROBUST_REFERENCE_DESIGNS", "_reference_submission",
    ) if term in source)
    return {
        "source_sha256": _sha256(path),
        "fixed_world_literal_hits": literal_hits,
        "evaluator_source_term_hits": forbidden_terms,
        "passed": not literal_hits and not forbidden_terms,
    }


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    weak = document.get("weak_baseline") or {}
    nominal = document.get("nominal_reference_policy") or {}
    robust = document.get("robust_reference_policy") or {}
    ideal = document.get("independent_ideal_limits") or []
    if not (
        document.get("execution_passed") is True
        and document.get("passed") is True
        and document.get("trusted_evidence") is True
        and provenance.get("git_revision") == CALIBRATION_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and document.get("spectrum_row_count") == 2002
        and document.get("spectrum_generated_sha256")
        == "eeb37120e14ad2fbb5e986d63b5f7711fbf622a03ebf67edabea618df397a728"
        and abs(float(document.get("spectrum_global_tilt_integral_w_m2", 0.0))
                - 1000.3706555734423) < 1e-10
        and len(ideal) == 4
        and float(document.get(
            "maximum_independent_runtime_efficiency_gap", 1.0
        )) < 2e-10
        and float(document.get("minimum_nominal_headroom", 0.0)) > 0.02
        and float(document.get("minimum_robust_headroom", 0.0)) > 0.02
        and document.get("nominal_reference_junction_counts_by_budget_option")
        == [[1], [2, 3], [3, 4]]
        and document.get("robust_reference_junction_counts_by_budget_option")
        == [[1], [2], [3]]
        and weak.get("valid") == 1.0
        and weak.get("combined_score") == 0.0
        and nominal.get("combined_score") == 1.0
        and nominal.get("heldout_policy_score") == 1.0
        and robust.get("robustness_score") == 1.0
        and robust.get("heldout_robustness_score") == 1.0
    ):
        raise ValueError("PhotovoltaicTandemDesign task calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "evidence_scope": document["evidence_scope"],
        "spectrum_generated_sha256": document["spectrum_generated_sha256"],
        "independent_ideal_efficiencies": [
            row["independent_efficiency"] for row in ideal
        ],
        "maximum_independent_runtime_efficiency_gap": document[
            "maximum_independent_runtime_efficiency_gap"
        ],
        "minimum_nominal_headroom": document["minimum_nominal_headroom"],
        "minimum_robust_headroom": document["minimum_robust_headroom"],
        "nominal_reference_junction_counts_by_budget_option": document[
            "nominal_reference_junction_counts_by_budget_option"
        ],
        "robust_reference_junction_counts_by_budget_option": document[
            "robust_reference_junction_counts_by_budget_option"
        ],
        "weak_baseline": _science(weak),
        "nominal_reference_policy": _science(nominal),
        "robust_reference_policy": _science(robust),
        "limitations": document.get("limitations") or [],
    }


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


def _load_model(label: str, relative: str) -> dict[str, Any]:
    report_path = ROOT / relative
    document = json.loads(report_path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("passed") is True
        and document.get("trusted_evidence") is True
        and provenance.get("git_revision") == INPUT_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
    ):
        raise ValueError("untrusted photovoltaic model report: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one successful photovoltaic run")
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
        and run.get("seed") == expected_seed
        and config.get("budget") == expected_budget
        and config.get("llm", {}).get("model") == "gpt-5.5"
        and config.get("llm", {}).get("server_side_seed_control") is False
    ):
        raise ValueError("unexpected photovoltaic calibration condition")

    workdir = Path(run["workdir"]).resolve()
    try:
        relative_workdir = workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("photovoltaic workdir is outside repository") from exc
    trajectory_path = workdir / "trajectory.jsonl"
    raw_events = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable photovoltaic snapshot differs from raw trajectory")
    if len(raw_events) != expected_budget + 1:
        raise ValueError("photovoltaic trajectory is incomplete")

    trajectory = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
            and int(compact["step"]) == int(raw["step"])
        ):
            raise ValueError("raw and portable photovoltaic lineage differs")
        metrics = raw.get("metrics") or {}
        science = _science(metrics)
        if any(
            value is not None and not _finite_number(value)
            for value in science.values()
        ):
            raise ValueError("photovoltaic science metric is non-finite")
        per_instance = metrics.get("per_instance") or []
        if metrics.get("valid") == 1.0 and len(per_instance) != 8:
            raise ValueError("valid photovoltaic event lacks all eight regimes")
        trajectory.append({
            "step": int(raw["step"]),
            "oracle_calls": int(raw["oracle_calls"]),
            "budget_units": int(raw["budget_units"]),
            "score": float(raw["score"]),
            "best_score": float(raw["best_score"]),
            "valid": bool(raw.get("valid")) and metrics.get("valid") == 1.0,
            "accepted": bool(raw["accepted"]),
            "candidate_sha256": raw["candidate_sha256"],
            "parent_sha256": raw["parent_sha256"],
            "failure_kind": _failure_kind(raw),
            "infrastructure_failure": bool(metrics.get("infrastructure_failure")),
            "science_metrics": science,
            "valid_regime_count": sum(bool(row.get("valid")) for row in per_instance),
            "invalid_regime_count": sum(not bool(row.get("valid")) for row in per_instance),
            "llm": raw.get("llm") or {},
            "algorithm_metadata": raw.get("algorithm_metadata") or {},
        })

    summary = run.get("summary") or {}
    manifest_path = workdir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if expected_mode == "selection_blind" else "online_incumbent"
    )
    best_program = workdir / "best_program.py"
    terminal_program = workdir / "solution.py"
    best_hash = _sha256(best_program)
    selected_events = [
        event for event in trajectory if event["candidate_sha256"] == best_hash
    ]
    if len(selected_events) != 1:
        raise ValueError("photovoltaic best program does not bind one event")
    selected = selected_events[0]
    proposals = trajectory[1:]
    failure_counts: dict[str, int] = {}
    for event in proposals:
        if event["failure_kind"]:
            failure_counts[event["failure_kind"]] = (
                failure_counts.get(event["failure_kind"], 0) + 1
            )
    record = {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(report_path),
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "llm_condition_sha256": config.get("llm_condition_sha256"),
        "model": config.get("llm", {}).get("model"),
        "server_side_seed_control": False,
        "feedback_mode": expected_mode,
        "feedback_scope": summary.get("feedback_scope"),
        "selection_policy": summary.get("selection_policy"),
        "seed": expected_seed,
        "proposal_budget": expected_budget,
        "oracle_calls": int(summary["oracle_calls"]),
        "budget_units": int(summary["budget_units"]),
        "llm_calls": int(summary["llm"]["calls"]),
        "provider_usage_records": int(summary["llm"]["provider_usage_records"]),
        "input_tokens": summary["llm"].get("input_tokens"),
        "output_tokens": summary["llm"].get("output_tokens"),
        "total_tokens": summary["llm"].get("total_tokens"),
        "wall_seconds": float(summary["wall_seconds"]),
        "baseline_score": float(run["baseline"]),
        "best_score": float(run["best"]),
        "best_so_far_auc": float(summary["best_so_far_auc"]),
        "accepted_proposals": int(run["accepted"]),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "run_manifest_sha256": _sha256(manifest_path),
        "task_contract_sha256": manifest.get("task_contract_sha256"),
        "runtime_source_sha256": manifest.get("runtime_source_sha256"),
        "best_program": str(relative_workdir / "best_program.py"),
        "best_program_sha256": best_hash,
        "terminal_program": str(relative_workdir / "solution.py"),
        "terminal_program_sha256": _sha256(terminal_program),
        "selected_step": selected["step"],
        "selected_candidate_sha256": selected["candidate_sha256"],
        "selected_metrics": selected["science_metrics"],
        "terminal_candidate_sha256": trajectory[-1]["candidate_sha256"],
        "proposal_count": len(proposals),
        "valid_proposal_count": sum(event["valid"] for event in proposals),
        "invalid_proposal_count": sum(not event["valid"] for event in proposals),
        "valid_nonzero_proposal_count": sum(
            event["valid"] and event["score"] > 0.0 for event in proposals
        ),
        "failure_counts": failure_counts,
        "infrastructure_failure_count": sum(
            event["infrastructure_failure"] for event in proposals
        ),
        "trajectory": trajectory,
        "fixed_world_shortcut_scan": _shortcut_scan(best_program),
        "artifact_retention_scope": (
            "best and terminal sources are retained; intermediate proposal sources "
            "are not retained, but hashes, parent lineage, metrics and accounting remain bound"
        ),
    }
    record["integrity_passed"] = bool(
        _lineage_is_valid(record)
        and record["selection_policy"] == expected_policy
        and record["oracle_calls"] == expected_budget + 1
        and record["budget_units"] == expected_budget + 1
        and record["llm_calls"] == expected_budget
        and record["provider_usage_records"] == expected_budget
        and int(run["evaluated"]) == expected_budget + 1
        and record["accepted_proposals"] == int(run["accepted"])
        and abs(record["best_score"] - selected["score"]) < 1e-12
        and selected["valid"]
        and selected["valid_regime_count"] == 8
        and record["terminal_program_sha256"] == record["terminal_candidate_sha256"]
        and record["fixed_world_shortcut_scan"]["passed"]
        and record["infrastructure_failure_count"] == 0
        and manifest.get("task_id") == TASK
        and manifest.get("feedback_mode") == expected_mode
        and manifest.get("seed") == expected_seed
        and manifest.get("llm_condition_sha256")
        == config.get("llm_condition_sha256")
    )
    if not record["integrity_passed"]:
        raise ValueError("photovoltaic lineage, artifact or accounting gate failed")
    return record


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    runtime_source_equivalent: bool = True,
    runtime_source_changes: list[str] | None = None,
    calibration_source_revision: str = CALIBRATION_SOURCE_REVISION,
    model_source_revision: str = INPUT_SOURCE_REVISION,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    conditions = {record["llm_condition_sha256"] for record in records.values()}
    contracts = {record["task_contract_sha256"] for record in records.values()}
    runtimes = {record["runtime_source_sha256"] for record in records.values()}
    proposals = [
        event for record in records.values() for event in record["trajectory"][1:]
    ]
    contrast = {
        field: (
            normal["selected_metrics"][field]
            - blind["selected_metrics"][field]
        )
        for field in SCIENCE_FIELDS
    }
    contrast.update({
        "best_score": normal["best_score"] - blind["best_score"],
        "best_so_far_auc": normal["best_so_far_auc"] - blind["best_so_far_auc"],
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "wall_seconds": normal["wall_seconds"] - blind["wall_seconds"],
        "valid_proposal_count": (
            normal["valid_proposal_count"] - blind["valid_proposal_count"]
        ),
    })
    selected = [record["selected_metrics"] for record in records.values()]
    execution_passed = bool(
        calibration["source_revision"] == calibration_source_revision
        and revisions == {model_source_revision}
        and runtime_source_equivalent
        and len(scopes) == 1
        and len(conditions) == 1
        and None not in conditions
        and len(contracts) == 1
        and None not in contracts
        and len(runtimes) == 1
        and None not in runtimes
        and all(record["integrity_passed"] for record in records.values())
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["seed"] == 0
        and normal["seed"] == blind["seed"] == 1
        and one["feedback_mode"] == normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and one["oracle_calls"] == 2
        and normal["oracle_calls"] == blind["oracle_calls"] == 4
        and len(proposals) == 7
        and sum(event["valid"] for event in proposals) == 5
        and sum(event["infrastructure_failure"] for event in proposals) == 0
        and all(metrics["combined_score"] > 0.99 for metrics in selected)
        and all(metrics["heldout_policy_score"] > 0.98 for metrics in selected)
        and max(metrics["robustness_score"] for metrics in selected) < 0.91
        and max(metrics["heldout_robustness_score"] for metrics in selected) < 0.83
        and all(metrics["development_mean_cost_utilization"] > 0.99
                for metrics in selected)
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "REDUCED_ORDER_TANDEM_PV_SINGLE_RUN_GPT55_CALIBRATION_NOT_"
            "FEEDBACK_CAUSAL_POPULATION_DEVICE_MATERIAL_RECORD_EFFICIENCY_"
            "MANUFACTURING_EXPERIMENTAL_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "model_source_revision": model_source_revision,
        "input_task_runtime_source_equivalent": runtime_source_equivalent,
        "input_task_runtime_source_changes": runtime_source_changes or [],
        "input_source_scope_equivalent": len(scopes) == 1,
        "input_llm_condition_equivalent": len(conditions) == 1,
        "input_task_contract_equivalent": len(contracts) == 1,
        "input_runtime_manifest_equivalent": len(runtimes) == 1,
        "task_calibration": calibration,
        "records": records,
        "proposal_hurdle_summary": {
            "proposal_count": len(proposals),
            "valid_proposal_count": sum(event["valid"] for event in proposals),
            "invalid_proposal_count": sum(not event["valid"] for event in proposals),
            "valid_nonzero_proposal_count": sum(
                event["valid"] and event["score"] > 0.0 for event in proposals
            ),
            "candidate_runtime_error_count": sum(
                event["failure_kind"] == "candidate_runtime_error"
                for event in proposals
            ),
            "infrastructure_failure_count": sum(
                event["infrastructure_failure"] for event in proposals
            ),
            "retained_best_source_count": len(records),
            "retained_terminal_source_count": len(records),
            "unretained_intermediate_source_count": (
                len(proposals) - len(records)
            ),
        },
        "normal_minus_blind_budget_three_descriptive_contrast": contrast,
        "descriptive_findings": {
            "all_selected_artifacts_near_saturate_nominal_development": all(
                metrics["combined_score"] > 0.99 for metrics in selected
            ),
            "all_selected_artifacts_transfer_nominally_to_heldout": all(
                metrics["heldout_policy_score"] > 0.98 for metrics in selected
            ),
            "all_selected_artifacts_leave_sealed_robustness_headroom": all(
                metrics["robustness_score"] < 0.91
                and metrics["heldout_robustness_score"] < 0.83
                for metrics in selected
            ),
            "all_selected_artifacts_use_nearly_full_cost": all(
                metrics["development_mean_cost_utilization"] > 0.99
                for metrics in selected
            ),
            "budget_one_has_highest_normal_selected_score": (
                one["best_score"] > normal["best_score"]
            ),
            "blind_has_highest_selected_score": (
                blind["best_score"] > max(one["best_score"], normal["best_score"])
            ),
            "normal_and_blind_are_oracle_call_matched": contrast["oracle_calls"] == 0,
            "normal_and_blind_are_token_matched": contrast["total_tokens"] == 0,
            "feedback_effect_identified": False,
            "device_or_experimental_validity_demonstrated": False,
        },
        "limitations": [
            "Each condition has one run; no confidence interval, population, leaderboard, model-ranking or scaling-law estimate is supported.",
            "The Azure endpoint exposes no server-side generation seed, so equal local seed labels do not pair model randomness.",
            "Normal and selection-blind match oracle calls but differ in tokens, prompts, histories and wall time; their contrast is descriptive, not causal.",
            "Selection-blind performs offline best-of-three selection over proposals that all see the frozen baseline; it is not a deployed sequential policy.",
            "Budget one uses a different local seed label and is an independent calibration, not a prefix of budget three.",
            "Robustness, held-out transfer, efficiency, current matching, cost, junction count and per-regime metrics were evaluator-only.",
            "Full cost utilization is observed alongside a robustness gap but does not cause it: sealed shifts change physical performance, not the fabrication-cost envelope.",
            "The task lacks explicit cost-overrun or shifted-feasibility margins; a complete scientific-instrument margin experiment remains unimplemented.",
            "The public reduced-order detailed-balance model omits non-radiative recombination, transport, interfaces, tunnel junctions, luminescent coupling, resistance, thermal balance, real materials and manufacturing yield.",
            "The selected programs optimize a known public model; they do not discover a new photovoltaic mechanism, material or device.",
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
    changes = _source_changes(CALIBRATION_SOURCE_REVISION, INPUT_SOURCE_REVISION)
    return _analyze_records(
        calibration,
        records,
        runtime_source_equivalent=not changes,
        runtime_source_changes=changes,
    )


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
