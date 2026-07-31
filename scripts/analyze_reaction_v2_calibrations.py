#!/usr/bin/env python3
"""Build portable, non-causal evidence from ReactionMechanismFitting-v2 runs."""

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

from frontier_science.protocol import compact_trajectory_snapshot  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402
from frontier_science.runtime_migration import runtime_source_changes  # noqa: E402


CALIBRATION = "experiments/reaction_mechanism_v2_calibration_2026-07-22.json"
REPORTS = {
    "budget_one": "experiments/gpt55_reaction_v2_b1_2026-07-22.json",
    "normal_budget_three": "experiments/gpt55_reaction_v2_b3_2026-07-22.json",
    "blind_budget_three": "experiments/gpt55_reaction_v2_blind_b3_2026-07-22.json",
}
TASK = "ChemicalKinetics/ReactionMechanismFitting"
SOURCE_SCOPE = (
    "frontier_science", "scripts", "tests", "benchmarks",
    "requirements-upstream.txt",
)
FIELDS = (
    "combined_score", "mechanism_score", "robustness_score",
    "heldout_mechanism_score", "development_support_f1",
    "heldout_support_f1", "development_rate_curve_score",
    "heldout_rate_curve_score", "development_prediction_score",
    "heldout_prediction_score", "development_extrapolation_score",
    "heldout_extrapolation_score",
    "development_misspecified_prediction_score",
    "heldout_misspecified_prediction_score",
    "development_confidence_calibration_score",
    "heldout_confidence_calibration_score",
    "development_false_discovery_rate", "heldout_false_discovery_rate",
    "development_correct_refusal_rate", "heldout_correct_refusal_rate",
    "mean_experiment_calls", "mean_experiment_budget_units", "valid",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, SOURCE_SCOPE, root=ROOT)


def _scalar_view(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in FIELDS}


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if document.get("trusted_evidence") is not True or document.get("passed") is not True:
        raise ValueError("task calibration is not trusted and passed")
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("task calibration source was dirty")
    baseline = document.get("always_abstain_baseline") or {}
    classical = document.get("truth_blind_classical_fit") or {}
    ranks = document.get("four_assay_identifiability_checks") or []
    conservation = document.get("mass_conservation_checks") or []
    if baseline.get("combined_score") != 0.0 or baseline.get("robustness_score") != 0.0:
        raise ValueError("always-abstain anchor does not score zero")
    if not 0.3 <= float(classical.get("combined_score", -1.0)) <= 0.8:
        raise ValueError("classical task difficulty is outside its gate")
    if len(ranks) != 7 or not all(row.get("passed") for row in ranks):
        raise ValueError("identifiability checks did not pass")
    if len(conservation) != 11 or not all(row.get("passed") for row in conservation):
        raise ValueError("mass-conservation checks did not pass")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "always_abstain_metrics": _scalar_view(baseline),
        "classical_metrics": _scalar_view(classical),
        "maximum_identifiability_condition_number": max(
            float(row["condition_number"]) for row in ranks
        ),
        "maximum_mass_balance_error": max(
            float(row["maximum_mass_balance_error"]) for row in conservation
        ),
    }


def _selected_event(events: list[dict[str, Any]], best: float) -> dict[str, Any]:
    matching = [
        event for event in events if event.get("accepted")
        and abs(float(event["score"]) - float(best)) <= 1e-12
    ]
    if not matching:
        raise ValueError("no accepted event matches run best")
    return min(matching, key=lambda event: int(event["step"]))


def _load(label: str, relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if document.get("trusted_evidence") is not True or document.get("passed") is not True:
        raise ValueError("model report is not trusted and passed: %s" % relative)
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("model report source was dirty: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected exactly one successful run: %s" % relative)
    run = runs[0]
    if run.get("task") != TASK or run.get("algorithm") != "greedy_rewrite":
        raise ValueError("unexpected task or algorithm: %s" % relative)
    trajectory_path = Path(run["workdir"]) / "trajectory.jsonl"
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable snapshot differs from raw trajectory: %s" % relative)
    events = snapshot["events"]
    proposals = events[1:]
    baseline_hash = events[0]["candidate_sha256"]
    if label == "blind_budget_three":
        if run.get("feedback_mode") != "selection_blind":
            raise ValueError("blind run has incorrect feedback mode")
        if run["summary"].get("selection_policy") != "offline_best_of_open_loop_batch":
            raise ValueError("blind run lacks offline-selection semantics")
        if not all(event["parent_sha256"] == baseline_hash for event in proposals):
            raise ValueError("blind proposal parent was not frozen")
    else:
        if run.get("feedback_mode") != "normal":
            raise ValueError("normal run has incorrect feedback mode")
        parent = baseline_hash
        for event in proposals:
            if event["parent_sha256"] != parent:
                raise ValueError("normal incumbent lineage is broken")
            if event["accepted"]:
                parent = event["candidate_sha256"]
    if int(run["evaluated"]) != int(run["summary"]["oracle_calls"]):
        raise ValueError("oracle-call count mismatch")
    if sum(bool(event["accepted"]) for event in proposals) != int(run["accepted"]):
        raise ValueError("accepted count mismatch")
    selected = _selected_event(events, float(run["best"]))
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
        "selected_metrics": _scalar_view(selected["metrics"]),
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


def _analyze_records(calibration: dict[str, Any],
                     records: dict[str, dict[str, Any]],
                     source_equivalent: bool = True) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    blind_proposals = blind["trajectory"][1:]
    blind_selected = blind["selected_metrics"]
    high_prediction = max(
        blind_proposals, key=lambda event: float(event["development_prediction_score"])
    )
    model_revisions = {record["source_revision"] for record in records.values()}
    contrast = {
        field: float(normal["selected_metrics"][field])
        - float(blind_selected[field])
        for field in FIELDS if field != "valid"
    }
    contrast.update({
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
    })
    execution_passed = bool(
        source_equivalent
        and len(model_revisions) == 1
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["oracle_calls"] == 2
        and normal["oracle_calls"] == blind["oracle_calls"] == 4
        and one["feedback_mode"] == normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and all(not record["server_side_seed_control"] for record in records.values())
        and one["selected_step"] == normal["selected_step"] == 0
        and all(not event["accepted"] for event in normal["trajectory"][1:])
        and all(event["combined_score"] == 0.0
                and event["mean_experiment_calls"] == 1.0
                for event in normal["trajectory"][1:])
        and blind["selected_step"] == 1
        and blind["best_score"] > 0.3
        and blind_selected["robustness_score"] > 0.3
        and blind_selected["development_support_f1"] > 0.6
        and blind_selected["development_false_discovery_rate"] == 0.5
        and blind_selected["heldout_false_discovery_rate"] == 0.5
        and high_prediction["development_prediction_score"] > 0.70
        and high_prediction["development_extrapolation_score"] > 0.70
        and high_prediction["combined_score"] < 0.30
        and high_prediction["development_false_discovery_rate"] == 0.5
        and normal["total_tokens"] != blind["total_tokens"]
        and calibration["classical_metrics"]["combined_score"] > blind["best_score"]
        and calibration["classical_metrics"]["development_prediction_score"]
        > calibration["classical_metrics"]["combined_score"] + 0.3
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": "REACTION_MECHANISM_CALIBRATION_NOT_CAUSAL_POPULATION_OR_WET_LAB_EVIDENCE",
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
        "prediction_mechanism_refusal_counterexample": {
            field: high_prediction[field]
            for field in ("step", "candidate_sha256", *FIELDS)
        },
        "science_vectors": {
            "classical_truth_blind": {
                "optimization_O": calibration["classical_metrics"]["combined_score"],
                "fidelity_F": calibration["classical_metrics"]["heldout_prediction_score"],
                "mechanism_M": calibration["classical_metrics"]["mechanism_score"],
                "validity_V": calibration["classical_metrics"]["robustness_score"],
                "refusal_R": 1.0 - calibration["classical_metrics"]["development_false_discovery_rate"],
            },
            "gpt55_blind_selected": {
                "optimization_O": blind_selected["combined_score"],
                "fidelity_F": blind_selected["heldout_prediction_score"],
                "mechanism_M": blind_selected["mechanism_score"],
                "validity_V": blind_selected["robustness_score"],
                "refusal_R": 1.0 - blind_selected["development_false_discovery_rate"],
            },
        },
        "limitations": [
            "Each condition has one run; no confidence interval, model ranking or causal feedback estimate is supported.",
            "Normal and selection-blind share a local identifier but Azure exposes no server-side model seed, so generation randomness is not paired.",
            "The conditions are oracle-call matched but not token- or context-matched; selection-blind is offline best-of-batch while normal uses online incumbent selection.",
            "The normal run never accepted a proposal, so later prompts retained the same zero-score baseline; this diagnoses sparse aggregate feedback but not a causal feedback effect.",
            "Prediction, extrapolation, held-out mechanism, confidence, refusal and per-world metrics were sealed from proposal and selection state.",
            "The oracle is a synthetic unimolecular kinetics laboratory, not wet-lab evidence; no autonomous scientific-discovery claim is supported.",
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
    source_changes: list[str] = []
    source_equivalent = False
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
