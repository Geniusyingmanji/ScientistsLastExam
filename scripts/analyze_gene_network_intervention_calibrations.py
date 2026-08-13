#!/usr/bin/env python3
"""Bind and analyze GeneNetworkIntervention GPT-5.5 calibrations.

The three conditions are one descriptive run each.  This analysis separates
proposal validity, scientific coverage/refusal and selected score; it does not
turn equal local seed labels into a paired generation or feedback experiment.
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

from sle.protocol import compact_trajectory_snapshot, load_trajectory  # noqa: E402
from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402
from sle.runtime_migration import runtime_source_changes  # noqa: E402


TASK = "SystemsBiology/GeneNetworkIntervention"
CALIBRATION = "experiments/gene_network_intervention_calibration_2026-07-24.json"
REPORTS = {
    "budget_one": "experiments/gpt55_gene_network_v1_b1_2026-07-24.json",
    "normal_budget_three": "experiments/gpt55_gene_network_v1_b3_2026-07-24.json",
    "blind_budget_three": (
        "experiments/gpt55_gene_network_v1_blind_b3_2026-07-24.json"
    ),
}
EXPECTED_TASK_SOURCE_REVISION = "b777889d0e394a66e2375bb5d2f4243dae994a62"
EXPECTED_MODEL_SOURCE_REVISION = "a46d254f56978afdd92ee4400abbc7fc457c1720"
TASK_RUNTIME_SCOPE = (
    "sle",
    ":(exclude)sle/certification.yaml",
    "benchmarks/Biology/GeneNetworkIntervention",
    "requirements-upstream.txt",
)
SCIENCE_FIELDS = (
    "development_mechanism_score",
    "development_prediction_score",
    "development_decision_utility",
    "robustness_score",
    "development_transfer_utility",
    "heldout_policy_score",
    "heldout_mechanism_score",
    "heldout_prediction_score",
    "heldout_decision_utility",
    "heldout_robustness_score",
    "heldout_transfer_utility",
    "development_supported_claim_coverage",
    "heldout_supported_claim_coverage",
    "development_unsupported_refusal_rate",
    "heldout_unsupported_refusal_rate",
    "development_false_discovery_rate",
    "heldout_false_discovery_rate",
    "candidate_world_valid_rate",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value == value
        and abs(float(value)) != float("inf")
    )


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, TASK_RUNTIME_SCOPE, root=ROOT)


def _science_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in SCIENCE_FIELDS}


def _failure_kind(event: dict[str, Any]) -> str | None:
    metrics = event.get("metrics") or {}
    explicit = metrics.get("candidate_failure_kind")
    if isinstance(explicit, str) and explicit:
        return explicit
    message = metrics.get("error_message") or event.get("error")
    prefix = "candidate invalid: "
    if isinstance(message, str) and message.startswith(prefix):
        return message[len(prefix):]
    return None


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    baseline = document.get("baseline") or {}
    reference = document.get("truth_blind_nonlinear_reference") or {}
    required_reference = (
        reference.get("valid") == 1.0
        and 0.02 < float(reference.get("combined_score", 0.0)) < 0.98
        and float(reference.get("heldout_policy_score", 0.0)) > 0.02
        and reference.get("development_supported_claim_coverage") == 1.0
        and reference.get("heldout_supported_claim_coverage") == 1.0
        and reference.get("development_unsupported_refusal_rate") == 1.0
        and reference.get("heldout_unsupported_refusal_rate") == 1.0
        and reference.get("development_false_discovery_rate") == 0.0
        and reference.get("heldout_false_discovery_rate") == 0.0
    )
    if not (
        document.get("execution_passed") is True
        and document.get("passed") is True
        and document.get("trusted_evidence") is True
        and provenance.get("git_revision") == EXPECTED_TASK_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and baseline.get("combined_score") == 0.0
        and baseline.get("valid") == 1.0
        and required_reference
    ):
        raise ValueError("GeneNetworkIntervention task calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "baseline": {
            "combined_score": baseline["combined_score"],
            "valid": baseline["valid"],
        },
        "truth_blind_reference": {
            "combined_score": reference["combined_score"],
            "robustness_score": reference["robustness_score"],
            "heldout_policy_score": reference["heldout_policy_score"],
            "heldout_robustness_score": reference["heldout_robustness_score"],
            **_science_metrics(reference),
        },
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
        and provenance.get("git_revision") == EXPECTED_MODEL_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
    ):
        raise ValueError("untrusted gene-network model report: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1:
        raise ValueError("expected exactly one gene-network run")
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
        and config.get("llm", {}).get("server_side_seed_control") is False
    ):
        raise ValueError("unexpected gene-network calibration condition")

    workdir = Path(run["workdir"]).resolve()
    try:
        relative_workdir = workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("gene-network workdir is outside repository") from exc
    trajectory_path = workdir / "trajectory.jsonl"
    raw_events = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable gene-network snapshot differs from raw trajectory")
    if len(raw_events) != expected_budget + 1:
        raise ValueError("gene-network trajectory is incomplete")

    trajectory = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            int(compact["step"]) == int(raw["step"])
            and compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
        ):
            raise ValueError("raw and portable gene-network lineage differs")
        metrics = raw.get("metrics") or {}
        valid = bool(raw.get("valid")) and float(metrics.get("valid", 0.0)) == 1.0
        trajectory.append({
            "step": int(raw["step"]),
            "oracle_calls": int(raw["oracle_calls"]),
            "budget_units": int(raw["budget_units"]),
            "score": float(raw["score"]),
            "best_score": float(raw["best_score"]),
            "valid": valid,
            "accepted": bool(raw["accepted"]),
            "candidate_sha256": raw["candidate_sha256"],
            "parent_sha256": raw["parent_sha256"],
            "failure_kind": _failure_kind(raw),
            "science_metrics": _science_metrics(metrics),
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
    selected = trajectory[0]
    best_program_path = workdir / "best_program.py"
    terminal_program_path = workdir / "solution.py"
    record = {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(report_path),
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
        "baseline_score": float(run["baseline"]),
        "best_score": float(run["best"]),
        "accepted_proposals": int(run["accepted"]),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "run_manifest_sha256": _sha256(manifest_path),
        "best_program": str(relative_workdir / "best_program.py"),
        "best_program_sha256": _sha256(best_program_path),
        "terminal_program": str(relative_workdir / "solution.py"),
        "terminal_program_sha256": _sha256(terminal_program_path),
        "selected_step": selected["step"],
        "selected_candidate_sha256": selected["candidate_sha256"],
        "terminal_candidate_sha256": trajectory[-1]["candidate_sha256"],
        "trajectory": trajectory,
    }
    proposals = trajectory[1:]
    failure_counts: dict[str, int] = {}
    for event in proposals:
        if event["failure_kind"]:
            failure_counts[event["failure_kind"]] = (
                failure_counts.get(event["failure_kind"], 0) + 1
            )
    valid_proposals = [event for event in proposals if event["valid"]]
    record.update({
        "proposal_count": len(proposals),
        "valid_proposal_count": len(valid_proposals),
        "invalid_proposal_count": len(proposals) - len(valid_proposals),
        "failure_counts": failure_counts,
        "valid_nonzero_proposal_count": sum(
            event["valid"] and event["score"] > 0.0 for event in proposals
        ),
        "valid_all_refusal_proposal_count": sum(
            event["valid"]
            and event["science_metrics"].get(
                "development_supported_claim_coverage"
            ) == 0.0
            and event["science_metrics"].get(
                "heldout_supported_claim_coverage"
            ) == 0.0
            and event["science_metrics"].get(
                "development_unsupported_refusal_rate"
            ) == 1.0
            and event["science_metrics"].get(
                "heldout_unsupported_refusal_rate"
            ) == 1.0
            for event in proposals
        ),
    })
    record["integrity_passed"] = bool(
        _lineage_is_valid(record)
        and record["selection_policy"] == expected_policy
        and record["oracle_calls"] == expected_budget + 1
        and record["budget_units"] == expected_budget + 1
        and record["llm_calls"] == expected_budget
        and record["provider_usage_records"] == expected_budget
        and int(run["evaluated"]) == expected_budget + 1
        and record["accepted_proposals"] == 0
        and record["best_score"] == 0.0
        and record["selected_step"] == 0
        and record["best_program_sha256"] == record["selected_candidate_sha256"]
        and record["terminal_program_sha256"] == record["terminal_candidate_sha256"]
        and manifest.get("task_id") == TASK
        and manifest.get("feedback_mode") == expected_mode
        and manifest.get("seed") == 1
        and manifest.get("llm_condition_sha256")
        == config.get("llm_condition_sha256")
    )
    if not record["integrity_passed"]:
        raise ValueError("gene-network lineage or accounting gate failed")
    return record


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    runtime_source_equivalent: bool,
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
    all_proposals = [
        event
        for record in records.values()
        for event in record["trajectory"][1:]
    ]
    failure_counts: dict[str, int] = {}
    for event in all_proposals:
        if event["failure_kind"]:
            failure_counts[event["failure_kind"]] = (
                failure_counts.get(event["failure_kind"], 0) + 1
            )
    execution_passed = bool(
        runtime_source_equivalent
        and calibration["source_revision"] == EXPECTED_TASK_SOURCE_REVISION
        and revisions == {expected_model_source_revision}
        and len(scopes) == 1
        and len(conditions) == 1
        and None not in conditions
        and all(record["integrity_passed"] for record in records.values())
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["feedback_mode"] == normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
    )
    normal_minus_blind = {
        "best_score": normal["best_score"] - blind["best_score"],
        "valid_proposals": (
            normal["valid_proposal_count"] - blind["valid_proposal_count"]
        ),
        "invalid_proposals": (
            normal["invalid_proposal_count"] - blind["invalid_proposal_count"]
        ),
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
        "total_tokens": (
            normal["total_tokens"] - blind["total_tokens"]
            if _finite_number(normal["total_tokens"])
            and _finite_number(blind["total_tokens"]) else None
        ),
        "wall_seconds": normal["wall_seconds"] - blind["wall_seconds"],
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "GENE_NETWORK_SINGLE_RUN_TASK_CALIBRATION_NOT_FEEDBACK_CAUSAL_"
            "POPULATION_REAL_PERTURB_SEQ_WET_LAB_OR_DISCOVERY_EVIDENCE"
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
        "input_source_scope_equivalent": len(scopes) == 1,
        "input_llm_condition_equivalent": len(conditions) == 1,
        "task_calibration": calibration,
        "records": records,
        "proposal_hurdle_summary": {
            "proposal_count": len(all_proposals),
            "valid_proposal_count": sum(
                record["valid_proposal_count"] for record in records.values()
            ),
            "invalid_proposal_count": sum(
                record["invalid_proposal_count"] for record in records.values()
            ),
            "valid_nonzero_proposal_count": sum(
                record["valid_nonzero_proposal_count"]
                for record in records.values()
            ),
            "valid_all_refusal_proposal_count": sum(
                record["valid_all_refusal_proposal_count"]
                for record in records.values()
            ),
            "failure_counts": failure_counts,
        },
        "normal_minus_blind_descriptive_contrast": normal_minus_blind,
        "descriptive_findings": {
            "budget_one_improves_baseline": one["best_score"] > 0.0,
            "normal_budget_three_improves_baseline": normal["best_score"] > 0.0,
            "blind_budget_three_improves_baseline": blind["best_score"] > 0.0,
            "any_valid_nonzero_scientific_proposal": any(
                record["valid_nonzero_proposal_count"] > 0
                for record in records.values()
            ),
            "budget_one_has_callback_schema_failure": (
                one["failure_counts"].get("candidate_callback_schema_error", 0)
                > 0
            ),
            "normal_budget_three_has_no_valid_proposal": (
                normal["valid_proposal_count"] == 0
            ),
            "blind_budget_three_contains_valid_all_refusal": (
                blind["valid_all_refusal_proposal_count"] > 0
            ),
            "normal_and_blind_are_oracle_call_matched": (
                normal_minus_blind["oracle_calls"] == 0
            ),
            "normal_and_blind_are_token_matched": (
                normal_minus_blind["total_tokens"] == 0
            ),
            "feedback_effect_identified": False,
            "autonomous_biological_discovery_demonstrated": False,
        },
        "limitations": [
            "Each condition has one run; no confidence interval, population, leaderboard or scaling-law estimate is supported.",
            "The Azure endpoint exposes no server-side generation seed, so equal local seed labels do not pair model randomness.",
            "Normal and selection-blind are oracle-call matched but differ in tokens, context and wall time; their contrast is descriptive, not causal.",
            "Selection-blind is an offline best-of-open-loop batch; every proposal uses the frozen baseline parent.",
            "Budget one and budget three are independent model calls, not prefixes of one trajectory.",
            "Scientific mechanism, prediction, intervention transfer, refusal and per-world metrics were evaluator-only; proposal feedback contained only the allowlisted selection view.",
            "A zero joint score conflates invalid experiment protocol, callback schema failure and valid over-refusal unless the hurdle states are reported separately.",
            "The truth-blind nonlinear reference is a task calibration control, not an autonomous agent or biological result.",
            "The benchmark is a synthetic four-gene ODE, not a named cell line, real Perturb-seq dataset or wet-lab validation.",
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
        calibration, records, runtime_source_equivalent,
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
