#!/usr/bin/env python3
"""Build a portable, non-causal analysis of the three Truss-v2 calibrations."""

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

from sle.protocol import compact_trajectory_snapshot  # noqa: E402
from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402


REPORTS = {
    "budget_one": "experiments/gpt55_truss_v2_b1_2026-07-21.json",
    "normal_budget_three": "experiments/gpt55_truss_v2_b3_2026-07-21.json",
    "blind_budget_three": "experiments/gpt55_truss_v2_blind_b3_2026-07-21.json",
}
TASK = "StructuralEngineering/TrussWeightMinimization"
SCIENCE_FIELDS = (
    "combined_score",
    "robustness_score",
    "heldout_policy_score",
    "heldout_robustness_score",
    "mean_shifted_case_feasibility_rate",
    "mean_shifted_constraint_feasibility_rate",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    trajectory = compact_trajectory_snapshot(Path(run["workdir"]) / "trajectory.jsonl")
    if trajectory != run.get("trajectory_snapshot"):
        raise ValueError("portable snapshot disagrees with raw trajectory: %s" % relative)
    if int(run.get("evaluated", -1)) != int(run["summary"].get("oracle_calls", -2)):
        raise ValueError("oracle-call count mismatch: %s" % relative)
    events = trajectory["events"]
    baseline_hash = events[0]["candidate_sha256"]
    proposals = events[1:]
    if label == "blind_budget_three":
        if not all(event["parent_sha256"] == baseline_hash for event in proposals):
            raise ValueError("selection-blind proposal changed parent")
        if run["summary"].get("selection_policy") != "offline_best_of_open_loop_batch":
            raise ValueError("selection-blind policy metadata is missing")
    if label == "normal_budget_three":
        parent = baseline_hash
        for event in proposals:
            if event["parent_sha256"] != parent:
                raise ValueError("normal accepted-candidate lineage is broken")
            if event["accepted"]:
                parent = event["candidate_sha256"]

    selected = max(
        (event for event in events if event["accepted"]),
        key=lambda event: int(event["step"]),
    )
    if abs(float(selected["best_score"]) - float(run["best"])) > 1e-12:
        raise ValueError("selected event disagrees with run best: %s" % relative)
    return {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(path),
        "trajectory_sha256": trajectory["trajectory_sha256"],
        "source_revision": provenance["git_revision"],
        "feedback_mode": run["feedback_mode"],
        "feedback_scope": run["summary"].get("feedback_scope"),
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
        "selected_metrics": {
            field: selected["metrics"].get(field) for field in SCIENCE_FIELDS
        },
        "trajectory": [
            {
                "step": int(event["step"]),
                "accepted": bool(event["accepted"]),
                "valid": bool(event["metrics"].get("valid")),
                "candidate_sha256": event["candidate_sha256"],
                "parent_sha256": event["parent_sha256"],
                **{field: event["metrics"].get(field) for field in SCIENCE_FIELDS},
            }
            for event in events
        ],
    }


def _analyze_records(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Analyze already validated records; kept pure for portable unit tests."""
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    normal_metrics = normal["selected_metrics"]
    blind_metrics = blind["selected_metrics"]
    contrast = {
        field: float(normal_metrics[field]) - float(blind_metrics[field])
        for field in SCIENCE_FIELDS
    }
    contrast["total_tokens"] = normal["total_tokens"] - blind["total_tokens"]
    contrast["oracle_calls"] = normal["oracle_calls"] - blind["oracle_calls"]

    normal_events = normal["trajectory"]
    final_visible_gain = (
        normal_events[-1]["combined_score"] - normal_events[-2]["combined_score"]
    )
    final_heldout_robustness_change = (
        normal_events[-1]["heldout_robustness_score"]
        - normal_events[-2]["heldout_robustness_score"]
    )
    common_revision = {record["source_revision"] for record in records.values()}
    execution_passed = bool(
        len(common_revision) == 1
        and records["budget_one"]["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and normal["oracle_calls"] == blind["oracle_calls"] == 4
        and all(not record["server_side_seed_control"] for record in records.values())
        and normal["best_score"] > blind["best_score"]
        and final_visible_gain > 0.0
        and final_heldout_robustness_change < 0.0
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": "TRUSS_HEADROOM_DIAGNOSTIC_NOT_CAUSAL_OR_POPULATION_EVIDENCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_source_revision": next(iter(common_revision)) if len(common_revision) == 1 else None,
        "records": records,
        "normal_minus_blind_selected_contrast": contrast,
        "within_normal_final_accepted_change": {
            "development_score": final_visible_gain,
            "heldout_policy_score": (
                normal_events[-1]["heldout_policy_score"]
                - normal_events[-2]["heldout_policy_score"]
            ),
            "heldout_robustness_score": final_heldout_robustness_change,
        },
        "limitations": [
            "Normal and selection-blind each have one replicate identifier; no confidence interval or causal feedback claim is supported.",
            "The Azure endpoint exposes no server-side random seed, so equal local identifiers do not imply paired model randomness.",
            "Normal used more tokens than selection-blind, so the conditions are call-matched but not token- or context-matched.",
            "Budget-one uses a different local identifier and is an independent calibration, not a prefix of the budget-three trajectory.",
            "Held-out and shifted metrics were sealed from proposal and selection state throughout all conditions.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def analyze() -> dict[str, Any]:
    records = {
        label: _load(label, relative) for label, relative in REPORTS.items()
    }
    return _analyze_records(records)


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
