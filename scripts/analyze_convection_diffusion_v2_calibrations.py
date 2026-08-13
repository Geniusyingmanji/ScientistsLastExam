#!/usr/bin/env python3
"""Bind and analyze ConvectionDiffusionOpt-v2 GPT-5.5 calibrations.

The three model conditions are single-run task calibrations.  This analyzer
checks their source and LLM condition, replays raw trajectory lineage, retains
protocol failures separately from valid scientific abstentions, and compares
the model proposals with the calibrated one- and two-experiment policies.
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

from sle.protocol import (  # noqa: E402
    compact_trajectory_snapshot,
    load_trajectory,
)
from sle.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)
from sle.runtime_migration import runtime_source_changes  # noqa: E402


TASK = "HeatTransfer/ConvectionDiffusionOpt"
CALIBRATION = "experiments/convection_diffusion_v2_calibration_2026-07-23.json"
REPORTS = {
    "budget_one": "experiments/gpt55_convection_diffusion_v2_b1_2026-07-23.json",
    "normal_budget_three": "experiments/gpt55_convection_diffusion_v2_b3_2026-07-23.json",
    "blind_budget_three": (
        "experiments/gpt55_convection_diffusion_v2_blind_b3_2026-07-23.json"
    ),
}
EXPECTED_MODEL_SOURCE_REVISION = "01ce0456c35656d285cede873ff46256bdba75ef"
TASK_RUNTIME_SCOPE = (
    "sle",
    "benchmarks/Engineering/ConvectionDiffusionOpt",
    "requirements-upstream.txt",
)
FIELDS = (
    "combined_score", "valid", "feasibility_rate", "raw_score",
    "mechanism_score", "development_prediction_score",
    "development_design_score", "development_robust_design_score",
    "development_design_utility", "development_robust_design_utility",
    "robustness_score", "development_validation_gap",
    "heldout_policy_score", "heldout_mechanism_score",
    "heldout_prediction_score", "heldout_design_score",
    "heldout_robust_design_score", "heldout_design_utility",
    "heldout_robust_design_utility", "heldout_robustness_score",
    "development_supported_claim_coverage",
    "heldout_supported_claim_coverage",
    "development_false_discovery_rate", "heldout_false_discovery_rate",
    "development_correct_refusal_rate", "heldout_correct_refusal_rate",
    "development_confidence_calibration_score",
    "heldout_confidence_calibration_score",
    "development_mean_experiment_calls", "heldout_mean_experiment_calls",
    "development_mean_budget_units", "heldout_mean_budget_units",
    "heldout_feasibility_rate", "candidate_world_call_count",
    "candidate_world_valid_rate", "candidate_failure_kind", "error_message",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, TASK_RUNTIME_SCOPE, root=ROOT)


def _scalar(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in FIELDS}


def _world_summary(worlds: Any) -> dict[str, Any] | None:
    if not isinstance(worlds, list) or len(worlds) != 11:
        return None
    supported = [row for row in worlds if row.get("kind") == "in_library"]
    unsupported = [row for row in worlds if row.get("kind") != "in_library"]
    valid = [row for row in worlds if bool(row.get("valid"))]
    claims = [row for row in supported if not bool(row.get("abstain"))]
    return {
        "world_count": len(worlds),
        "valid_world_count": len(valid),
        "supported_world_count": len(supported),
        "supported_claim_count": len(claims),
        "supported_claim_coverage": len(claims) / len(supported),
        "mean_supported_mechanism_quality": (
            sum(float(row.get("mechanism_quality", 0.0)) for row in supported)
            / len(supported)
        ),
        "unsupported_world_count": len(unsupported),
        "unsupported_correct_refusal_rate": (
            sum(bool(row.get("correct_refusal")) for row in unsupported)
            / len(unsupported)
        ),
        "unsupported_false_discovery_rate": (
            sum(bool(row.get("false_discovery")) for row in unsupported)
            / len(unsupported)
        ),
        "all_worlds_abstained": all(bool(row.get("abstain")) for row in worlds),
        "failure_kinds": dict(Counter(
            str(row["failure_kind"]) for row in worlds
            if row.get("failure_kind")
        )),
    }


def _failure_kind(metrics: dict[str, Any], error: Any) -> str | None:
    if metrics.get("candidate_failure_kind"):
        return str(metrics["candidate_failure_kind"])
    message = str(error or metrics.get("error_message") or "")
    if "invalid_experiment_request" in message:
        return "invalid_experiment_request"
    if message:
        return "other_candidate_protocol_error"
    return None


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    baseline = document.get("always_abstain_baseline") or {}
    one = document.get("truth_blind_one_experiment_policy") or {}
    two = document.get("truth_blind_two_experiment_policy") or {}
    exact = document.get("exact_mechanism_replayable_design_reference") or {}
    gate = document.get("difficulty_gate") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and document.get("task_dimensions") == {
            "grid_shape": [25, 25],
            "parameter_count": 5,
            "design_source_count": 4,
            "development_world_count": 6,
            "heldout_world_count": 5,
            "shift_count": 4,
            "experiment_budget_units": 12,
        }
        and baseline.get("combined_score") == 0.0
        and one.get("combined_score") == 0.0
        and float(one.get("heldout_policy_score", 1.0)) < 1.0e-12
        and float(two.get("combined_score", 0.0)) > 0.89
        and float(two.get("heldout_policy_score", 0.0)) > 0.89
        and float(two.get("robustness_score", 0.0)) > 0.89
        and float(two.get("heldout_robustness_score", 0.0)) > 0.89
        and two.get("development_false_discovery_rate") == 0.0
        and two.get("heldout_false_discovery_rate") == 0.0
        and exact.get("combined_score") == 1.0
        and exact.get("heldout_policy_score") == 1.0
        and gate.get("passed") is True
    ):
        raise ValueError("ConvectionDiffusionOpt-v2 task calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "task_dimensions": document["task_dimensions"],
        "always_abstain_metrics": _scalar(baseline),
        "one_experiment_metrics": _scalar(one),
        "two_experiment_metrics": _scalar(two),
        "exact_reference_metrics": _scalar(exact),
        "difficulty_gate": gate,
        "maximum_single_experiment_condition_number": max(
            float(row["jacobian_condition_number"])
            for row in document["single_experiment_ambiguity_checks"]
        ),
    }


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
        raise ValueError("expected one successful model run: %s" % relative)
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
        and (config.get("llm") or {}).get("wire") == "responses"
        and (config.get("llm") or {}).get("model") == "gpt-5.5"
        and (config.get("llm") or {}).get("server_side_seed_control") is False
    ):
        raise ValueError("unexpected model condition: %s" % relative)

    workdir = Path(run["workdir"]).resolve()
    try:
        relative_workdir = workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("model workdir is outside repository") from exc
    trajectory_path = workdir / "trajectory.jsonl"
    raw_events = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable snapshot differs from raw trajectory: %s" % relative)

    trajectory = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            int(compact["step"]) == int(raw["step"])
            and compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
        ):
            raise ValueError("raw/compact trajectory lineage differs")
        metrics = raw.get("metrics") or {}
        trajectory.append({
            "step": int(raw["step"]),
            "score": float(raw["score"]),
            "best_score": float(raw["best_score"]),
            "valid": bool(raw["valid"]),
            "accepted": bool(raw["accepted"]),
            "candidate_sha256": raw["candidate_sha256"],
            "parent_sha256": raw["parent_sha256"],
            "failure_kind": _failure_kind(metrics, raw.get("error")),
            "world_summary": _world_summary(metrics.get("per_world")),
            **_scalar(metrics),
        })

    record = {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(report_path),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "llm_condition_sha256": config.get("llm_condition_sha256"),
        "feedback_mode": run["feedback_mode"],
        "feedback_scope": (run.get("summary") or {}).get("feedback_scope"),
        "selection_policy": (run.get("summary") or {}).get("selection_policy"),
        "seed": int(run["seed"]),
        "proposal_budget": int(config["budget"]),
        "oracle_calls": int(run["summary"]["oracle_calls"]),
        "total_tokens": int(run["summary"]["llm"]["total_tokens"]),
        "best_score": float(run["best"]),
        "selected_step": max(
            int(event["step"]) for event in trajectory if event["accepted"]
        ),
        "best_program": str(relative_workdir / "best_program.py"),
        "trajectory": trajectory,
    }
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if expected_mode == "selection_blind" else "online_incumbent"
    )
    selected = next(
        event for event in trajectory if event["step"] == record["selected_step"]
    )
    if not (
        _lineage_is_valid(record)
        and record["selection_policy"] == expected_policy
        and int(run["evaluated"]) == record["oracle_calls"]
        and int(raw_events[-1]["oracle_calls"]) == record["oracle_calls"]
        and abs(selected["score"] - record["best_score"]) <= 1.0e-12
        and _sha256(workdir / "best_program.py") == selected["candidate_sha256"]
    ):
        raise ValueError("model lineage, accounting or selected artifact gate failed")
    return record


def _proposal_summary(record: dict[str, Any]) -> dict[str, Any]:
    proposals = record["trajectory"][1:]
    failures = Counter(
        event["failure_kind"] for event in proposals if event["failure_kind"]
    )
    valid = [event for event in proposals if event["valid"]]
    return {
        "proposal_count": len(proposals),
        "valid_proposal_count": len(valid),
        "invalid_proposal_count": len(proposals) - len(valid),
        "failure_counts": dict(failures),
        "valid_proposal_experiment_calls": [
            event["development_mean_experiment_calls"] for event in valid
        ],
        "valid_proposal_experiment_budget_units": [
            event["development_mean_budget_units"] for event in valid
        ],
        "valid_proposal_all_worlds_abstained": [
            event["world_summary"]["all_worlds_abstained"] for event in valid
        ],
    }


def _valid_proposal_is_conservative_failure(event: dict[str, Any]) -> bool:
    worlds = event.get("world_summary") or {}
    return bool(
        event.get("valid")
        and event.get("combined_score") == 0.0
        and event.get("mechanism_score") == 0.0
        and event.get("development_supported_claim_coverage") == 0.0
        and event.get("heldout_supported_claim_coverage") == 0.0
        and event.get("development_false_discovery_rate") == 0.0
        and event.get("heldout_false_discovery_rate") == 0.0
        and event.get("development_correct_refusal_rate") == 1.0
        and event.get("heldout_correct_refusal_rate") == 1.0
        and worlds.get("supported_claim_coverage") == 0.0
        and worlds.get("unsupported_correct_refusal_rate") == 1.0
        and worlds.get("unsupported_false_discovery_rate") == 0.0
        and worlds.get("all_worlds_abstained") is True
    )


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    runtime_source_equivalent: bool = True,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    conditions = {record["llm_condition_sha256"] for record in records.values()}
    proposals = {
        label: record["trajectory"][1:] for label, record in records.items()
    }
    all_proposals = [event for rows in proposals.values() for event in rows]
    valid_proposals = [event for event in all_proposals if event["valid"]]
    summaries = {label: _proposal_summary(record) for label, record in records.items()}
    classical = calibration["two_experiment_metrics"]
    execution_passed = bool(
        runtime_source_equivalent
        and revisions == {EXPECTED_MODEL_SOURCE_REVISION}
        and len(scopes) == 1
        and len(conditions) == 1
        and None not in conditions
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["seed"] == 0
        and normal["seed"] == blind["seed"] == 1
        and one["feedback_mode"] == normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and one["oracle_calls"] == 2
        and normal["oracle_calls"] == blind["oracle_calls"] == 4
        and all(record["best_score"] == 0.0 for record in records.values())
        and all(record["selected_step"] == 0 for record in records.values())
        and all(_lineage_is_valid(record) for record in records.values())
        and all(not event["accepted"] for event in all_proposals)
        and len(all_proposals) == 7
        and len(valid_proposals) == 3
        and all(_valid_proposal_is_conservative_failure(event)
                for event in valid_proposals)
        and summaries["budget_one"]["failure_counts"]
        == {"invalid_experiment_request": 1}
        and summaries["normal_budget_three"]["failure_counts"]
        == {"candidate_runtime_error": 2}
        and summaries["blind_budget_three"]["failure_counts"]
        == {"candidate_runtime_error": 1}
        and 12.0 in summaries["blind_budget_three"][
            "valid_proposal_experiment_budget_units"
        ]
        and float(classical["combined_score"]) > 0.89
        and float(classical["heldout_policy_score"]) > 0.89
        and float(classical["mechanism_score"]) > 0.64
        and float(classical["heldout_mechanism_score"]) > 0.65
        and normal["total_tokens"] != blind["total_tokens"]
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "CONVECTION_DIFFUSION_SINGLE_RUN_CALIBRATION_NOT_CAUSAL_"
            "POPULATION_PHYSICAL_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_task_source_revision": calibration["source_revision"],
        "input_model_source_revision": (
            next(iter(revisions)) if len(revisions) == 1 else None
        ),
        "input_task_runtime_source_equivalent": bool(runtime_source_equivalent),
        "input_source_scope_equivalent": len(scopes) == 1,
        "input_llm_condition_equivalent": len(conditions) == 1,
        "task_calibration": calibration,
        "records": records,
        "proposal_summary": summaries,
        "normal_minus_blind_diagnostic": {
            "best_score": normal["best_score"] - blind["best_score"],
            "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
            "total_tokens": normal["total_tokens"] - blind["total_tokens"],
            "valid_proposals": (
                summaries["normal_budget_three"]["valid_proposal_count"]
                - summaries["blind_budget_three"]["valid_proposal_count"]
            ),
        },
        "science_vectors": {
            "truth_blind_two_experiment_policy": {
                "optimization_O": classical["combined_score"],
                "fidelity_F": classical["heldout_prediction_score"],
                "mechanism_M": classical["heldout_mechanism_score"],
                "validity_V": classical["heldout_robustness_score"],
                "refusal_R": 1.0 - float(classical["heldout_false_discovery_rate"]),
                "supported_discovery_coverage": classical[
                    "heldout_supported_claim_coverage"
                ],
            },
            "valid_gpt55_nonbaseline_proposals": {
                "proposal_count": len(valid_proposals),
                "optimization_O": 0.0,
                "fidelity_F": 0.0,
                "mechanism_M": 0.0,
                "validity_V": 0.0,
                "refusal_R": 1.0,
                "supported_discovery_coverage": 0.0,
            },
        },
        "limitations": [
            "Each condition has one run; no confidence interval, model ranking, scaling law or causal feedback estimate is supported.",
            "Normal and selection-blind share a local seed identifier, but Azure exposes no server-side generation seed, so generation randomness is not paired.",
            "The budget-three conditions are oracle-call matched and close but not equal in token use; normal used %d fewer tokens." % (blind["total_tokens"] - normal["total_tokens"]),
            "No proposal improved the baseline, so normal never changed its incumbent; the zero normal-minus-blind score contrast contains no feedback-effect information.",
            "Three nonbaseline proposals are protocol-valid, but all three abstain on every supported and unsupported world. Correct unsupported-world refusal therefore coexists with zero supported discovery coverage.",
            "Four proposals fail the executable contract or runtime gate. Protocol validity, experiment design, mechanism inference and scientific refusal must remain separate failure states.",
            "Held-out mechanism, prediction, design, robustness, confidence, refusal and per-world metrics remained sealed from proposal and selection state.",
            "The oracle is a synthetic steady finite-difference laboratory, not a continuum convergence study, conjugate heat-transfer model, physical device or autonomous discovery result.",
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
    report = _analyze_records(calibration, records, runtime_source_equivalent)
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
