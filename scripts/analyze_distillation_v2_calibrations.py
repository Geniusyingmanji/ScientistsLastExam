#!/usr/bin/env python3
"""Build portable, non-causal evidence from DistillationColumnDesign-v2 runs."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import platform
import sys
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
from sle.secure_eval import CandidateProxy  # noqa: E402


TASK = "ChemicalProcess/DistillationColumnDesign"
TASK_DIR = ROOT / "benchmarks/Chemistry/DistillationColumnDesign"
CALIBRATION = "experiments/distillation_v2_calibration_2026-07-23.json"
REPORTS = {
    "budget_one": "experiments/gpt55_distillation_v2_b1_2026-07-23.json",
    "normal_budget_three": (
        "experiments/gpt55_distillation_v2_b3_2026-07-23.json"
    ),
    "blind_budget_three": (
        "experiments/gpt55_distillation_v2_blind_b3_2026-07-23.json"
    ),
}
SOURCE_SCOPE = (
    "sle", "scripts", "tests", "benchmarks",
    "requirements-upstream.txt",
)
SCALAR_FIELDS = (
    "combined_score", "valid", "feasibility_rate", "raw_score",
    "robustness_score", "heldout_policy_score",
    "heldout_robustness_score", "heldout_feasibility_rate",
    "development_shift_feasibility_rate",
    "heldout_shift_feasibility_rate",
    "development_mean_annualized_cost",
    "heldout_mean_annualized_cost",
    "candidate_instance_call_count", "candidate_instance_valid_rate",
)
CONSTRAINT_FIELDS = (
    "distillate_purity", "bottoms_purity", "light_recovery",
    "heavy_recovery",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, SOURCE_SCOPE, root=ROOT)


def _load_oracle():
    path = TASK_DIR / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location(
        "distillation_v2_analysis_oracle", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load DistillationColumnDesign-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scalar(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in SCALAR_FIELDS}


def _constraint_margins(metrics, problem):
    return {
        "distillate_purity": (
            float(metrics["distillate_light_mole_fraction"])
            - float(problem["minimum_distillate_light_mole_fraction"])
        ),
        "bottoms_purity": (
            float(problem["maximum_bottoms_light_mole_fraction"])
            - float(metrics["bottoms_light_mole_fraction"])
        ),
        "light_recovery": (
            float(metrics["light_recovery"])
            - float(problem["minimum_light_recovery"])
        ),
        "heavy_recovery": (
            float(metrics["heavy_recovery"])
            - float(problem["minimum_heavy_recovery"])
        ),
    }


def _split_summary(metrics, split, oracle):
    rows = [row for row in metrics["per_instance"] if row["split"] == split]
    expected = 4 if split == "development" else 2
    if len(rows) != expected or not all(row.get("valid") is True for row in rows):
        raise ValueError("selected %s instances are incomplete or invalid" % split)
    instances = {row["name"]: row for row in oracle.INSTANCES}
    nominal_margins = []
    designs = []
    shift_records = {
        shift["name"]: {
            "case_count": 0,
            "feasible_count": 0,
            "invalid_solver_count": 0,
            "constraint_violation_counts": {
                field: 0 for field in CONSTRAINT_FIELDS
            },
            "minimum_constraint_margins": {
                field: float("inf") for field in CONSTRAINT_FIELDS
            },
        }
        for shift in oracle.SHIFT_SPECS
    }
    for row in rows:
        problem = instances[row["name"]]["problem"]
        margins = _constraint_margins(row["nominal"], problem)
        nominal_margins.extend(margins.values())
        designs.append({"name": row["name"], **row["design"]})
        for shifted in row["shifted"]:
            record = shift_records[shifted["name"]]
            record["case_count"] += 1
            record["feasible_count"] += int(bool(
                shifted.get("process_feasible")
            ))
            if shifted.get("valid") is not True:
                record["invalid_solver_count"] += 1
                continue
            shifted_margins = _constraint_margins(shifted, problem)
            for field, margin in shifted_margins.items():
                record["minimum_constraint_margins"][field] = min(
                    record["minimum_constraint_margins"][field], margin
                )
                if margin < -1.0e-12:
                    record["constraint_violation_counts"][field] += 1
    for record in shift_records.values():
        record["feasibility_rate"] = (
            record["feasible_count"] / record["case_count"]
        )
        record["minimum_constraint_margins"] = {
            field: (None if value == float("inf") else value)
            for field, value in record["minimum_constraint_margins"].items()
        }
    score_key = "combined_score" if split == "development" else "heldout_policy_score"
    robust_key = (
        "robustness_score" if split == "development"
        else "heldout_robustness_score"
    )
    feasibility_key = (
        "feasibility_rate" if split == "development"
        else "heldout_feasibility_rate"
    )
    shift_key = (
        "development_shift_feasibility_rate" if split == "development"
        else "heldout_shift_feasibility_rate"
    )
    cost_key = (
        "development_mean_annualized_cost" if split == "development"
        else "heldout_mean_annualized_cost"
    )
    return {
        "instance_count": len(rows),
        "nominal_visible_score": float(metrics[score_key]),
        "sealed_robustness_score": float(metrics[robust_key]),
        "nominal_feasibility_rate": float(metrics[feasibility_key]),
        "sealed_shift_feasibility_rate": float(metrics[shift_key]),
        "mean_nominal_annualized_cost": float(metrics[cost_key]),
        "minimum_nominal_constraint_margin": min(nominal_margins),
        "designs": designs,
        "shift_diagnostics": shift_records,
    }


def _selected_event(events, best):
    matches = [
        event for event in events
        if event.get("accepted")
        and abs(float(event["score"]) - float(best)) <= 1.0e-12
    ]
    if not matches:
        raise ValueError("no accepted trajectory event matches run best")
    return min(matches, key=lambda event: int(event["step"]))


def _lineage_is_valid(record):
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


def _load_calibration(relative):
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    independent = document.get("independent_least_squares_mesh_checks") or []
    references = document.get("reference_gates") or []
    if not (
        document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and document.get("task_dimensions") == {
            "development_instance_count": 4,
            "heldout_instance_count": 2,
            "shift_count": 5,
            "tray_count_range": [8, 50],
        }
        and len(independent) == 6
        and all(row.get("passed") for row in independent)
        and len(references) == 6
        and all(row.get("passed") for row in references)
        and document["nominal_reference_policy"]["combined_score"] == 1.0
        and document["robust_reference_policy"]["robustness_score"] == 1.0
        and document["robust_reference_policy"][
            "heldout_robustness_score"
        ] == 1.0
    ):
        raise ValueError("distillation task calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "task_dimensions": document["task_dimensions"],
        "weak_baseline": document["weak_baseline"],
        "nominal_reference_policy": document["nominal_reference_policy"],
        "robust_reference_policy": document["robust_reference_policy"],
        "maximum_independent_product_composition_error": max(
            float(row["maximum_product_composition_error"])
            for row in independent
        ),
    }


def _load_model(label, relative, oracle):
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
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
        raise ValueError("expected one successful run: %s" % relative)
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
        and config.get("llm", {}).get("model") == "gpt-5.5"
    ):
        raise ValueError("unexpected distillation calibration condition")
    workdir = Path(run["workdir"]).resolve()
    try:
        relative_workdir = workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("model workdir is outside repository") from exc
    trajectory_path = workdir / "trajectory.jsonl"
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable snapshot differs from raw trajectory")
    raw_events = load_trajectory(trajectory_path)
    if len(raw_events) != len(snapshot["events"]):
        raise ValueError("raw and compact trajectory lengths differ")
    trajectory = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            int(compact["step"]) == int(raw["step"])
            and compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
        ):
            raise ValueError("raw and compact trajectory lineage differs")
        metrics = raw.get("metrics") or {}
        trajectory.append({
            "step": int(compact["step"]),
            "accepted": bool(compact["accepted"]),
            "valid": bool(metrics.get("valid")),
            "score": float(compact["score"]),
            "best_score": float(compact["best_score"]),
            "candidate_sha256": compact["candidate_sha256"],
            "parent_sha256": compact["parent_sha256"],
            "candidate_failure_kind": metrics.get("candidate_failure_kind"),
            **_scalar(metrics),
        })
    selected = _selected_event(snapshot["events"], float(run["best"]))
    selected_raw = next(
        row for row in raw_events if int(row["step"]) == int(selected["step"])
    )
    selected_metrics = selected_raw.get("metrics") or {}
    best_program = workdir / "best_program.py"
    if _sha256(best_program) != selected["candidate_sha256"]:
        raise ValueError("best program hash differs from selected candidate")
    failures = {}
    for event in trajectory[1:]:
        kind = event["candidate_failure_kind"]
        if kind:
            failures[kind] = failures.get(kind, 0) + 1
    record = {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(path),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "llm_condition_sha256": config.get("llm_condition_sha256"),
        "model": config.get("llm", {}).get("model"),
        "server_side_seed_control": bool(
            config.get("llm", {}).get("server_side_seed_control")
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
        "selected_metrics": _scalar(selected_metrics),
        "selected_axes": {
            "development": _split_summary(
                selected_metrics, "development", oracle
            ),
            "heldout": _split_summary(selected_metrics, "heldout", oracle),
        },
        "proposal_valid_count": sum(event["valid"] for event in trajectory[1:]),
        "proposal_failure_counts": failures,
        "best_program": str(relative_workdir / "best_program.py"),
        "trajectory": trajectory,
    }
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if expected_mode == "selection_blind" else "online_incumbent"
    )
    if not (
        _lineage_is_valid(record)
        and record["selection_policy"] == expected_policy
        and int(run["evaluated"]) == record["oracle_calls"]
        and sum(event["accepted"] for event in trajectory[1:])
        == int(run["accepted"])
    ):
        raise ValueError("distillation lineage or accounting gate failed")
    return record


def _metric_subset(metrics):
    return {
        field: metrics[field]
        for field in (
            "process_feasible", "distillate_light_mole_fraction",
            "bottoms_light_mole_fraction", "light_recovery",
            "heavy_recovery", "annualized_cost",
        )
    }


def _cost_counterfactual(normal, oracle):
    """Post-hoc public-input probe; this is not a preregistered held-out test."""
    candidate_path = ROOT / normal["best_program"]
    source = candidate_path.read_text(encoding="utf-8")
    instance = next(
        row for row in oracle.INSTANCES
        if row["name"] == "dev_balanced_aromatic"
    )
    regimes = (
        ("capital_heavy_energy_light", 200000.0, 50000.0),
        ("capital_light_energy_heavy", 5000.0, 700000.0),
    )
    records = []
    with CandidateProxy(candidate_path, "design_column", 240.0) as proxy:
        for index, (name, tray_cost, vapour_cost) in enumerate(regimes):
            if index:
                proxy.reset_session()
            problem = copy.deepcopy(instance["problem"])
            problem["annualized_cost_per_tray"] = tray_cost
            problem["annualized_cost_per_vapour_flow"] = vapour_cost
            candidate_design = oracle._validate_design(
                proxy(copy.deepcopy(problem)), problem
            )
            candidate_metrics = oracle._solve_column(candidate_design, problem)
            reference_design = copy.deepcopy(
                instance["nominal_reference_design"]
            )
            reference_metrics = oracle._solve_column(reference_design, problem)
            records.append({
                "name": name,
                "annualized_cost_per_tray": tray_cost,
                "annualized_cost_per_vapour_flow": vapour_cost,
                "candidate_design": candidate_design,
                "candidate_metrics": _metric_subset(candidate_metrics),
                "reference_design": reference_design,
                "reference_metrics": _metric_subset(reference_metrics),
                "candidate_minus_reference_annualized_cost": (
                    candidate_metrics["annualized_cost"]
                    - reference_metrics["annualized_cost"]
                ),
            })
    same_design = records[0]["candidate_design"] == records[1]["candidate_design"]
    deltas = [
        row["candidate_minus_reference_annualized_cost"] for row in records
    ]
    return {
        "post_hoc": True,
        "selection_state_accessed": False,
        "probe_instance": instance["name"],
        "candidate_sha256": _sha256(candidate_path),
        "source_mentions_public_tray_cost_field": (
            "annualized_cost_per_tray" in source
        ),
        "source_mentions_public_vapour_cost_field": (
            "annualized_cost_per_vapour_flow" in source
        ),
        "candidate_design_identical_across_cost_regimes": same_design,
        "candidate_reference_cost_ranking_reverses": (
            min(deltas) < 0.0 < max(deltas)
        ),
        "all_candidate_and_reference_designs_feasible": all(
            row["candidate_metrics"]["process_feasible"]
            and row["reference_metrics"]["process_feasible"]
            for row in records
        ),
        "regimes": records,
        "interpretation": (
            "The selected policy returns the same artifact even though the public "
            "capital-versus-energy cost change reverses its ordering against a feasible "
            "lower-reflux witness. This diagnoses missing cost responsiveness, not an "
            "invalid nominal benchmark score."
        ),
    }


def _analyze_records(calibration, records, cost_probe, source_equivalent=True):
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    llm_conditions = {
        record["llm_condition_sha256"] for record in records.values()
    }
    proposals = [
        event for record in records.values() for event in record["trajectory"][1:]
    ]
    timeout_count = sum(
        event.get("candidate_failure_kind") == "candidate_timeout"
        for event in proposals
    )
    normal_development = normal["selected_axes"]["development"]
    normal_heldout = normal["selected_axes"]["heldout"]
    normal_minus_blind = {
        "development_nominal_visible_score": (
            normal_development["nominal_visible_score"]
            - blind["selected_axes"]["development"]["nominal_visible_score"]
        ),
        "heldout_nominal_visible_score": (
            normal_heldout["nominal_visible_score"]
            - blind["selected_axes"]["heldout"]["nominal_visible_score"]
        ),
        "development_sealed_robustness_score": (
            normal_development["sealed_robustness_score"]
            - blind["selected_axes"]["development"]["sealed_robustness_score"]
        ),
        "development_sealed_shift_feasibility_rate": (
            normal_development["sealed_shift_feasibility_rate"]
            - blind["selected_axes"]["development"][
                "sealed_shift_feasibility_rate"
            ]
        ),
        "proposal_valid_count": (
            normal["proposal_valid_count"] - blind["proposal_valid_count"]
        ),
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
    }
    execution_passed = bool(
        source_equivalent
        and len(revisions) == 1
        and len(scopes) == 1
        and len(llm_conditions) == 1
        and None not in llm_conditions
        and all(record["model"] == "gpt-5.5" for record in records.values())
        and all(
            not record["server_side_seed_control"] for record in records.values()
        )
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["seed"] == 0
        and normal["seed"] == blind["seed"] == 1
        and one["oracle_calls"] == 2
        and normal["oracle_calls"] == blind["oracle_calls"] == 4
        and one["feedback_mode"] == normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and all(_lineage_is_valid(record) for record in records.values())
        and len(proposals) == 7
        and sum(event["valid"] for event in proposals) == 1
        and timeout_count == 6
        and one["best_score"] == 0.0
        and one["selected_step"] == 0
        and normal["selected_step"] == 2
        and 0.60 < normal["best_score"] < 0.65
        and 0.53 < normal_heldout["nominal_visible_score"] < 0.55
        and normal_development["nominal_feasibility_rate"] == 1.0
        and normal_heldout["nominal_feasibility_rate"] == 1.0
        and normal_development["sealed_robustness_score"] == 0.0
        and normal_heldout["sealed_robustness_score"] == 0.0
        and normal_development["sealed_shift_feasibility_rate"] == 0.2
        and normal_heldout["sealed_shift_feasibility_rate"] == 0.2
        and blind["best_score"] == 0.0
        and blind["selected_step"] == 0
        and normal["total_tokens"] != blind["total_tokens"]
        and cost_probe[
            "candidate_design_identical_across_cost_regimes"
        ] is True
        and cost_probe["candidate_reference_cost_ranking_reverses"] is True
        and cost_probe[
            "all_candidate_and_reference_designs_feasible"
        ] is True
        and cost_probe["source_mentions_public_tray_cost_field"] is False
        and cost_probe["source_mentions_public_vapour_cost_field"] is False
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "DISTILLATION_SINGLE_RUN_CALIBRATION_NOT_CAUSAL_POPULATION_"
            "GLOBAL_OPTIMALITY_PLANT_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_task_source_revision": calibration["source_revision"],
        "input_model_source_revision": (
            next(iter(revisions)) if len(revisions) == 1 else None
        ),
        "input_source_scope_equivalent": bool(source_equivalent),
        "input_llm_condition_equivalent": len(llm_conditions) == 1,
        "task_calibration": calibration,
        "records": records,
        "observed_proposal_pattern": {
            "proposal_count": len(proposals),
            "valid_proposal_count": sum(event["valid"] for event in proposals),
            "candidate_timeout_count": timeout_count,
            "normal_selected_nominal_development_score": normal["best_score"],
            "normal_selected_nominal_heldout_score": normal_heldout[
                "nominal_visible_score"
            ],
            "normal_selected_development_shift_feasibility_rate": (
                normal_development["sealed_shift_feasibility_rate"]
            ),
            "normal_selected_heldout_shift_feasibility_rate": normal_heldout[
                "sealed_shift_feasibility_rate"
            ],
            "normal_selected_development_robustness_score": (
                normal_development["sealed_robustness_score"]
            ),
            "normal_selected_heldout_robustness_score": normal_heldout[
                "sealed_robustness_score"
            ],
        },
        "science_axis_separation": {
            "nominal_cost_optimization": {
                "development_score": normal_development[
                    "nominal_visible_score"
                ],
                "heldout_score": normal_heldout["nominal_visible_score"],
                "development_feasibility_rate": normal_development[
                    "nominal_feasibility_rate"
                ],
                "heldout_feasibility_rate": normal_heldout[
                    "nominal_feasibility_rate"
                ],
            },
            "sealed_operating_robustness": {
                "development_score": normal_development[
                    "sealed_robustness_score"
                ],
                "heldout_score": normal_heldout[
                    "sealed_robustness_score"
                ],
                "development_shift_feasibility_rate": normal_development[
                    "sealed_shift_feasibility_rate"
                ],
                "heldout_shift_feasibility_rate": normal_heldout[
                    "sealed_shift_feasibility_rate"
                ],
            },
            "public_cost_model_responsiveness": cost_probe,
        },
        "normal_minus_blind_diagnostic": normal_minus_blind,
        "descriptive_findings": {
            "one_valid_proposal_improves_nominal_cost": normal["best_score"] > 0.0,
            "nominally_feasible_selected_design_has_zero_robustness": (
                normal_development["nominal_feasibility_rate"] == 1.0
                and normal_development["sealed_robustness_score"] == 0.0
            ),
            "only_richer_feed_shift_is_feasible": all(
                diagnostics["feasibility_rate"] == (
                    1.0 if name == "richer_feed" else 0.0
                )
                for split in (normal_development, normal_heldout)
                for name, diagnostics in split["shift_diagnostics"].items()
            ),
            "selected_program_is_not_cost_responsive_in_post_hoc_probe": (
                cost_probe[
                    "candidate_design_identical_across_cost_regimes"
                ]
                and cost_probe["candidate_reference_cost_ranking_reverses"]
            ),
            "normal_and_blind_are_oracle_call_matched": (
                normal_minus_blind["oracle_calls"] == 0
            ),
            "normal_and_blind_are_not_token_matched": (
                normal_minus_blind["total_tokens"] != 0
            ),
        },
        "limitations": [
            "Each condition has one run; no confidence interval, population estimate, leaderboard or scaling law is supported.",
            "The Azure endpoint exposes no server-side generation seed, so equal local seed labels do not pair model randomness.",
            "Normal and selection-blind are oracle-call matched but not token- or context-matched; their contrast is descriptive, not causal.",
            "Budget one uses a different local seed label and is an independent calibration, not a prefix of budget three.",
            "Held-out, per-instance and shifted robustness metrics were sealed from proposal and selection state.",
            "The cost-regime counterfactual is a post-hoc mechanism probe, not a preregistered hidden benchmark or model-performance estimate.",
            "Fixed repository-visible binary separations still require server-held mixtures and specifications.",
            "The constant-relative-volatility equilibrium-stage model is not rate-based process simulation, plant validation or autonomous scientific discovery evidence.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def analyze():
    oracle = _load_oracle()
    calibration = _load_calibration(CALIBRATION)
    records = {
        label: _load_model(label, relative, oracle)
        for label, relative in REPORTS.items()
    }
    revisions = {record["source_revision"] for record in records.values()}
    source_changes = []
    source_equivalent = False
    if len(revisions) == 1:
        source_changes = _source_changes(
            calibration["source_revision"], next(iter(revisions))
        )
        source_equivalent = not source_changes
    cost_probe = _cost_counterfactual(records["normal_budget_three"], oracle)
    report = _analyze_records(
        calibration, records, cost_probe, source_equivalent
    )
    report["input_source_scope_changes"] = source_changes
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
