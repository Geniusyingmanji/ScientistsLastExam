#!/usr/bin/env python3
"""Build portable, non-causal evidence from BroadbandAbsorber-v2 calibrations."""

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


REPORTS = {
    "budget_one": "experiments/gpt55_absorber_v2_b1_2026-07-23.json",
    "normal_budget_three": "experiments/gpt55_absorber_v2_b3_2026-07-23.json",
    "blind_budget_three": (
        "experiments/gpt55_absorber_v2_blind_b3_2026-07-23.json"
    ),
}
TASK = "AcousticMetamaterials/BroadbandAbsorber"
EXPECTED_SOURCE_REVISION = "3e4333a0ec9eab13d644f368886749bc3ca2fe7f"
SCALAR_FIELDS = (
    "combined_score",
    "robustness_score",
    "development_validation_gap",
    "heldout_policy_score",
    "heldout_robustness_score",
    "development_exact_utility",
    "heldout_exact_utility",
    "development_proxy_utility",
    "heldout_proxy_utility",
    "development_mean_absorption",
    "heldout_mean_absorption",
    "development_twentieth_percentile_absorption",
    "heldout_twentieth_percentile_absorption",
    "development_coverage_above_half",
    "heldout_coverage_above_half",
    "feasibility_rate",
    "heldout_feasibility_rate",
    "candidate_instance_call_count",
    "candidate_instance_valid_rate",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mean(values: list[float]) -> float:
    if not values:
        raise ValueError("cannot average an empty collection")
    return float(sum(values) / len(values))


def _split_axes(metrics: dict[str, Any], split: str) -> dict[str, Any]:
    prefix = "development" if split == "development" else "heldout"
    score_key = "combined_score" if split == "development" else "heldout_policy_score"
    robustness_key = (
        "robustness_score" if split == "development"
        else "heldout_robustness_score"
    )
    rows = [row for row in metrics["per_instance"] if row["split"] == split]
    expected_count = 4 if split == "development" else 2
    if len(rows) != expected_count or not all(row.get("valid") is True for row in rows):
        raise ValueError("selected %s instances are incomplete or invalid" % split)

    manufacturing = [
        (row, shift)
        for row in rows
        for shift in row["shifted"]
        if str(shift["name"]).startswith("manufacturing_")
    ]
    failures = [
        {
            "instance": row["name"],
            "shift": shift["name"],
        }
        for row, shift in manufacturing
        if not bool(shift["geometry_feasible"])
    ]
    exact = float(metrics[prefix + "_exact_utility"])
    proxy = float(metrics[prefix + "_proxy_utility"])
    nominal_score = float(metrics[score_key])
    robustness_score = float(metrics[robustness_key])
    return {
        "instance_count": len(rows),
        "nominal_visible_score": nominal_score,
        "sealed_robustness_score": robustness_score,
        "robustness_retention_ratio": (
            robustness_score / nominal_score if nominal_score > 0.0 else None
        ),
        "exact_distributed_model_utility": exact,
        "public_proxy_utility": proxy,
        "proxy_minus_distributed_utility": proxy - exact,
        "mean_absorption": float(metrics[prefix + "_mean_absorption"]),
        "twentieth_percentile_absorption": float(
            metrics[prefix + "_twentieth_percentile_absorption"]
        ),
        "coverage_above_half": float(
            metrics[prefix + "_coverage_above_half"]
        ),
        "artifact_feasibility_rate": float(
            metrics[
                "feasibility_rate"
                if split == "development" else "heldout_feasibility_rate"
            ]
        ),
        "mean_worst_shift_utility": _mean([
            float(row["robust_utility"]) for row in rows
        ]),
        "mean_all_shift_geometry_feasibility_rate": _mean([
            float(row["shift_geometry_feasibility_rate"]) for row in rows
        ]),
        "manufacturing_shift_geometry_feasibility_rate": _mean([
            float(bool(shift["geometry_feasible"]))
            for _, shift in manufacturing
        ]),
        "manufacturing_geometry_failures": failures,
    }


def _selected_event(events: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [event for event in events if event["accepted"]]
    if not accepted:
        raise ValueError("trajectory has no selected baseline or proposal")
    return max(accepted, key=lambda event: int(event["step"]))


def _load(label: str, relative: str) -> dict[str, Any]:
    report_path = ROOT / relative
    document = json.loads(report_path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if document.get("trusted_evidence") is not True or document.get("passed") is not True:
        raise ValueError("input report is not trusted and passed: %s" % relative)
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("input report has dirty source provenance: %s" % relative)
    if provenance.get("source_changes") != []:
        raise ValueError("input report records source changes: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected exactly one successful run: %s" % relative)
    run = runs[0]
    if run.get("task") != TASK or run.get("algorithm") != "greedy_rewrite":
        raise ValueError("unexpected task or algorithm: %s" % relative)

    workdir = Path(run["workdir"])
    trajectory_path = workdir / "trajectory.jsonl"
    raw_events = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable snapshot disagrees with raw trajectory: %s" % relative)
    if len(raw_events) != len(snapshot["events"]):
        raise ValueError("raw and compact event counts disagree: %s" % relative)
    if int(run["evaluated"]) != int(run["summary"].get("oracle_calls", -1)):
        raise ValueError("run oracle-call count mismatch: %s" % relative)
    if int(raw_events[-1]["oracle_calls"]) != int(run["evaluated"]):
        raise ValueError("trajectory oracle-call count mismatch: %s" % relative)

    events = snapshot["events"]
    baseline_hash = events[0]["candidate_sha256"]
    proposals = events[1:]
    expected_mode = "selection_blind" if label == "blind_budget_three" else "normal"
    if run.get("feedback_mode") != expected_mode:
        raise ValueError("unexpected feedback mode: %s" % relative)
    if label == "blind_budget_three":
        if not all(event["parent_sha256"] == baseline_hash for event in proposals):
            raise ValueError("selection-blind proposal changed frozen parent")
        if run["summary"].get("selection_policy") != "offline_best_of_open_loop_batch":
            raise ValueError("selection-blind policy metadata is missing")
    else:
        parent = baseline_hash
        for event in proposals:
            if event["parent_sha256"] != parent:
                raise ValueError("normal incumbent lineage is broken: %s" % relative)
            if event["accepted"]:
                parent = event["candidate_sha256"]
        if run["summary"].get("selection_policy") != "online_incumbent":
            raise ValueError("normal selection policy metadata is missing")

    selected = _selected_event(events)
    selected_raw = raw_events[int(selected["step"])]
    if selected_raw["candidate_sha256"] != selected["candidate_sha256"]:
        raise ValueError("raw selected candidate disagrees with snapshot: %s" % relative)
    if abs(float(selected["best_score"]) - float(run["best"])) > 1.0e-12:
        raise ValueError("selected event disagrees with run best: %s" % relative)
    if _sha256(workdir / "best_program.py") != selected["candidate_sha256"]:
        raise ValueError("best-program artifact disagrees with selected hash: %s" % relative)

    metrics = selected_raw.get("metrics") or {}
    selected_valid = bool(metrics.get("valid"))
    axes = None
    if selected_valid:
        if not isinstance(metrics.get("per_instance"), list):
            raise ValueError("selected valid event lacks per-instance evidence")
        axes = {
            "development": _split_axes(metrics, "development"),
            "heldout": _split_axes(metrics, "heldout"),
            "development_nominal_minus_robustness_score": float(
                metrics["development_validation_gap"]
            ),
        }

    proposal_valid_count = sum(bool(event["metrics"].get("valid")) for event in proposals)
    failure_counts: dict[str, int] = {}
    for event in proposals:
        kind = event["metrics"].get("candidate_failure_kind")
        if kind:
            failure_counts[str(kind)] = failure_counts.get(str(kind), 0) + 1

    config = document["config"]
    return {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(report_path),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "llm_condition_sha256": config.get("llm_condition_sha256"),
        "model": config["llm"].get("model"),
        "server_side_seed_control": bool(
            config["llm"].get("server_side_seed_control")
        ),
        "feedback_mode": run["feedback_mode"],
        "feedback_scope": run["summary"].get("feedback_scope"),
        "selection_policy": run["summary"].get("selection_policy"),
        "seed": int(run["seed"]),
        "proposal_budget": int(config["budget"]),
        "oracle_calls": int(run["summary"]["oracle_calls"]),
        "total_tokens": int(run["summary"]["llm"]["total_tokens"]),
        "best_score": float(run["best"]),
        "selected_step": int(selected["step"]),
        "selected_candidate_sha256": selected["candidate_sha256"],
        "selected_artifact_valid": selected_valid,
        "selected_axes": axes,
        "proposal_valid_count": proposal_valid_count,
        "proposal_valid_rate": proposal_valid_count / len(proposals),
        "proposal_failure_counts": failure_counts,
        "trajectory": [
            {
                "step": int(event["step"]),
                "accepted": bool(event["accepted"]),
                "valid": bool(event["metrics"].get("valid")),
                "candidate_sha256": event["candidate_sha256"],
                "parent_sha256": event["parent_sha256"],
                "candidate_failure_kind": event["metrics"].get(
                    "candidate_failure_kind"
                ),
                **{
                    field: event["metrics"].get(field)
                    for field in SCALAR_FIELDS
                },
            }
            for event in events
        ],
    }


def _selected_contrast(normal: dict[str, Any], blind: dict[str, Any]) -> dict[str, Any]:
    n = normal["selected_axes"]
    b = blind["selected_axes"]
    result: dict[str, Any] = {
        "development_nominal_visible_score": (
            n["development"]["nominal_visible_score"]
            - b["development"]["nominal_visible_score"]
        ),
        "heldout_nominal_visible_score": (
            n["heldout"]["nominal_visible_score"]
            - b["heldout"]["nominal_visible_score"]
        ),
        "development_sealed_robustness_score": (
            n["development"]["sealed_robustness_score"]
            - b["development"]["sealed_robustness_score"]
        ),
        "heldout_sealed_robustness_score": (
            n["heldout"]["sealed_robustness_score"]
            - b["heldout"]["sealed_robustness_score"]
        ),
        "development_robustness_retention_ratio": (
            n["development"]["robustness_retention_ratio"]
            - b["development"]["robustness_retention_ratio"]
        ),
        "heldout_robustness_retention_ratio": (
            n["heldout"]["robustness_retention_ratio"]
            - b["heldout"]["robustness_retention_ratio"]
        ),
        "development_exact_distributed_model_utility": (
            n["development"]["exact_distributed_model_utility"]
            - b["development"]["exact_distributed_model_utility"]
        ),
        "heldout_exact_distributed_model_utility": (
            n["heldout"]["exact_distributed_model_utility"]
            - b["heldout"]["exact_distributed_model_utility"]
        ),
        "development_proxy_minus_distributed_utility": (
            n["development"]["proxy_minus_distributed_utility"]
            - b["development"]["proxy_minus_distributed_utility"]
        ),
        "heldout_proxy_minus_distributed_utility": (
            n["heldout"]["proxy_minus_distributed_utility"]
            - b["heldout"]["proxy_minus_distributed_utility"]
        ),
        "development_mean_absorption": (
            n["development"]["mean_absorption"]
            - b["development"]["mean_absorption"]
        ),
        "heldout_mean_absorption": (
            n["heldout"]["mean_absorption"]
            - b["heldout"]["mean_absorption"]
        ),
        "development_twentieth_percentile_absorption": (
            n["development"]["twentieth_percentile_absorption"]
            - b["development"]["twentieth_percentile_absorption"]
        ),
        "heldout_twentieth_percentile_absorption": (
            n["heldout"]["twentieth_percentile_absorption"]
            - b["heldout"]["twentieth_percentile_absorption"]
        ),
        "development_coverage_above_half": (
            n["development"]["coverage_above_half"]
            - b["development"]["coverage_above_half"]
        ),
        "heldout_coverage_above_half": (
            n["heldout"]["coverage_above_half"]
            - b["heldout"]["coverage_above_half"]
        ),
        "development_manufacturing_geometry_feasibility_rate": (
            n["development"]["manufacturing_shift_geometry_feasibility_rate"]
            - b["development"]["manufacturing_shift_geometry_feasibility_rate"]
        ),
        "heldout_manufacturing_geometry_feasibility_rate": (
            n["heldout"]["manufacturing_shift_geometry_feasibility_rate"]
            - b["heldout"]["manufacturing_shift_geometry_feasibility_rate"]
        ),
        "development_nominal_minus_robustness_score": (
            n["development_nominal_minus_robustness_score"]
            - b["development_nominal_minus_robustness_score"]
        ),
        "proposal_valid_rate": (
            normal["proposal_valid_rate"] - blind["proposal_valid_rate"]
        ),
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
    }
    return result


def _analyze_records(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    source_scopes = {
        tuple(record["source_scope"] or []) for record in records.values()
    }
    llm_conditions = {
        record["llm_condition_sha256"] for record in records.values()
    }
    contrast = _selected_contrast(normal, blind)
    execution_passed = bool(
        revisions == {EXPECTED_SOURCE_REVISION}
        and len(source_scopes) == 1
        and len(llm_conditions) == 1
        and None not in llm_conditions
        and all(record["model"] == "gpt-5.5" for record in records.values())
        and all(
            not record["server_side_seed_control"] for record in records.values()
        )
        and one["feedback_mode"] == normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["seed"] == 0
        and normal["seed"] == blind["seed"] == 1
        and one["oracle_calls"] == 2
        and normal["oracle_calls"] == blind["oracle_calls"] == 4
        and all(
            record["selected_artifact_valid"] for record in records.values()
        )
        and one["selected_step"] == 0
        and normal["selected_step"] == 1
        and blind["selected_step"] == 2
        and normal["best_score"] > 0.9
        and blind["best_score"] > 0.9
        and normal["selected_axes"]["development"][
            "sealed_robustness_score"
        ] > 0.8
        and blind["selected_axes"]["development"][
            "sealed_robustness_score"
        ] < 0.5
        and contrast["development_sealed_robustness_score"] > 0.4
        and contrast["heldout_sealed_robustness_score"] > 0.4
        and contrast[
            "development_manufacturing_geometry_feasibility_rate"
        ] > 0.0
        and contrast["oracle_calls"] == 0
        and contrast["total_tokens"] != 0
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "ABSORBER_SINGLE_RUN_CALIBRATION_NOT_CAUSAL_OR_POPULATION_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_source_revision": (
            next(iter(revisions)) if len(revisions) == 1 else None
        ),
        "input_source_scope_equivalent": len(source_scopes) == 1,
        "input_llm_condition_equivalent": len(llm_conditions) == 1,
        "records": records,
        "normal_minus_blind_selected_contrast": contrast,
        "descriptive_findings": {
            "near_equal_visible_development_scores": (
                abs(contrast["development_nominal_visible_score"]) < 0.01
            ),
            "normal_has_higher_sealed_robustness": (
                contrast["development_sealed_robustness_score"] > 0.0
                and contrast["heldout_sealed_robustness_score"] > 0.0
            ),
            "blind_has_manufacturing_geometry_failures": bool(
                blind["selected_axes"]["development"][
                    "manufacturing_geometry_failures"
                ]
                or blind["selected_axes"]["heldout"][
                    "manufacturing_geometry_failures"
                ]
            ),
            "normal_selected_has_no_manufacturing_geometry_failures": not bool(
                normal["selected_axes"]["development"][
                    "manufacturing_geometry_failures"
                ]
                or normal["selected_axes"]["heldout"][
                    "manufacturing_geometry_failures"
                ]
            ),
        },
        "limitations": [
            "Each condition has one run; no confidence interval, population estimate or leaderboard claim is supported.",
            "The Azure endpoint exposes no server-side generation seed, so equal local identifiers do not pair model randomness.",
            "Normal and selection-blind used different token counts; their one-run contrast is neither token-matched nor causal.",
            "Budget one uses a different local identifier and is an independent calibration, not a prefix of budget three.",
            "Held-out, proxy-gap, absorption-component, per-instance and shifted robustness metrics were sealed from proposal and selection state.",
            "The local reduced-order acoustic model omits several engineering effects; thermoviscous finite-element and impedance-tube replication remain required.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def analyze() -> dict[str, Any]:
    return _analyze_records({
        label: _load(label, relative) for label, relative in REPORTS.items()
    })


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
