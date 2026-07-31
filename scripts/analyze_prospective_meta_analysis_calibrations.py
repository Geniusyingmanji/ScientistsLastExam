#!/usr/bin/env python3
"""Bind and analyze ProspectiveMetaAnalysis-v1 GPT-5.5 calibrations.

The three model conditions are single descriptive runs.  They do not estimate
population performance or a feedback effect.  The analyzer separates executable
validity, evidence-workflow coverage and conditional scientific quality.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import platform
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.protocol import compact_trajectory_snapshot, load_trajectory  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402
from frontier_science.runtime_migration import runtime_source_changes  # noqa: E402
from frontier_science.algorithms.common import (  # noqa: E402
    task_contract_sha256,
)
from frontier_science.spec import load_task_spec  # noqa: E402


TASK = "EvidenceSynthesis/ProspectiveMetaAnalysis"
MODEL_SOURCE_REVISION = "3b10e68fedefc415128386f626a39071d7ecfe02"
CALIBRATION = "experiments/prospective_meta_analysis_calibration_2026-07-25.json"
REPORTS = {
    "budget_one": "experiments/gpt55_prospective_meta_v1_b1_2026-07-25.json",
    "normal_budget_three": "experiments/gpt55_prospective_meta_v1_b3_2026-07-25.json",
    "blind_budget_three": (
        "experiments/gpt55_prospective_meta_v1_blind_b3_2026-07-25.json"
    ),
}
CONDITIONS = {
    "budget_one": {"mode": "normal", "budget": 1, "seed": 0},
    "normal_budget_three": {"mode": "normal", "budget": 3, "seed": 1},
    "blind_budget_three": {"mode": "selection_blind", "budget": 3, "seed": 1},
}
TASK_RUNTIME_SCOPE = (
    "frontier_science/evaluate.py",
    "frontier_science/trusted_driver.py",
    "frontier_science/secure_eval.py",
    "frontier_science/candidate_worker.py",
    "frontier_science/rpc_codec.py",
    "frontier_science/spec.py",
    "frontier_science/registry.py",
    "benchmarks/Biology/ProspectiveMetaAnalysis",
    "requirements-upstream.txt",
)
SCIENCE_FIELDS = (
    "combined_score", "raw_score", "valid", "feasibility_rate",
    "robustness_score", "heldout_policy_score", "heldout_robustness_score",
    "heldout_feasibility_rate", "development_evidence_integrity_score",
    "heldout_evidence_integrity_score",
    "development_preconfirmation_mechanism_score",
    "heldout_preconfirmation_mechanism_score", "development_prediction_score",
    "heldout_prediction_score", "development_forecast_distribution_score",
    "heldout_forecast_distribution_score", "development_design_information_score",
    "heldout_design_information_score", "development_postconfirmation_score",
    "heldout_postconfirmation_score", "development_confirmation_point_score",
    "heldout_confirmation_point_score",
    "development_confirmation_interval_coverage",
    "heldout_confirmation_interval_coverage", "development_false_discovery_rate",
    "heldout_false_discovery_rate", "development_supported_claim_coverage",
    "heldout_supported_claim_coverage", "development_unsupported_refusal_rate",
    "heldout_unsupported_refusal_rate", "development_mean_confirmation_calls",
    "heldout_mean_confirmation_calls", "development_raw_quality",
    "heldout_raw_quality",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, TASK_RUNTIME_SCOPE, root=ROOT)


def _science(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in SCIENCE_FIELDS}


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _lineage_valid(events, mode):
    if not events or events[0].get("parent_sha256") is not None:
        return False
    baseline = events[0]["candidate_sha256"]
    if mode == "selection_blind":
        return all(event["parent_sha256"] == baseline for event in events[1:])
    parent = baseline
    for event in events[1:]:
        if event["parent_sha256"] != parent:
            return False
        if event["accepted"]:
            parent = event["candidate_sha256"]
    return True


def _scan_retained_source(path: Path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    calls = set()
    identifiers = set()
    literals = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.add(node.value)
    forbidden_imports = sorted(imports & {
        "benchmarks", "builtins", "frontier_science", "http", "importlib", "os",
        "pathlib", "requests", "socket", "subprocess", "sys", "urllib",
        "verification",
    })
    forbidden_calls = sorted(calls & {
        "__import__", "compile", "eval", "exec", "open", "read_bytes",
        "read_text",
    })
    hidden_terms = (
        "linear_positive", "linear_mixed", "linear_null", "nonlinear",
        "DEVELOPMENT_SPECS", "HELDOUT_SPECS", "oracle_reference_policy",
        "verification/evaluator.py", "verification.evaluator", "world_kind",
        "world_index",
    )
    literal_hits = sorted({
        term
        for literal in literals
        for term in hidden_terms
        if term.lower() in literal.lower()
    })
    identifier_hits = sorted(set(hidden_terms) & identifiers)
    try:
        relative = str(path.relative_to(ROOT))
    except ValueError:
        relative = str(path)
    return {
        "path": relative,
        "sha256": _sha256(path),
        "source_bytes": len(source.encode("utf-8")),
        "source_lines": len(source.splitlines()),
        "forbidden_import_hits": forbidden_imports,
        "forbidden_call_hits": forbidden_calls,
        "hidden_world_literal_hits": literal_hits,
        "hidden_world_identifier_hits": identifier_hits,
        "passed": not (
            forbidden_imports or forbidden_calls or literal_hits or identifier_hits
        ),
    }


def _load_calibration():
    path = ROOT / CALIBRATION
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    reference = document.get("truth_blind_reference") or {}
    oracle_reference = document.get("oracle_reference") or {}
    world_checks = document.get("world_checks") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and provenance.get("git_revision") == MODEL_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and document.get("task") == TASK
        and document.get("secure_weak_baseline", {}).get("combined_score") == 0.0
        and 0.75 < reference.get("combined_score", 0.0) < 0.99
        and 0.70 < reference.get("heldout_policy_score", 0.0) < 0.99
        and reference.get("development_false_discovery_rate") == 0.0
        and reference.get("heldout_false_discovery_rate") == 0.0
        and reference.get("development_unsupported_refusal_rate") == 1.0
        and reference.get("heldout_unsupported_refusal_rate") == 1.0
        and oracle_reference.get("combined_score") == 1.0
        and oracle_reference.get("heldout_policy_score") == 1.0
        and world_checks.get("passed") is True
        and world_checks.get("minimum_naive_highlighted_article_intercept_bias", 0.0) > 0.01
        and document.get("invalid_artifact_checks", {}).get("passed") is True
    ):
        raise ValueError("ProspectiveMetaAnalysis task calibration gate failed")
    return {
        "report": CALIBRATION,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "evidence_scope": document["evidence_scope"],
        "task_dimensions": document["task_dimensions"],
        "weak_baseline": document["secure_weak_baseline"],
        "truth_blind_reference": reference,
        "oracle_reference": oracle_reference,
        "world_checks": world_checks,
        "limitations": document["limitations"],
    }


def _classify_event(event):
    metrics = event.get("metrics") or {}
    if event["step"] == 0:
        return "baseline"
    if not bool(event.get("valid")) or float(metrics.get("valid", 0.0)) != 1.0:
        reasons = {
            row.get("reason") for row in metrics.get("per_world", [])
            if row.get("reason")
        }
        if reasons and all("wrong fields" in reason for reason in reasons):
            return "schema_invalid"
        return "invalid"
    workflow_fields = (
        "development_evidence_integrity_score",
        "heldout_evidence_integrity_score",
        "development_mean_confirmation_calls",
        "heldout_mean_confirmation_calls",
        "development_supported_claim_coverage",
        "heldout_supported_claim_coverage",
    )
    if all(float(metrics.get(field, 0.0)) == 0.0 for field in workflow_fields):
        return "valid_empty_abstention"
    return "valid_scientific_workflow"


def _load_model(label, relative):
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    expected = CONDITIONS[label]
    if not (
        document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and provenance.get("git_revision") == MODEL_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
    ):
        raise ValueError("model report is not trusted: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one completed model run")
    run = runs[0]
    config = document["config"]
    if not (
        run["task"] == TASK
        and run["algorithm"] == "greedy_rewrite"
        and run["feedback_mode"] == expected["mode"]
        and int(run["seed"]) == expected["seed"]
        and int(config["budget"]) == expected["budget"]
        and config["llm"]["model"] == "gpt-5.5"
        and config["llm"]["server_side_seed_control"] is False
    ):
        raise ValueError("unexpected model condition")
    workdir = Path(run["workdir"]).resolve()
    try:
        relative_workdir = workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("model workdir is outside repository") from exc
    trajectory_path = workdir / "trajectory.jsonl"
    raw = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run["trajectory_snapshot"] or len(raw) != expected["budget"] + 1:
        raise ValueError("raw and portable trajectory differ")
    events = []
    for compact, full in zip(snapshot["events"], raw):
        if not (
            int(compact["step"]) == int(full["step"])
            and compact["candidate_sha256"] == full["candidate_sha256"]
            and compact["parent_sha256"] == full.get("parent_sha256")
        ):
            raise ValueError("raw and portable trajectory lineage differs")
        metrics = full.get("metrics") or {}
        science = _science(metrics)
        if any(
            value is not None and not _finite_number(value)
            for value in science.values()
        ):
            raise ValueError("model science metric is non-finite")
        metric_valid = metrics.get("valid") == 1.0
        if bool(full.get("valid")) != metric_valid:
            raise ValueError("event validity disagrees with trusted metrics")
        per_world = metrics.get("per_world") or []
        if len(per_world) != 10:
            raise ValueError("event does not bind all ten evidence worlds")
        if metric_valid != all(bool(row.get("valid")) for row in per_world):
            raise ValueError("aggregate and per-world validity differ")
        events.append({
            "step": int(full["step"]),
            "oracle_calls": int(full["oracle_calls"]),
            "budget_units": int(full["budget_units"]),
            "score": float(full["score"]),
            "best_score": float(full["best_score"]),
            "valid": bool(full["valid"]),
            "accepted": bool(full["accepted"]),
            "candidate_sha256": full["candidate_sha256"],
            "parent_sha256": full.get("parent_sha256"),
            "classification": _classify_event(full),
            "science_metrics": science,
            "failure_reasons": sorted({
                row.get("reason") for row in per_world
                if row.get("reason")
            }),
            "llm": full.get("llm") or {},
        })
    if not _lineage_valid(events, run["feedback_mode"]):
        raise ValueError("candidate lineage is invalid")
    if [event["step"] for event in events] != list(range(expected["budget"] + 1)):
        raise ValueError("trajectory steps are not contiguous")
    if any(
        event["oracle_calls"] != event["step"] + 1
        or event["budget_units"] != event["step"] + 1
        for event in events
    ):
        raise ValueError("trajectory accounting is not contiguous")
    summary = run.get("summary") or {}
    llm_summary = summary.get("llm") or {}
    proposal_llm = [event["llm"] for event in events[1:]]
    token_sums = {
        field: sum(int(usage.get(field, 0)) for usage in proposal_llm)
        for field in ("input_tokens", "output_tokens", "total_tokens")
    }
    manifest_path = workdir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    spec = load_task_spec(ROOT / "benchmarks/Biology/ProspectiveMetaAnalysis")
    best = workdir / "best_program.py"
    terminal = workdir / "solution.py"
    terminal_scan = _scan_retained_source(terminal)
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if expected["mode"] == "selection_blind" else "online_incumbent"
    )
    record = {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "llm_condition_sha256": config.get("llm_condition_sha256"),
        "task_contract_sha256": manifest.get("task_contract_sha256"),
        "runtime_source_sha256": manifest.get("runtime_source_sha256"),
        "run_manifest_sha256": _sha256(manifest_path),
        "feedback_mode": run["feedback_mode"],
        "feedback_scope": summary["feedback_scope"],
        "selection_policy": summary["selection_policy"],
        "seed": int(run["seed"]),
        "proposal_budget": int(config["budget"]),
        "oracle_calls": int(summary["oracle_calls"]),
        "budget_units": int(summary["budget_units"]),
        "llm_calls": int(llm_summary["calls"]),
        "provider_usage_records": int(llm_summary["provider_usage_records"]),
        "input_tokens": int(llm_summary["input_tokens"]),
        "output_tokens": int(llm_summary["output_tokens"]),
        "total_tokens": int(llm_summary["total_tokens"]),
        "wall_seconds": float(summary["wall_seconds"]),
        "baseline_score": float(run["baseline"]),
        "best_score": float(run["best"]),
        "accepted_proposals": int(run["accepted"]),
        "proposal_count": expected["budget"],
        "valid_proposal_count": sum(event["valid"] for event in events[1:]),
        "invalid_proposal_count": sum(not event["valid"] for event in events[1:]),
        "classification_counts": dict(Counter(
            event["classification"] for event in events[1:]
        )),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "trajectory": events,
        "baseline_candidate_sha256": events[0]["candidate_sha256"],
        "best_program": str(relative_workdir / "best_program.py"),
        "best_program_sha256": _sha256(best),
        "terminal_program": str(relative_workdir / "solution.py"),
        "terminal_program_sha256": _sha256(terminal),
        "terminal_source_scan": terminal_scan,
        "artifact_retention_scope": (
            "baseline-selected best and terminal proposal source are retained; intermediate "
            "proposal sources are not retained, but hashes, lineage and full trusted metrics remain bound"
        ),
    }
    record["integrity_passed"] = bool(
        record["selection_policy"] == expected_policy
        and record["oracle_calls"] == expected["budget"] + 1
        and record["budget_units"] == expected["budget"] + 1
        and record["llm_calls"] == expected["budget"]
        and record["provider_usage_records"] == expected["budget"]
        and int(run["evaluated"]) == record["oracle_calls"]
        and int(run["accepted"]) == record["accepted_proposals"]
        == sum(event["accepted"] for event in events[1:])
        and float(summary["best_score"]) == record["best_score"]
        == events[-1]["best_score"]
        and float(summary["baseline_score"]) == record["baseline_score"]
        == events[0]["score"]
        and int(summary["accepted"]) == record["accepted_proposals"]
        and all(token_sums[field] == record[field] for field in token_sums)
        and all(
            int(usage.get("total_tokens", 0))
            == int(usage.get("input_tokens", 0))
            + int(usage.get("output_tokens", 0))
            for usage in proposal_llm
        )
        and record["best_program_sha256"] == events[0]["candidate_sha256"]
        and record["terminal_program_sha256"] == events[-1]["candidate_sha256"]
        and terminal_scan["sha256"] == events[-1]["candidate_sha256"]
        and terminal_scan["passed"]
        and manifest.get("task_id") == TASK
        and manifest.get("feedback_mode") == expected["mode"]
        and int(manifest.get("seed", -1)) == expected["seed"]
        and manifest.get("llm_condition_sha256")
        == config.get("llm_condition_sha256")
        and manifest.get("task_contract_sha256") == task_contract_sha256(spec)
        and isinstance(manifest.get("runtime_source_sha256"), str)
        and len(manifest["runtime_source_sha256"]) == 64
        and all(char in "0123456789abcdef" for char in manifest["runtime_source_sha256"])
    )
    if not record["integrity_passed"]:
        raise ValueError("model lineage, accounting, or retained-artifact gate failed")
    return record


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    runtime_source_equivalent: bool = True,
    runtime_source_changes: list[str] | None = None,
):
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    conditions = {record["llm_condition_sha256"] for record in records.values()}
    contracts = {record["task_contract_sha256"] for record in records.values()}
    runtimes = {record["runtime_source_sha256"] for record in records.values()}
    baseline_hashes = {
        record["baseline_candidate_sha256"] for record in records.values()
    }
    all_events = [
        event for record in records.values() for event in record["trajectory"][1:]
    ]
    counts = Counter(event["classification"] for event in all_events)
    workflow_events = [
        event for event in all_events
        if event["classification"] == "valid_scientific_workflow"
    ]
    execution_passed = bool(
        set(records) == set(CONDITIONS)
        and calibration["source_revision"] == MODEL_SOURCE_REVISION
        and revisions == {MODEL_SOURCE_REVISION}
        and runtime_source_equivalent
        and scopes == {tuple(calibration["source_scope"] or [])}
        and len(conditions) == 1
        and None not in conditions
        and len(contracts) == 1
        and None not in contracts
        and len(runtimes) == 1
        and None not in runtimes
        and len(baseline_hashes) == 1
        and all(record["integrity_passed"] for record in records.values())
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["seed"] == 0
        and normal["seed"] == blind["seed"] == 1
        and one["feedback_mode"] == normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and len(all_events) == 7
        and counts["schema_invalid"] == 4
        and counts["valid_empty_abstention"] == 3
        and not workflow_events
        and all(record["best_score"] == 0.0 for record in records.values())
        and all(record["accepted_proposals"] == 0 for record in records.values())
        and normal["oracle_calls"] == blind["oracle_calls"] == 4
        and normal["input_tokens"] == blind["input_tokens"] == 4641
        and normal["output_tokens"] != blind["output_tokens"]
        and all(
            record["terminal_source_scan"]["passed"]
            for record in records.values()
        )
    )
    provenance = source_provenance(ROOT)
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "SINGLE_RUN_SYNTHETIC_EVIDENCE_WORKFLOW_CALIBRATION_NOT_FEEDBACK_"
            "CAUSAL_POPULATION_CLINICAL_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": provenance,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "model_source_revision": MODEL_SOURCE_REVISION,
        "input_task_runtime_source_equivalent": runtime_source_equivalent,
        "input_task_runtime_source_changes": runtime_source_changes or [],
        "input_source_scope_equivalent": (
            scopes == {tuple(calibration["source_scope"] or [])}
        ),
        "input_llm_condition_equivalent": len(conditions) == 1 and None not in conditions,
        "input_task_contract_equivalent": len(contracts) == 1 and None not in contracts,
        "input_runtime_manifest_equivalent": len(runtimes) == 1 and None not in runtimes,
        "input_baseline_candidate_equivalent": len(baseline_hashes) == 1,
        "task_calibration": calibration,
        "records": records,
        "proposal_hurdle_summary": {
            "proposal_count": len(all_events),
            "valid_proposal_count": sum(event["valid"] for event in all_events),
            "invalid_proposal_count": sum(not event["valid"] for event in all_events),
            "schema_invalid_count": counts["schema_invalid"],
            "valid_empty_abstention_count": counts["valid_empty_abstention"],
            "valid_scientific_workflow_count": len(workflow_events),
            "proposal_with_nonzero_evidence_integrity_count": sum(
                float(event["science_metrics"].get(
                    "development_evidence_integrity_score", 0.0
                ) or 0.0) > 0.0 for event in all_events
            ),
            "proposal_with_confirmation_count": sum(
                float(event["science_metrics"].get(
                    "development_mean_confirmation_calls", 0.0
                ) or 0.0) > 0.0 for event in all_events
            ),
            "proposal_with_supported_claim_coverage_count": sum(
                float(event["science_metrics"].get(
                    "development_supported_claim_coverage", 0.0
                ) or 0.0) > 0.0 for event in all_events
            ),
            "retained_terminal_source_count": 3,
            "unretained_intermediate_source_count": 4,
        },
        "normal_minus_blind_budget_three_descriptive_contrast": {
            "best_score": normal["best_score"] - blind["best_score"],
            "valid_proposal_count": (
                normal["valid_proposal_count"] - blind["valid_proposal_count"]
            ),
            "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
            "input_tokens": normal["input_tokens"] - blind["input_tokens"],
            "output_tokens": normal["output_tokens"] - blind["output_tokens"],
            "total_tokens": normal["total_tokens"] - blind["total_tokens"],
            "wall_seconds": normal["wall_seconds"] - blind["wall_seconds"],
        },
        "reference_context": {
            "weak_baseline_development_score": calibration["weak_baseline"]["combined_score"],
            "truth_blind_reference_development_score": calibration[
                "truth_blind_reference"
            ]["combined_score"],
            "truth_blind_reference_heldout_score": calibration[
                "truth_blind_reference"
            ]["heldout_policy_score"],
            "truth_blind_reference_false_discovery": [
                calibration["truth_blind_reference"]["development_false_discovery_rate"],
                calibration["truth_blind_reference"]["heldout_false_discovery_rate"],
            ],
            "truth_blind_reference_nonlinear_refusal": [
                calibration["truth_blind_reference"]["development_unsupported_refusal_rate"],
                calibration["truth_blind_reference"]["heldout_unsupported_refusal_rate"],
            ],
        },
        "descriptive_findings": {
            "model_reaches_nonzero_evidence_workflow_score": False,
            "normal_feedback_repairs_schema_validity_in_later_proposals": True,
            "normal_feedback_produces_evidence_screening_or_confirmation": False,
            "all_valid_proposals_are_empty_abstentions": True,
            "same_zero_score_conflates_schema_failure_and_empty_abstention": True,
            "normal_and_blind_are_oracle_call_and_input_token_matched": True,
            "normal_and_blind_are_output_token_matched": False,
            "feedback_effect_identified": False,
            "real_meta_analysis_or_autonomous_discovery_demonstrated": False,
        },
        "limitations": [
            "Each condition has one run; no population, leaderboard, confidence interval or scaling-law estimate is supported.",
            "Azure exposes no server-side generation seed, so equal local seed labels do not pair proposal randomness.",
            "Normal and selection-blind match oracle calls and input tokens but differ in prompts, generated sources, output tokens and wall time; the contrast is descriptive, not causal.",
            "Candidate-facing feedback intentionally omits evaluator-only schema reasons and science vectors; this protects sealed metrics but can make a zero plateau ambiguous.",
            "Only one terminal proposal source per condition is retained. Four intermediate proposal sources cannot receive a narrower post-hoc source diagnosis.",
            "The task is a synthetic standardized-summary laboratory, not a real systematic review, clinical trial or prospective meta-analysis.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def analyze():
    calibration = _load_calibration()
    records = {label: _load_model(label, path) for label, path in REPORTS.items()}
    current_revision = source_provenance(ROOT)["git_revision"]
    runtime_changes = _source_changes(MODEL_SOURCE_REVISION, current_revision)
    return _analyze_records(
        calibration,
        records,
        runtime_source_equivalent=not runtime_changes,
        runtime_source_changes=runtime_changes,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        key: report[key]
        for key in ("passed", "execution_passed", "trust_decision", "trusted_evidence")
    }, indent=2))
    print("Report: %s" % args.output.resolve())
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
