#!/usr/bin/env python3
"""Build portable evidence from GravityInversion-v2 task/model calibrations."""

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


CALIBRATION = "experiments/gravity_v2_calibration_2026-07-22.json"
REPORTS = {
    "budget_one": "experiments/gpt55_gravity_v2_b1_2026-07-22.json",
    "budget_three": "experiments/gpt55_gravity_v2_b3_2026-07-22.json",
}
TASK = "Geophysics/GravityInversion"
SOURCE_SCOPE = (
    "sle", "scripts", "tests", "benchmarks",
    "requirements-upstream.txt",
)
FIELDS = (
    "combined_score", "mechanism_score", "robustness_score",
    "heldout_mechanism_score", "development_body_support_f1",
    "heldout_body_support_f1", "development_field_component_score",
    "heldout_field_component_score", "development_mass_moment_score",
    "heldout_mass_moment_score", "development_observed_fit_score",
    "heldout_observed_fit_score", "development_prediction_score",
    "heldout_prediction_score", "development_extrapolation_score",
    "heldout_extrapolation_score", "development_false_discovery_rate",
    "heldout_false_discovery_rate", "development_correct_refusal_rate",
    "heldout_correct_refusal_rate", "mean_survey_calls",
    "mean_survey_budget_units", "valid", "error_message",
)
WORLD_FIELDS = (
    "split", "world_index", "kind", "mechanism_score",
    "body_support_f1", "field_component_score", "mass_moment_score",
    "observed_fit_score", "interpolation_prediction_score",
    "extrapolation_prediction_score", "correct_refusal",
    "false_discovery", "abstained", "n_true_bodies",
    "n_predicted_bodies", "survey_calls", "survey_budget_units",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, SOURCE_SCOPE, root=ROOT)


def _scalar(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in FIELDS}


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if document.get("trusted_evidence") is not True or document.get("passed") is not True:
        raise ValueError("gravity task calibration is not trusted and passed")
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("gravity task calibration source was dirty")
    baseline = document.get("always_abstain_baseline") or {}
    classical = document.get("truth_blind_classical_fit") or {}
    ranks = document.get("multiheight_identifiability_checks") or []
    quadrature = document.get("independent_quadrature_checks") or []
    if baseline.get("combined_score") != 0.0 or baseline.get("robustness_score") != 0.0:
        raise ValueError("gravity always-abstain anchor is not zero")
    if not 0.3 <= float(classical.get("combined_score", -1.0)) <= 0.85:
        raise ValueError("gravity classical difficulty is outside its gate")
    if len(ranks) != 7 or not all(row.get("passed") for row in ranks):
        raise ValueError("gravity identifiability checks did not pass")
    if len(quadrature) != 20 or not all(row.get("passed") for row in quadrature):
        raise ValueError("gravity independent physics checks did not pass")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "classical_metrics": _scalar(classical),
        "maximum_condition_number": max(
            float(row["condition_number"]) for row in ranks
        ),
        "maximum_quadrature_error_mgal": max(
            float(row["maximum_absolute_error_mgal"]) for row in quadrature
        ),
    }


def _selected(events: list[dict[str, Any]], best: float) -> dict[str, Any]:
    matches = [
        event for event in events if event["accepted"]
        and abs(float(event["score"]) - float(best)) <= 1e-12
    ]
    if not matches:
        raise ValueError("no accepted event matches gravity run best")
    return min(matches, key=lambda event: int(event["step"]))


def _load(label: str, relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if document.get("trusted_evidence") is not True or document.get("passed") is not True:
        raise ValueError("gravity model report is not trusted and passed")
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("gravity model report source was dirty")
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one successful gravity run")
    run = runs[0]
    if (
        run.get("task") != TASK or run.get("algorithm") != "greedy_rewrite"
        or run.get("feedback_mode") != "normal"
    ):
        raise ValueError("unexpected gravity task/algorithm/feedback mode")
    trajectory_path = Path(run["workdir"]) / "trajectory.jsonl"
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("gravity compact snapshot differs from raw trajectory")
    raw = load_trajectory(trajectory_path)
    events = snapshot["events"]
    if len(raw) != len(events):
        raise ValueError("gravity raw and compact trajectory lengths differ")
    parent = events[0]["candidate_sha256"]
    for event in events[1:]:
        if event["parent_sha256"] != parent:
            raise ValueError("gravity accepted-incumbent lineage is broken")
        if event["accepted"]:
            parent = event["candidate_sha256"]
    if int(run["evaluated"]) != int(run["summary"]["oracle_calls"]):
        raise ValueError("gravity oracle-call count mismatch")
    selected = _selected(events, float(run["best"]))
    selected_raw = next(row for row in raw if int(row["step"]) == selected["step"])
    return {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(path),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "source_revision": provenance["git_revision"],
        "seed": int(run["seed"]),
        "proposal_budget": int(document["config"]["budget"]),
        "server_side_seed_control": bool(
            document["config"]["llm"].get("server_side_seed_control")
        ),
        "oracle_calls": int(run["summary"]["oracle_calls"]),
        "total_tokens": int(run["summary"]["llm"]["total_tokens"]),
        "wall_seconds": float(run["summary"]["wall_seconds"]),
        "best_score": float(run["best"]),
        "selected_step": int(selected["step"]),
        "selected_candidate_sha256": selected["candidate_sha256"],
        "selected_metrics": _scalar(selected_raw["metrics"]),
        "selected_worlds": [
            {field: world.get(field) for field in WORLD_FIELDS}
            for world in selected_raw["metrics"].get("per_world", [])
        ],
        "trajectory": [
            {
                "step": int(event["step"]),
                "accepted": bool(event["accepted"]),
                "candidate_sha256": event["candidate_sha256"],
                "parent_sha256": event["parent_sha256"],
                **_scalar(event["metrics"]),
            }
            for event in events
        ],
    }


def _analyze_records(calibration: dict[str, Any],
                     records: dict[str, dict[str, Any]],
                     source_equivalent: bool = True) -> dict[str, Any]:
    one = records["budget_one"]
    three = records["budget_three"]
    selected = three["selected_metrics"]
    proposals = three["trajectory"][1:]
    rejected = [event for event in proposals if not event["accepted"]]
    rejected_best_validation = max(
        rejected, key=lambda event: float(event["robustness_score"])
    )
    weak_world = min(
        (world for world in three["selected_worlds"]
         if world["kind"] == "in_library"),
        key=lambda world: float(world["mechanism_score"]),
    )
    revisions = {record["source_revision"] for record in records.values()}
    execution_passed = bool(
        source_equivalent and len(revisions) == 1
        and one["proposal_budget"] == 1 and three["proposal_budget"] == 3
        and one["oracle_calls"] == 2 and three["oracle_calls"] == 4
        and not one["server_side_seed_control"]
        and not three["server_side_seed_control"]
        and one["selected_step"] == 0 and one["best_score"] == 0.0
        and not bool(one["trajectory"][1]["valid"])
        and "budget_cost" in str(one["trajectory"][1]["error_message"])
        and [event["step"] for event in three["trajectory"] if event["accepted"]]
        == [0, 1, 3]
        and three["best_score"] > 0.99
        and 0.70 < float(selected["robustness_score"]) < 0.85
        and float(selected["development_prediction_score"]) > 0.98
        and float(selected["heldout_prediction_score"]) > 0.98
        and float(selected["development_false_discovery_rate"]) == 0.0
        and float(selected["heldout_false_discovery_rate"]) == 0.0
        and float(rejected_best_validation["combined_score"])
        < float(selected["combined_score"])
        and float(rejected_best_validation["robustness_score"])
        > float(selected["robustness_score"])
        and float(weak_world["interpolation_prediction_score"]) > 0.95
        and float(weak_world["mechanism_score"]) < 0.40
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": "GRAVITY_CALIBRATION_NOT_CAUSAL_POPULATION_OR_FIELD_EVIDENCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_task_source_revision": calibration["source_revision"],
        "input_model_source_revision": (
            next(iter(revisions)) if len(revisions) == 1 else None
        ),
        "input_source_scope_equivalent": bool(source_equivalent),
        "task_calibration": calibration,
        "records": records,
        "selected_development_minus_heldout_mechanism": (
            float(selected["combined_score"])
            - float(selected["robustness_score"])
        ),
        "rejected_candidate_with_higher_heldout_mechanism": {
            field: rejected_best_validation.get(field)
            for field in ("step", "candidate_sha256", *FIELDS)
        },
        "field_prediction_internal_geology_counterexample": weak_world,
        "selected_science_vector": {
            "optimization_O": selected["combined_score"],
            "fidelity_F": selected["heldout_prediction_score"],
            "mechanism_M": selected["mechanism_score"],
            "validity_V": selected["robustness_score"],
            "refusal_R": 1.0 - float(selected["development_false_discovery_rate"]),
        },
        "limitations": [
            "Budget-one and budget-three each contain one independent run; no population, scaling or causal feedback estimate is supported.",
            "The Azure endpoint exposes no server-side model seed, and the conditions use different local identifiers.",
            "Budget-one failure is a candidate API misuse, not evidence that one proposal is scientifically incapable in general.",
            "Near-saturated development recovery reflects synthesis of a known parametric inversion workflow, so Gravity-v2 is an on-ramp rather than a long-horizon headline task.",
            "Held-out mechanism, field prediction, extrapolation, refusal and per-world metrics were sealed from proposal and selection state.",
            "The oracle uses synthetic 2-D infinite-strike bodies and Gaussian noise; no field validation or autonomous geological discovery claim is supported.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def analyze() -> dict[str, Any]:
    calibration = _load_calibration(CALIBRATION)
    records = {label: _load(label, path) for label, path in REPORTS.items()}
    revisions = {record["source_revision"] for record in records.values()}
    changes: list[str] = []
    equivalent = False
    if len(revisions) == 1:
        changes = _source_changes(
            calibration["source_revision"], next(iter(revisions))
        )
        equivalent = not changes
    report = _analyze_records(calibration, records, equivalent)
    report["input_source_scope_changes"] = changes
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
