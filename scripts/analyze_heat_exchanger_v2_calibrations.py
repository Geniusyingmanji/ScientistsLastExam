#!/usr/bin/env python3
"""Build portable, non-causal evidence from HeatExchanger-v2 calibrations."""

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


CALIBRATION = "experiments/heat_exchanger_v2_calibration_2026-07-22.json"
REPORTS = {
    "budget_one": "experiments/gpt55_heat_exchanger_v2_b1_2026-07-22.json",
    "normal_budget_three": "experiments/gpt55_heat_exchanger_v2_b3_2026-07-22.json",
    "blind_budget_three": "experiments/gpt55_heat_exchanger_v2_blind_b3_2026-07-22.json",
}
TASK = "Thermodynamics/HeatExchangerDesign"
SOURCE_SCOPE = (
    "sle", "scripts", "tests", "benchmarks",
    "requirements-upstream.txt",
)
FIELDS = (
    "combined_score",
    "development_proxy_score",
    "heldout_exact_score",
    "heldout_proxy_score",
    "robustness_score",
    "heldout_robustness_score",
    "feasibility_rate",
    "heldout_feasibility_rate",
    "development_false_promotion_rate",
    "heldout_false_promotion_rate",
    "development_proxy_exact_rank_correlation",
    "heldout_proxy_exact_rank_correlation",
    "valid",
)
PER_INSTANCE_FIELDS = (
    "name", "split", "score", "proxy_score", "robustness_score",
    "exact_feasibility_rate", "proxy_feasibility_rate",
    "false_promotion_rate", "proxy_exact_rank_correlation",
    "raw_exact_hypervolume", "raw_proxy_hypervolume",
    "raw_shifted_hypervolumes",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(str(left), str(right), SOURCE_SCOPE, root=ROOT)


def _scalar_view(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in FIELDS}


def _instance_view(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    rows = metrics.get("per_instance") or []
    if not isinstance(rows, list) or len(rows) != 6:
        raise ValueError("expected six per-instance HeatExchanger metrics")
    return [
        {field: row.get(field) for field in PER_INSTANCE_FIELDS}
        for row in rows
    ]


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if document.get("trusted_evidence") is not True or document.get("passed") is not True:
        raise ValueError("task calibration is not trusted and passed")
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("task calibration has dirty source")
    required = (
        "baseline", "proxy_only_classical_policy", "nominal_reference_policy",
        "robust_reference_policy",
    )
    if any(not isinstance(document.get(key), dict) for key in required):
        raise ValueError("task calibration is missing a reference policy")
    reproductions = document.get("reference_reproduction") or []
    physics = document.get("anchor_and_physics_checks") or []
    convergence = document.get("segment_convergence_checks") or []
    if len(reproductions) != 6 or not all(
        row.get("pool_matches_oracle")
        and row.get("proxy_feasibility_matches")
        and row.get("nominal_indices_match")
        and row.get("robust_indices_match")
        for row in reproductions
    ):
        raise ValueError("task references do not reproduce")
    if len(physics) != 6 or not all(row.get("passed") for row in physics):
        raise ValueError("task physics checks did not pass")
    if len(convergence) != 6 or not all(row.get("passed") for row in convergence):
        raise ValueError("task segment-convergence checks did not pass")
    policies = {}
    for key in required:
        metrics = document[key]
        policies[key] = {
            "metrics": _scalar_view(metrics),
            "per_instance": _instance_view(metrics),
        }
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "policies": policies,
        "maximum_independent_proxy_error": max(
            float(row["maximum_independent_proxy_error"])
            for row in reproductions
        ),
        "maximum_anchor_error": max(
            float(row["maximum_anchor_error"]) for row in physics
        ),
        "maximum_10_vs_40_heat_duty_relative_error": max(
            float(row["maximum_10_vs_40_heat_duty_relative_error"])
            for row in convergence
        ),
    }


def _selected_event(events: list[dict[str, Any]], best: float) -> dict[str, Any]:
    accepted = [event for event in events if event.get("accepted")]
    matching = [
        event for event in accepted
        if abs(float(event["score"]) - float(best)) <= 1e-12
    ]
    if not matching:
        raise ValueError("no accepted trajectory event matches the run best")
    return min(matching, key=lambda event: int(event["step"]))


def _load(label: str, relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if document.get("trusted_evidence") is not True or document.get("passed") is not True:
        raise ValueError("input is not trusted and passed: %s" % relative)
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("input source was dirty: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected exactly one successful run: %s" % relative)
    run = runs[0]
    if run.get("task") != TASK or run.get("algorithm") != "greedy_rewrite":
        raise ValueError("unexpected task or algorithm: %s" % relative)
    trajectory_path = Path(run["workdir"]) / "trajectory.jsonl"
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable snapshot disagrees with raw trajectory: %s" % relative)
    raw_events = load_trajectory(trajectory_path)
    events = snapshot["events"]
    if len(raw_events) != len(events):
        raise ValueError("raw and compact trajectory lengths differ")
    if int(run.get("evaluated", -1)) != int(run["summary"].get("oracle_calls", -2)):
        raise ValueError("oracle-call count mismatch: %s" % relative)
    if sum(bool(event["accepted"]) for event in events[1:]) != int(run["accepted"]):
        raise ValueError("accepted-proposal count mismatch: %s" % relative)

    baseline_hash = events[0]["candidate_sha256"]
    proposals = events[1:]
    if label == "blind_budget_three":
        if run.get("feedback_mode") != "selection_blind":
            raise ValueError("blind report has the wrong feedback mode")
        if not all(event["parent_sha256"] == baseline_hash for event in proposals):
            raise ValueError("selection-blind proposal changed parent")
        if run["summary"].get("selection_policy") != "offline_best_of_open_loop_batch":
            raise ValueError("selection-blind policy metadata is missing")
    else:
        if run.get("feedback_mode") != "normal":
            raise ValueError("normal report has the wrong feedback mode")
        parent = baseline_hash
        for event in proposals:
            if event["parent_sha256"] != parent:
                raise ValueError("normal accepted-candidate lineage is broken")
            if event["accepted"]:
                parent = event["candidate_sha256"]

    selected = _selected_event(events, float(run["best"]))
    selected_raw = next(
        event for event in raw_events if int(event["step"]) == int(selected["step"])
    )
    invalid_reasons = []
    for raw in raw_events[1:]:
        if bool((raw.get("metrics") or {}).get("valid")):
            continue
        reasons = sorted({
            str(row.get("reason"))
            for row in (raw.get("metrics") or {}).get("per_instance", [])
            if not row.get("valid") and row.get("reason")
        })
        invalid_reasons.append({"step": int(raw["step"]), "reasons": reasons})
    return {
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
        "selected_metrics": _scalar_view(selected_raw["metrics"]),
        "selected_per_instance": _instance_view(selected_raw["metrics"]),
        "invalid_proposals": invalid_reasons,
        "trajectory": [
            {
                "step": int(event["step"]),
                "accepted": bool(event["accepted"]),
                "candidate_sha256": event["candidate_sha256"],
                "parent_sha256": event["parent_sha256"],
                **_scalar_view(event["metrics"]),
            }
            for event in events
        ],
    }


def _accepted_changes(record: dict[str, Any]) -> list[dict[str, Any]]:
    accepted = [event for event in record["trajectory"] if event["accepted"]]
    changes = []
    for previous, current in zip(accepted, accepted[1:]):
        changes.append({
            "from_step": previous["step"],
            "to_step": current["step"],
            **{
                field: float(current[field]) - float(previous[field])
                for field in FIELDS if field != "valid"
            },
        })
    return changes


def _regime_concentration(record: dict[str, Any]) -> dict[str, Any]:
    rows = [
        row for row in record["selected_per_instance"]
        if row["split"] == "development"
    ]
    scores = [max(0.0, float(row["score"])) for row in rows]
    total = sum(scores)
    leader = max(rows, key=lambda row: float(row["score"]))
    return {
        "development_regime_count": len(rows),
        "near_zero_regime_count": sum(score <= 1e-12 for score in scores),
        "maximum_regime_score": max(scores),
        "minimum_regime_score": min(scores),
        "score_range": max(scores) - min(scores),
        "leading_regime": leader["name"],
        "leading_regime_share_of_score_sum": (
            float(leader["score"]) / total if total > 0.0 else 0.0
        ),
        "per_regime": [
            {
                "name": row["name"],
                "score": row["score"],
                "proxy_score": row["proxy_score"],
                "robustness_score": row["robustness_score"],
                "exact_feasibility_rate": row["exact_feasibility_rate"],
                "false_promotion_rate": row["false_promotion_rate"],
            }
            for row in rows
        ],
    }


def _analyze_records(calibration: dict[str, Any],
                     records: dict[str, dict[str, Any]],
                     source_equivalent: bool = True) -> dict[str, Any]:
    budget_one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    normal_metrics = normal["selected_metrics"]
    blind_metrics = blind["selected_metrics"]
    classical = calibration["policies"]["proxy_only_classical_policy"]["metrics"]
    normal_changes = _accepted_changes(normal)
    normal_regimes = _regime_concentration(normal)
    blind_regimes = _regime_concentration(blind)
    model_revisions = {record["source_revision"] for record in records.values()}
    contrast = {
        field: float(normal_metrics[field]) - float(blind_metrics[field])
        for field in FIELDS if field != "valid"
    }
    contrast.update({
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
    })
    execution_passed = bool(
        source_equivalent
        and len(model_revisions) == 1
        and budget_one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and budget_one["oracle_calls"] == 2
        and normal["oracle_calls"] == blind["oracle_calls"] == 4
        and budget_one["feedback_mode"] == normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and all(not record["server_side_seed_control"] for record in records.values())
        and budget_one["selected_step"] == 0
        and bool(budget_one["invalid_proposals"])
        and [event["step"] for event in normal["trajectory"] if event["accepted"]]
        == [0, 2, 3]
        and len(normal_changes) == 2
        and all(change["combined_score"] > 0.0 for change in normal_changes)
        and normal_changes[-1]["feasibility_rate"] < 0.0
        and normal_changes[-1]["development_false_promotion_rate"] > 0.0
        and blind["best_score"] > normal["best_score"] > 0.0
        and blind_metrics["development_false_promotion_rate"]
        > normal_metrics["development_false_promotion_rate"] > 0.0
        and normal["total_tokens"] != blind["total_tokens"]
        and classical["combined_score"] > 0.99
        and classical["development_proxy_score"] >= 0.999999
        and classical["feasibility_rate"] < 1.0
        and classical["development_false_promotion_rate"] > 0.0
        and classical["robustness_score"] < classical["combined_score"]
        and normal_regimes["near_zero_regime_count"] >= 2
        and normal_regimes["leading_regime_share_of_score_sum"] > 0.70
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": "HEAT_EXCHANGER_MULTIFIDELITY_DIAGNOSTIC_NOT_CAUSAL_POPULATION_OR_EXPERIMENTAL_EVIDENCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_task_source_revision": calibration["source_revision"],
        "input_model_source_revision": (
            next(iter(model_revisions)) if len(model_revisions) == 1 else None
        ),
        "input_source_scope_equivalent": bool(source_equivalent),
        "task_calibration": calibration,
        "records": records,
        "normal_minus_blind_selected_contrast": contrast,
        "within_normal_accepted_step_changes": normal_changes,
        "selected_regime_concentration": {
            "normal_budget_three": normal_regimes,
            "blind_budget_three": blind_regimes,
        },
        "selected_proxy_minus_exact": {
            "normal_budget_three": (
                normal_metrics["development_proxy_score"]
                - normal_metrics["combined_score"]
            ),
            "blind_budget_three": (
                blind_metrics["development_proxy_score"]
                - blind_metrics["combined_score"]
            ),
            "proxy_only_classical": (
                classical["development_proxy_score"]
                - classical["combined_score"]
            ),
        },
        "aggregate_score_blind_spots": {
            "proxy_only_classical_exact_score": classical["combined_score"],
            "proxy_only_classical_exact_feasibility_rate": classical["feasibility_rate"],
            "proxy_only_classical_false_promotion_rate": classical[
                "development_false_promotion_rate"
            ],
            "proxy_only_classical_robustness_score": classical["robustness_score"],
            "normal_selected_exact_score": normal_metrics["combined_score"],
            "normal_selected_proxy_score": normal_metrics["development_proxy_score"],
            "normal_selected_exact_feasibility_rate": normal_metrics["feasibility_rate"],
            "normal_selected_false_promotion_rate": normal_metrics[
                "development_false_promotion_rate"
            ],
        },
        "limitations": [
            "Budget-one, normal budget-three and selection-blind budget-three each have one run; no confidence interval, model ranking or causal feedback estimate is supported.",
            "The Azure endpoint exposes no server-side random seed, so equal local identifiers do not pair generation randomness.",
            "Normal and selection-blind are oracle-call matched but not token- or context-matched; normal used more tokens.",
            "The selection-blind score is an offline best-of-open-loop batch, whereas normal uses online incumbent updates.",
            "Proxy, held-out, false-promotion, per-regime and physical-shift metrics were sealed from proposal and selection state.",
            "The exact evaluator is a correlation-based engineering simulator, not CFD, process-plant or experimental truth; no autonomous scientific-discovery claim is supported.",
            "Near-unity aggregate hypervolume can coexist with infeasible or falsely promoted archive points, so aggregate score must be read with the fidelity and validity vector.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def analyze() -> dict[str, Any]:
    calibration = _load_calibration(CALIBRATION)
    records = {
        label: _load(label, relative) for label, relative in REPORTS.items()
    }
    model_revisions = {record["source_revision"] for record in records.values()}
    source_equivalent = False
    source_changes: list[str] = []
    if len(model_revisions) == 1:
        source_changes = _source_changes(
            calibration["source_revision"], next(iter(model_revisions))
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
