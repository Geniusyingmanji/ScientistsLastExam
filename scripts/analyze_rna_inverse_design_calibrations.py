#!/usr/bin/env python3
"""Bind and analyze the three RNAInverseDesign GPT-5.5 calibrations.

Each condition is one descriptive run.  Equal local seed labels do not control Azure
generation randomness, so normal versus selection-blind differences are not causal effects.
"""

from __future__ import annotations

import argparse
import ast
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


TASK = "RNAEngineering/RNAInverseDesign"
INPUT_SOURCE_REVISION = "41f5fb4700f09155a7d23afb67a0d16f4a41f905"
CALIBRATION = "experiments/rna_inverse_design_calibration_2026-07-24.json"
REPORTS = {
    "budget_one": "experiments/gpt55_rna_inverse_v1_b1_2026-07-24.json",
    "normal_budget_three": "experiments/gpt55_rna_inverse_v1_b3_2026-07-24.json",
    "blind_budget_three": (
        "experiments/gpt55_rna_inverse_v1_blind_b3_2026-07-24.json"
    ),
}
SCIENCE_FIELDS = (
    "development_exact_utility",
    "development_target_probability",
    "development_ensemble_correctness",
    "development_mfe_f1",
    "development_proxy_compatibility",
    "development_proxy_false_promotion_rate",
    "robustness_score",
    "heldout_policy_score",
    "heldout_robustness_score",
    "heldout_target_probability",
    "heldout_ensemble_correctness",
    "heldout_mfe_f1",
    "heldout_proxy_compatibility",
    "heldout_proxy_false_promotion_rate",
    "heldout_feasibility_rate",
    "candidate_problem_valid_rate",
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


def _fixed_instance_shortcut_scan(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_literals = {
        "hairpin_24", "single_bulge_28", "internal_loop_30",
        "tandem_hairpins_32", "two_branch_36", "asymmetric_internal_34",
        "three_branch_40", "long_tandem_42",
    }
    string_literals = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Str)
    }
    forbidden_hits = sorted(forbidden_literals & string_literals)
    source_hits = sorted(term for term in (
        "verification", "REFERENCE_SEQUENCES", "_reference_policy"
    ) if term in source)
    return {
        "source_sha256": _sha256(path),
        "fixed_instance_literal_hits": forbidden_hits,
        "evaluator_source_term_hits": source_hits,
        "passed": not forbidden_hits and not source_hits,
    }


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    reference = document.get("reference") or {}
    baseline = document.get("direct_baseline") or {}
    regeneration = document.get("reference_regeneration") or {}
    checks = document.get("exhaustive_dynamic_program_checks") or []
    counterexample = document.get("proxy_perfect_exact_failure") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("passed") is True
        and document.get("trusted_evidence") is True
        and provenance.get("git_revision") == INPUT_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and baseline.get("valid") == 1.0
        and baseline.get("combined_score") == 0.0
        and reference.get("valid") == 1.0
        and reference.get("combined_score") == 1.0
        and reference.get("heldout_policy_score") == 1.0
        and reference.get("robustness_score") == 1.0
        and regeneration.get("exact_match") is True
        and float(document.get("minimum_nominal_headroom", 0.0)) > 0.10
        and float(document.get("minimum_shift_headroom", 0.0)) > 0.10
        and len(checks) == 4
        and all(row.get("passed") is True for row in checks)
        and counterexample.get("proxy_compatibility") == 1.0
        and counterexample.get("normalized_exact_quality") == 0.0
        and float(counterexample.get("target_probability", 1.0)) < 1.0e-7
    ):
        raise ValueError("RNAInverseDesign task calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "minimum_nominal_headroom": document["minimum_nominal_headroom"],
        "minimum_shift_headroom": document["minimum_shift_headroom"],
        "baseline": {
            "combined_score": baseline["combined_score"],
            "development_proxy_compatibility": baseline[
                "development_proxy_compatibility"
            ],
            "development_proxy_false_promotion_rate": baseline[
                "development_proxy_false_promotion_rate"
            ],
        },
        "reference": {
            "combined_score": reference["combined_score"],
            "heldout_policy_score": reference["heldout_policy_score"],
            "robustness_score": reference["robustness_score"],
            "development_target_probability": reference[
                "development_target_probability"
            ],
            "heldout_target_probability": reference[
                "heldout_target_probability"
            ],
        },
        "proxy_perfect_exact_failure": counterexample,
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
        raise ValueError("untrusted RNA model report: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one successful RNA run")
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
        raise ValueError("unexpected RNA calibration condition")

    workdir = Path(run["workdir"]).resolve()
    try:
        relative_workdir = workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("RNA workdir is outside repository") from exc
    trajectory_path = workdir / "trajectory.jsonl"
    raw_events = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable RNA snapshot differs from raw trajectory")
    if len(raw_events) != expected_budget + 1:
        raise ValueError("RNA trajectory is incomplete")

    trajectory = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
            and int(compact["step"]) == int(raw["step"])
        ):
            raise ValueError("raw and portable RNA lineage differs")
        metrics = raw.get("metrics") or {}
        science = _science_metrics(metrics)
        if any(
            value is not None and not _finite_number(value)
            for value in science.values()
        ):
            raise ValueError("RNA science metric is non-finite")
        per_instance = metrics.get("per_instance") or []
        if len(per_instance) != 8:
            raise ValueError("RNA event does not retain all eight instances")
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
            "science_metrics": science,
            "valid_instance_count": sum(bool(row.get("valid")) for row in per_instance),
            "invalid_instance_count": sum(not bool(row.get("valid")) for row in per_instance),
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
    best_program_path = workdir / "best_program.py"
    terminal_program_path = workdir / "solution.py"
    best_hash = _sha256(best_program_path)
    selected_events = [
        event for event in trajectory if event["candidate_sha256"] == best_hash
    ]
    if len(selected_events) != 1:
        raise ValueError("RNA best program does not identify one trajectory event")
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
        "seed": int(run["seed"]),
        "proposal_budget": expected_budget,
        "oracle_calls": int(summary["oracle_calls"]),
        "budget_units": int(summary["budget_units"]),
        "llm_calls": int(summary["llm"]["calls"]),
        "provider_usage_records": int(summary["llm"]["provider_usage_records"]),
        "total_tokens": summary["llm"].get("total_tokens"),
        "wall_seconds": float(summary["wall_seconds"]),
        "baseline_score": float(run["baseline"]),
        "best_score": float(run["best"]),
        "accepted_proposals": int(run["accepted"]),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "run_manifest_sha256": _sha256(manifest_path),
        "best_program": str(relative_workdir / "best_program.py"),
        "best_program_sha256": best_hash,
        "terminal_program": str(relative_workdir / "solution.py"),
        "terminal_program_sha256": _sha256(terminal_program_path),
        "selected_step": selected["step"],
        "selected_candidate_sha256": selected["candidate_sha256"],
        "selected_metrics": selected["science_metrics"],
        "terminal_candidate_sha256": trajectory[-1]["candidate_sha256"],
        "trajectory": trajectory,
        "proposal_count": len(proposals),
        "valid_proposal_count": sum(event["valid"] for event in proposals),
        "invalid_proposal_count": sum(not event["valid"] for event in proposals),
        "valid_nonzero_proposal_count": sum(
            event["valid"] and event["score"] > 0.0 for event in proposals
        ),
        "failure_counts": failure_counts,
        "fixed_instance_shortcut_scan": _fixed_instance_shortcut_scan(
            best_program_path
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
        and abs(record["best_score"] - selected["score"]) < 1.0e-12
        and record["terminal_program_sha256"] == record["terminal_candidate_sha256"]
        and record["fixed_instance_shortcut_scan"]["passed"]
        and manifest.get("task_id") == TASK
        and manifest.get("feedback_mode") == expected_mode
        and manifest.get("seed") == 1
        and manifest.get("llm_condition_sha256") == config.get("llm_condition_sha256")
    )
    if not record["integrity_passed"]:
        raise ValueError("RNA lineage or accounting gate failed")
    return record


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    expected_source_revision: str = INPUT_SOURCE_REVISION,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    conditions = {record["llm_condition_sha256"] for record in records.values()}
    proposals = [
        event for record in records.values() for event in record["trajectory"][1:]
    ]
    normal_positive = [
        event for event in normal["trajectory"][1:]
        if event["valid"] and event["score"] > 0.0
    ]
    contrast = {
        field: normal["selected_metrics"][field] - blind["selected_metrics"][field]
        for field in SCIENCE_FIELDS
    }
    contrast.update({
        "best_score": normal["best_score"] - blind["best_score"],
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "wall_seconds": normal["wall_seconds"] - blind["wall_seconds"],
    })
    execution_passed = bool(
        calibration["source_revision"] == expected_source_revision
        and revisions == {expected_source_revision}
        and len(scopes) == 1
        and len(conditions) == 1
        and None not in conditions
        and all(record["integrity_passed"] for record in records.values())
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "RNA_INVERSE_SINGLE_RUN_SIMPLIFIED_ENSEMBLE_CALIBRATION_NOT_"
            "FEEDBACK_CAUSAL_POPULATION_FULL_TURNER_WET_LAB_OR_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_source_revision": expected_source_revision,
        "input_source_scope_equivalent": len(scopes) == 1,
        "input_llm_condition_equivalent": len(conditions) == 1,
        "task_calibration": calibration,
        "records": records,
        "proposal_hurdle_summary": {
            "proposal_count": len(proposals),
            "valid_proposal_count": sum(event["valid"] for event in proposals),
            "invalid_proposal_count": sum(not event["valid"] for event in proposals),
            "valid_nonzero_proposal_count": sum(
                event["valid"] and event["score"] > 0.0 for event in proposals
            ),
            "invalid_sequence_count": sum(
                event["failure_kind"] == "invalid_sequence" for event in proposals
            ),
        },
        "normal_accepted_science_curve": [
            {
                "step": event["step"],
                "score": event["score"],
                **event["science_metrics"],
            }
            for event in normal_positive
        ],
        "normal_minus_blind_selected_descriptive_contrast": contrast,
        "descriptive_findings": {
            "budget_one_improves_baseline": one["best_score"] > 0.0,
            "normal_budget_three_improves_baseline": normal["best_score"] > 0.0,
            "blind_budget_three_improves_baseline": blind["best_score"] > 0.0,
            "normal_accepts_three_monotone_improvements": (
                len(normal_positive) == 3
                and all(
                    normal_positive[index]["score"]
                    < normal_positive[index + 1]["score"]
                    for index in range(2)
                )
            ),
            "normal_endpoint_retains_proxy_false_promotions": (
                normal["selected_metrics"][
                    "development_proxy_false_promotion_rate"
                ] > 0.0
                or normal["selected_metrics"][
                    "heldout_proxy_false_promotion_rate"
                ] > 0.0
            ),
            "blind_selected_has_zero_proxy_false_promotions": (
                blind["selected_metrics"][
                    "development_proxy_false_promotion_rate"
                ] == 0.0
                and blind["selected_metrics"][
                    "heldout_proxy_false_promotion_rate"
                ] == 0.0
            ),
            "normal_and_blind_are_oracle_call_matched": contrast["oracle_calls"] == 0,
            "normal_and_blind_are_token_matched": contrast["total_tokens"] == 0,
            "feedback_effect_identified": False,
            "full_thermodynamic_or_experimental_rna_validity_demonstrated": False,
        },
        "limitations": [
            "Each condition has one run; no confidence interval, population, leaderboard or scaling-law estimate is supported.",
            "The Azure endpoint exposes no server-side generation seed, so equal local seed labels do not pair model randomness.",
            "Normal and selection-blind match oracle calls but differ in tokens, context and wall time; their contrast is descriptive, not causal.",
            "Selection-blind is an offline best-of-open-loop batch whose proposals all use the frozen baseline parent.",
            "Budget one and budget three are independent model calls, not prefixes of one trajectory.",
            "Exact ensemble, robustness, held-out, proxy false-promotion and per-instance metrics were evaluator-only.",
            "The transparent pair-stack-loop model is not the complete Turner nearest-neighbor model and omits pseudoknots, tertiary structure and kinetics.",
            "The reference and GPT-5.5 programs are computational task results, not synthesized RNAs or structural or functional assays.",
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
    return _analyze_records(calibration, records)


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
