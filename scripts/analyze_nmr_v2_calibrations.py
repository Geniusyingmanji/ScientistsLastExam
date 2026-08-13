#!/usr/bin/env python3
"""Build portable, non-causal evidence from NMR-v2 task/model calibrations."""

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


CALIBRATION = "experiments/nmr_v2_calibration_2026-07-22.json"
REPORTS = {
    "budget_one": "experiments/gpt55_nmr_v2_b1_2026-07-22.json",
    "budget_three": "experiments/gpt55_nmr_v2_b3_2026-07-22.json",
}
TASK = "Spectroscopy/NMRSpectrumFitting"
FIELDS = (
    "combined_score", "mechanism_score", "robustness_score",
    "heldout_mechanism_score", "development_reconstruction_score",
    "heldout_reconstruction_score",
    "development_confidence_calibration_score",
    "heldout_confidence_calibration_score",
    "development_false_discovery_rate", "heldout_false_discovery_rate",
    "development_correct_refusal_rate", "heldout_correct_refusal_rate",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if document.get("trusted_evidence") is not True or document.get("passed") is not True:
        raise ValueError("task calibration is not trusted and passed")
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("task calibration has dirty source")
    classical = document.get("classical_lorentzian_baseline") or {}
    exact = document.get("exact_reference_policy") or {}
    abstain = document.get("always_abstain_baseline") or {}
    required = (
        "combined_score", "robustness_score", "development_reconstruction_score",
        "heldout_reconstruction_score", "development_false_discovery_rate",
        "heldout_false_discovery_rate",
    )
    if any(field not in classical for field in required):
        raise ValueError("task calibration is missing classical metrics")
    if exact.get("combined_score") != 1.0 or exact.get("robustness_score") != 1.0:
        raise ValueError("exact task witness does not score one")
    if abstain.get("combined_score") != 0.0 or abstain.get("robustness_score") != 0.0:
        raise ValueError("always-abstain task witness does not score zero")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "classical_metrics": {field: classical[field] for field in required},
        "exact_reference_score": float(exact["combined_score"]),
        "exact_reference_heldout_score": float(exact["robustness_score"]),
        "always_abstain_score": float(abstain["combined_score"]),
        "always_abstain_heldout_score": float(abstain["robustness_score"]),
    }


def _load(label: str, relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if document.get("trusted_evidence") is not True or document.get("passed") is not True:
        raise ValueError("input report is not trusted and passed: %s" % relative)
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("input report has dirty source: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected exactly one successful run: %s" % relative)
    run = runs[0]
    if (
        run.get("task") != TASK or run.get("algorithm") != "greedy_rewrite"
        or run.get("feedback_mode") != "normal"
    ):
        raise ValueError("unexpected task/algorithm/feedback mode: %s" % relative)
    trajectory = compact_trajectory_snapshot(Path(run["workdir"]) / "trajectory.jsonl")
    if trajectory != run.get("trajectory_snapshot"):
        raise ValueError("portable snapshot disagrees with raw trajectory: %s" % relative)
    events = trajectory["events"]
    parent = events[0]["candidate_sha256"]
    for event in events[1:]:
        if event["parent_sha256"] != parent:
            raise ValueError("accepted-candidate lineage is broken: %s" % relative)
        if event["accepted"]:
            parent = event["candidate_sha256"]
    if int(run["evaluated"]) != int(run["summary"]["oracle_calls"]):
        raise ValueError("oracle-call count mismatch: %s" % relative)
    if abs(float(events[-1]["best_score"]) - float(run["best"])) > 1.0e-12:
        raise ValueError("terminal trajectory best mismatch: %s" % relative)
    selected = max(
        (event for event in events if event["accepted"]),
        key=lambda event: int(event["step"]),
    )
    if abs(float(selected["score"]) - float(run["best"])) > 1.0e-12:
        raise ValueError("accepted candidate disagrees with run best: %s" % relative)
    return {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(path),
        "trajectory_sha256": trajectory["trajectory_sha256"],
        "source_revision": provenance["git_revision"],
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
        "feedback_scope": run["summary"].get("feedback_scope"),
        "trajectory": [
            {
                "step": int(event["step"]),
                "accepted": bool(event["accepted"]),
                "valid": bool(event["metrics"].get("valid")),
                "candidate_sha256": event["candidate_sha256"],
                "parent_sha256": event["parent_sha256"],
                **{field: event["metrics"].get(field) for field in FIELDS},
            }
            for event in events
        ],
    }


def _selected(record: dict[str, Any]) -> dict[str, Any]:
    step = int(record["selected_step"])
    return next(event for event in record["trajectory"] if event["step"] == step)


def _analyze_records(calibration: dict[str, Any],
                     records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    budget_one = records["budget_one"]
    budget_three = records["budget_three"]
    selected_one = _selected(budget_one)
    selected_three = _selected(budget_three)
    proposals_three = budget_three["trajectory"][1:]
    rejected_after_feedback = [
        event for event in proposals_three
        if event["step"] > selected_three["step"] and not event["accepted"]
    ]
    classical = calibration["classical_metrics"]
    common_revision = {
        calibration["source_revision"],
        *(record["source_revision"] for record in records.values()),
    }
    execution_passed = bool(
        len(common_revision) == 1
        and budget_one["proposal_budget"] == 1
        and budget_three["proposal_budget"] == 3
        and budget_one["oracle_calls"] == 2
        and budget_three["oracle_calls"] == 4
        and not budget_one["server_side_seed_control"]
        and not budget_three["server_side_seed_control"]
        and all(event["valid"] for record in records.values()
                for event in record["trajectory"])
        and selected_one["combined_score"] > classical["combined_score"]
        and selected_one["combined_score"] < 0.90
        and selected_one["robustness_score"] < selected_one["combined_score"]
        and selected_one["development_reconstruction_score"] > 0.80
        and selected_one["heldout_reconstruction_score"] > 0.80
        and selected_one["development_false_discovery_rate"] > 0.0
        and selected_one["heldout_false_discovery_rate"] > 0.0
        and selected_three["step"] == 1
        and len(rejected_after_feedback) == 2
        and all(event["combined_score"] < selected_three["combined_score"]
                for event in rejected_after_feedback)
        and all(event["development_reconstruction_score"] > 0.75
                for event in rejected_after_feedback)
        and all(event["development_false_discovery_rate"] == 1.0
                and event["heldout_false_discovery_rate"] == 1.0
                for event in rejected_after_feedback)
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": "NMR_CALIBRATION_NOT_CAUSAL_OR_POPULATION_EVIDENCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_source_revision": (
            next(iter(common_revision)) if len(common_revision) == 1 else None
        ),
        "task_calibration": calibration,
        "records": records,
        "budget_one_minus_classical": {
            field: float(selected_one[field]) - float(classical[field])
            for field in classical
        },
        "selected_model_conditions": {
            "budget_one": {field: selected_one[field] for field in FIELDS},
            "budget_three": {field: selected_three[field] for field in FIELDS},
        },
        "budget_three_rejected_after_feedback": [
            {
                "step": event["step"],
                "candidate_sha256": event["candidate_sha256"],
                "parent_sha256": event["parent_sha256"],
                **{field: event[field] for field in FIELDS},
                "development_score_change_from_selected_parent": (
                    event["combined_score"] - selected_three["combined_score"]
                ),
                "development_reconstruction_change_from_selected_parent": (
                    event["development_reconstruction_score"]
                    - selected_three["development_reconstruction_score"]
                ),
            }
            for event in rejected_after_feedback
        ],
        "limitations": [
            "Each budget condition has one independent run; no population or causal feedback estimate is supported.",
            "Budget-one and budget-three use different local identifiers and are not prefixes of one trajectory.",
            "The Azure endpoint exposes no server-side model seed, so replicate identifiers do not control generation randomness.",
            "Held-out mechanism, reconstruction, confidence, refusal and per-instance metrics were sealed from proposal and selection state.",
            "The classical baseline and GPT-5.5 runs are task-calibration contrasts, not a model leaderboard or evidence from experimental NMR data.",
            "Rejected budget-three candidates diagnose failure modes but do not show that feedback caused them; no matched no-feedback treatment was run.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def analyze() -> dict[str, Any]:
    calibration = _load_calibration(CALIBRATION)
    records = {
        label: _load(label, relative) for label, relative in REPORTS.items()
    }
    return _analyze_records(calibration, records)


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
