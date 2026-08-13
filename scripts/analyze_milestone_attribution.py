#!/usr/bin/env python3
"""Analyze preregistered MA1/E52 milestone-component replays.

The generic analyzer consumes a frozen manifest of parent/full-child and
component replay outcomes.  Its default command builds two deterministic
task-calibration positive controls.  Those controls test the analyzer and do
not constitute agent-milestone or scientific-discovery evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


PREREGISTRATION = ".research/milestone_attribution_preregistration.md"
REACTION_CALIBRATION = (
    "experiments/reaction_mechanism_v2_calibration_2026-07-22.json"
)
CONVECTION_CALIBRATION = (
    "experiments/convection_diffusion_v2_calibration_2026-07-23.json"
)
REACTION_ANALYSIS = "experiments/reaction_v2_calibration_analysis_2026-07-22.json"
CONVECTION_ANALYSIS = (
    "experiments/convection_diffusion_v2_calibration_analysis_2026-07-23.json"
)

ALLOWED_FACTORS = {"D", "M", "I", "O", "P"}
ALLOWED_EVIDENCE_CLASSES = {
    "synthetic_test", "positive_control", "agent_milestone",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_hash(value: Any) -> str:
    rendered = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def _finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _metric_value(treatment: dict[str, Any], metric: str) -> float:
    metrics = treatment.get("metrics") or {}
    value = metrics.get(metric)
    if not _finite(value):
        raise ValueError("missing or non-finite metric %s" % metric)
    return float(value)


def _effect(
    left: dict[str, Any],
    right: dict[str, Any],
    outcome: dict[str, Any],
) -> dict[str, float]:
    raw = _metric_value(left, outcome["name"]) - _metric_value(
        right, outcome["name"]
    )
    direction = outcome["direction"]
    favorable = raw if direction == "maximize" else -raw
    return {"raw_effect": raw, "favorable_effect": favorable}


def _vector_effect(
    left: dict[str, Any],
    right: dict[str, Any],
    outcomes: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    return {
        outcome["name"]: _effect(left, right, outcome)
        for outcome in outcomes
    }


def _gate_passes(metrics: dict[str, Any], gate: dict[str, Any]) -> bool:
    value = metrics.get(gate["metric"])
    if not _finite(value):
        return False
    threshold = float(gate["threshold"])
    operator = gate["operator"]
    if operator == ">=":
        return float(value) >= threshold
    if operator == "<=":
        return float(value) <= threshold
    raise ValueError("unsupported gate operator: %s" % operator)


def _validate_design(manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported MA1 manifest schema")
    if manifest.get("evidence_class") not in ALLOWED_EVIDENCE_CLASSES:
        raise ValueError("unknown MA1 evidence class")
    outcomes = manifest.get("outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        raise ValueError("MA1 outcomes must be a non-empty list")
    names: set[str] = set()
    for outcome in outcomes:
        name = outcome.get("name")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("MA1 outcome names must be unique strings")
        names.add(name)
        if outcome.get("direction") not in {"maximize", "minimize"}:
            raise ValueError("MA1 outcome direction must be maximize/minimize")
        if not _finite(outcome.get("material_epsilon")) or float(
            outcome["material_epsilon"]
        ) < 0.0:
            raise ValueError("MA1 material epsilon must be finite and nonnegative")
    gates = manifest.get("hard_gates") or []
    for gate in gates:
        if gate.get("metric") not in names:
            raise ValueError("MA1 hard gate references an unknown metric")
        if gate.get("operator") not in {">=", "<="} or not _finite(
            gate.get("threshold")
        ):
            raise ValueError("invalid MA1 hard gate")
    return outcomes, gates


def _validate_treatment(
    name: str,
    treatment: dict[str, Any],
    parent_hash: str,
    common: dict[str, str],
    outcomes: list[dict[str, Any]],
) -> str:
    if treatment.get("non_separable") is True:
        if treatment.get("executable") is not False:
            raise ValueError("non-separable treatment must be non-executable")
        if not treatment.get("reason"):
            raise ValueError("non-separable treatment requires a reason")
        return "non_separable"
    if treatment.get("executable") is not True:
        raise ValueError("invalid executable treatment: %s" % name)
    if name != "parent" and treatment.get("built_from_parent_sha256") != parent_hash:
        raise ValueError("treatment was not rebuilt from frozen parent: %s" % name)
    for key, expected in common.items():
        if treatment.get(key) != expected:
            raise ValueError("treatment %s mismatches %s" % (name, key))
    metrics = treatment.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("treatment metrics missing: %s" % name)
    for outcome in outcomes:
        _metric_value(treatment, outcome["name"])
    return "executable"


def _factorial_effect(
    treatments: dict[str, dict[str, Any]],
    prefix: str,
    outcomes: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    cells = [treatments.get(prefix + suffix) for suffix in ("00", "10", "01", "11")]
    if any(cell is None for cell in cells):
        raise ValueError("incomplete factorial: %s" % prefix)
    if any(cell.get("non_separable") for cell in cells):
        raise ValueError("factorial cells cannot be non-separable")
    result: dict[str, dict[str, float]] = {}
    for outcome in outcomes:
        name = outcome["name"]
        y00, y10, y01, y11 = [_metric_value(cell, name) for cell in cells]
        raw = y11 - y10 - y01 + y00
        favorable = raw if outcome["direction"] == "maximize" else -raw
        result[name] = {"raw_interaction": raw, "favorable_interaction": favorable}
    return result


def _analyze_milestone(
    milestone: dict[str, Any],
    outcomes: list[dict[str, Any]],
    gates: list[dict[str, Any]],
    evidence_class: str,
) -> dict[str, Any]:
    factors = milestone.get("factors") or []
    if not factors or len(set(factors)) != len(factors):
        raise ValueError("milestone factors must be non-empty and unique")
    if not set(factors).issubset(ALLOWED_FACTORS):
        raise ValueError("unknown MA1 factor label")
    treatments = milestone.get("treatments") or {}
    parent = treatments.get("parent")
    full = treatments.get("full_child")
    if not isinstance(parent, dict) or not isinstance(full, dict):
        raise ValueError("parent and full_child treatments are required")
    parent_hash = milestone.get("parent_sha256")
    child_hash = milestone.get("child_sha256")
    if not isinstance(parent_hash, str) or len(parent_hash) != 64:
        raise ValueError("invalid parent hash")
    if not isinstance(child_hash, str) or len(child_hash) != 64:
        raise ValueError("invalid child hash")
    if parent_hash == child_hash:
        raise ValueError("parent and child hashes must differ")
    common = milestone.get("common_replay") or {}
    required_common = (
        "evidence_access_sha256", "evaluator_manifest_sha256",
        "world_panel_sha256", "environment_sha256",
    )
    if set(common) != set(required_common) or not all(
        isinstance(common[key], str) and len(common[key]) == 64
        for key in required_common
    ):
        raise ValueError("incomplete common replay manifest")
    if parent.get("artifact_sha256") != parent_hash:
        raise ValueError("parent treatment hash mismatch")
    if full.get("artifact_sha256") != child_hash:
        raise ValueError("full-child treatment hash mismatch")

    statuses: dict[str, str] = {}
    for name, treatment in treatments.items():
        statuses[name] = _validate_treatment(
            name, treatment, parent_hash, common, outcomes,
        )
    non_separable = [name for name, status in statuses.items() if status == "non_separable"]

    estimands: dict[str, Any] = {
        "full_child": _vector_effect(full, parent, outcomes),
        "component_only": {},
        "leave_one_out_necessity": {},
        "rollback": {},
        "factor_interactions": {},
        "data_method_interaction": None,
    }
    factor_support: dict[str, list[str]] = {factor: [] for factor in factors}
    for factor in factors:
        component = treatments.get("component_only:%s" % factor)
        if component and not component.get("non_separable"):
            estimands["component_only"][factor] = _vector_effect(
                component, parent, outcomes,
            )
            factor_support[factor].append("component_only")
        leave_out = treatments.get("leave_one_out:%s" % factor)
        if leave_out and not leave_out.get("non_separable"):
            estimands["leave_one_out_necessity"][factor] = _vector_effect(
                full, leave_out, outcomes,
            )
            factor_support[factor].append("leave_one_out")
        rollback = treatments.get("rollback:%s" % factor)
        if rollback and not rollback.get("non_separable"):
            estimands["rollback"][factor] = _vector_effect(
                full, rollback, outcomes,
            )
            factor_support[factor].append("rollback")

    for interaction in milestone.get("factorials") or []:
        first, second = interaction
        if first not in factors or second not in factors or first == second:
            raise ValueError("invalid factor interaction declaration")
        label = "%s:%s" % (first, second)
        estimands["factor_interactions"][label] = _factorial_effect(
            treatments, "factorial:%s:" % label, outcomes,
        )
        factor_support[first].append("factorial:%s" % label)
        factor_support[second].append("factorial:%s" % label)

    if milestone.get("data_changed") is True and milestone.get("method_changed") is True:
        if milestone.get("data_method_non_separable") is True:
            reason = milestone.get("data_method_non_separable_reason")
            if not isinstance(reason, str) or not reason:
                raise ValueError("non-separable data-method design requires a reason")
            estimands["data_method_interaction"] = {
                "status": "non_separable", "reason": reason,
            }
        else:
            estimands["data_method_interaction"] = _factorial_effect(
                treatments, "data_method:", outcomes,
            )
    elif any(name.startswith("data_method:") for name in treatments):
        raise ValueError("data-method cells supplied without both factors changing")

    visible_name = milestone["visible_outcome"]
    sealed_names = milestone.get("sealed_outcomes") or []
    outcome_map = {row["name"]: row for row in outcomes}
    if visible_name not in outcome_map or not sealed_names or any(
        name not in outcome_map for name in sealed_names
    ):
        raise ValueError("invalid visible/sealed outcome declaration")
    visible = estimands["full_child"][visible_name]["favorable_effect"]
    visible_material = visible >= float(outcome_map[visible_name]["material_epsilon"])
    sealed_material = all(
        estimands["full_child"][name]["favorable_effect"]
        >= float(outcome_map[name]["material_epsilon"])
        for name in sealed_names
    )
    gate_results = [
        {
            **gate,
            "parent_passed": _gate_passes(parent["metrics"], gate),
            "full_child_passed": _gate_passes(full["metrics"], gate),
        }
        for gate in gates
    ]
    hard_gates_pass = all(row["full_child_passed"] for row in gate_results)

    attribution_outcomes = milestone.get("attribution_outcomes") or sealed_names
    attributed_interactions: list[str] = []
    for label, effects in estimands["factor_interactions"].items():
        if all(
            effects[name]["favorable_interaction"]
            >= float(outcome_map[name]["material_epsilon"])
            for name in attribution_outcomes
        ):
            attributed_interactions.append(label)
    attributed_factors: list[str] = []
    for factor, evidence in factor_support.items():
        if not evidence:
            continue
        favorable_signals: list[bool] = []
        for family in ("component_only", "leave_one_out_necessity", "rollback"):
            effects = estimands[family].get(factor)
            if effects:
                favorable_signals.append(all(
                    effects[name]["favorable_effect"]
                    >= float(outcome_map[name]["material_epsilon"])
                    for name in attribution_outcomes
                ))
        interaction_support = any(
            factor in label.split(":") for label in attributed_interactions
        )
        if any(favorable_signals) or interaction_support:
            attributed_factors.append(factor)

    if not milestone.get("eligible") or not milestone.get("sampled"):
        decision = "not_in_attribution_sample"
    elif not visible_material:
        decision = "no_material_full_child_improvement"
    elif not sealed_material:
        decision = "development_only_proxy_improvement"
    elif not hard_gates_pass:
        decision = "reliability_or_validity_gate_failed"
    elif not attributed_factors and not attributed_interactions:
        decision = "bundled_improvement_component_attribution_unresolved"
    else:
        decision = "bounded_component_attribution"

    if evidence_class != "agent_milestone" and decision == "bounded_component_attribution":
        wording = "positive-control component effect; not an agent scientific insight"
    elif decision == "bounded_component_attribution":
        wording = "bounded causal contribution in the frozen benchmark replay"
    else:
        wording = decision.replace("_", " ")

    return {
        "milestone_id": milestone["milestone_id"],
        "task": milestone["task"],
        "evidence_class": evidence_class,
        "eligible": bool(milestone.get("eligible")),
        "sampled": bool(milestone.get("sampled")),
        "factors": factors,
        "treatment_status": statuses,
        "non_separable_treatments": non_separable,
        "estimands": estimands,
        "gate_results": gate_results,
        "visible_material_improvement": visible_material,
        "sealed_material_improvement": sealed_material,
        "hard_gates_passed": hard_gates_pass,
        "attributed_factors": attributed_factors,
        "attributed_interactions": attributed_interactions,
        "paired_world_effects": milestone.get("paired_world_effects"),
        "decision": decision,
        "allowed_wording": wording,
    }


def analyze_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    outcomes, gates = _validate_design(manifest)
    milestones = manifest.get("milestones")
    if not isinstance(milestones, list):
        raise ValueError("MA1 milestones must be a list")
    ids = [row.get("milestone_id") for row in milestones]
    if any(not isinstance(value, str) or not value for value in ids):
        raise ValueError("every milestone requires an id")
    if len(ids) != len(set(ids)):
        raise ValueError("milestone ids must be unique")
    analyses = [
        _analyze_milestone(
            milestone, outcomes, gates, manifest["evidence_class"],
        )
        for milestone in milestones
    ]
    decisions: dict[str, int] = {}
    for row in analyses:
        decisions[row["decision"]] = decisions.get(row["decision"], 0) + 1
    eligible = [row for row in analyses if row["eligible"]]
    sampled = [row for row in analyses if row["eligible"] and row["sampled"]]
    bounded = [
        row for row in analyses
        if row["decision"] == "bounded_component_attribution"
    ]
    return {
        "cohort_id": manifest.get("cohort_id"),
        "evidence_class": manifest["evidence_class"],
        "manifest_sha256": _stable_hash(manifest),
        "milestone_count": len(analyses),
        "eligible_milestone_count": len(eligible),
        "sampled_milestone_count": len(sampled),
        "bounded_attribution_count": len(bounded),
        "causal_attribution_coverage": (
            len(bounded) / len(sampled) if sampled else None
        ),
        "non_separable_treatment_count": sum(
            len(row["non_separable_treatments"]) for row in analyses
        ),
        "decision_counts": decisions,
        "milestones": analyses,
    }


def _load_trusted(relative: str) -> tuple[Path, dict[str, Any]]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if not (
        document.get("trusted_evidence") is True
        and document.get("passed") is True
        and provenance.get("source_tree_dirty") is False
    ):
        raise ValueError("untrusted MA1 input: %s" % relative)
    return path, document


def _common(task: str, input_hash: str) -> dict[str, str]:
    return {
        "evidence_access_sha256": hashlib.sha256(
            (task + ":evidence:" + input_hash).encode("utf-8")
        ).hexdigest(),
        "evaluator_manifest_sha256": hashlib.sha256(
            (task + ":evaluator:" + input_hash).encode("utf-8")
        ).hexdigest(),
        "world_panel_sha256": hashlib.sha256(
            (task + ":worlds:" + input_hash).encode("utf-8")
        ).hexdigest(),
        "environment_sha256": hashlib.sha256(
            (task + ":environment:" + input_hash).encode("utf-8")
        ).hexdigest(),
    }


def _treatment(
    artifact_hash: str,
    parent_hash: str,
    common: dict[str, str],
    metrics: dict[str, float],
    *,
    parent: bool = False,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "artifact_sha256": artifact_hash,
        "executable": True,
        **common,
        "metrics": metrics,
    }
    if not parent:
        row["built_from_parent_sha256"] = parent_hash
    return row


def _paired_world_effects(
    parent_worlds: list[dict[str, Any]],
    child_worlds: list[dict[str, Any]],
    field_map: dict[str, tuple[str, str]],
) -> dict[str, Any]:
    def key(row: dict[str, Any]) -> tuple[str, int, str]:
        return (
            str(row["split"]), int(row["world_index"]), str(row["kind"]),
        )

    parent = {key(row): row for row in parent_worlds}
    child = {key(row): row for row in child_worlds}
    if len(parent) != len(parent_worlds) or len(child) != len(child_worlds):
        raise ValueError("duplicate world lineage in MA1 positive control")
    if parent.keys() != child.keys():
        raise ValueError("parent/child world panels do not match")
    rows: list[dict[str, Any]] = []
    for world_key in sorted(parent):
        effects: dict[str, float] = {}
        for output, (field, direction) in field_map.items():
            left = child[world_key].get(field)
            right = parent[world_key].get(field)
            if isinstance(left, bool) and isinstance(right, bool):
                raw = float(left) - float(right)
            elif _finite(left) and _finite(right):
                raw = float(left) - float(right)
            else:
                raise ValueError("non-finite paired-world outcome: %s" % field)
            effects[output] = raw if direction == "maximize" else -raw
        rows.append({
            "split": world_key[0],
            "world_index": world_key[1],
            "kind": world_key[2],
            "favorable_effects": effects,
        })
    summaries: dict[str, Any] = {}
    for output in field_map:
        values = [row["favorable_effects"][output] for row in rows]
        summaries[output] = {
            "paired_world_count": len(values),
            "mean_favorable_effect": _mean(values),
            "minimum_favorable_effect": min(values),
            "maximum_favorable_effect": max(values),
            "positive_world_count": sum(value > 0.0 for value in values),
            "negative_world_count": sum(value < 0.0 for value in values),
        }
    return {"rows": rows, "summaries": summaries}


def _reaction_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    return {
        "development_score": float(metrics["combined_score"]),
        "sealed_score": float(metrics["robustness_score"]),
        "mechanism_score": float(metrics["heldout_mechanism_score"]),
        "prediction_score": float(metrics["heldout_prediction_score"]),
        "false_discovery_rate": float(metrics["heldout_false_discovery_rate"]),
        "validity": float(metrics["valid"]),
        "experiment_cost": float(metrics["mean_experiment_budget_units"]),
    }


def _convection_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    return {
        "development_score": float(metrics["combined_score"]),
        "sealed_score": float(metrics["heldout_policy_score"]),
        "mechanism_score": float(metrics["heldout_mechanism_score"]),
        "prediction_score": float(metrics["heldout_prediction_score"]),
        "false_discovery_rate": float(metrics["heldout_false_discovery_rate"]),
        "validity": float(metrics["valid"]),
        "experiment_cost": float(metrics["development_mean_budget_units"]),
    }


def _agent_sampling_frame(
    reaction: dict[str, Any], convection: dict[str, Any],
) -> dict[str, Any]:
    reaction_records = reaction.get("records") or {}
    convection_records = convection.get("records") or {}
    reaction_normal = [
        event
        for key in ("budget_one", "normal_budget_three")
        for event in reaction_records[key]["trajectory"][1:]
        if bool(event.get("accepted")) and float(event.get("combined_score", 0.0)) > 0.0
    ]
    convection_positive = [
        event
        for record in convection_records.values()
        for event in record["trajectory"][1:]
        if bool(event.get("accepted")) and float(event.get("combined_score", 0.0)) > 0.0
    ]
    reaction_blind = reaction_records["blind_budget_three"]
    return {
        "eligible_agent_milestone_count": len(reaction_normal) + len(convection_positive),
        "reaction_normal_positive_descendants": len(reaction_normal),
        "convection_positive_descendants": len(convection_positive),
        "reaction_blind_selected_excluded": bool(
            reaction_blind.get("feedback_mode") == "selection_blind"
            and float(reaction_blind.get("best_score", 0.0)) > 0.0
        ),
        "reaction_blind_exclusion_reason": (
            "offline frozen-parent proposal is not an iterative feedback descendant; "
            "development and heldout false-discovery rates are 0.5"
        ),
    }


def build_positive_control_manifest() -> tuple[dict[str, Any], dict[str, Any]]:
    reaction_path, reaction = _load_trusted(REACTION_CALIBRATION)
    convection_path, convection = _load_trusted(CONVECTION_CALIBRATION)
    reaction_analysis_path, reaction_analysis = _load_trusted(REACTION_ANALYSIS)
    convection_analysis_path, convection_analysis = _load_trusted(CONVECTION_ANALYSIS)
    preregistration = ROOT / PREREGISTRATION
    preregistration_sha = _sha256(preregistration)
    reaction_world_effects = _paired_world_effects(
        reaction["always_abstain_baseline"]["per_world"],
        reaction["truth_blind_classical_fit"]["per_world"],
        {
            "mechanism_quality": ("mechanism_score", "maximize"),
            "interpolation_prediction": (
                "interpolation_prediction_score", "maximize",
            ),
            "false_discovery": ("false_discovery", "minimize"),
            "validity": ("valid", "maximize"),
        },
    )
    convection_world_effects = _paired_world_effects(
        convection["truth_blind_one_experiment_policy"]["per_world"],
        convection["truth_blind_two_experiment_policy"]["per_world"],
        {
            "mechanism_quality": ("mechanism_quality", "maximize"),
            "prediction_quality": ("prediction_quality", "maximize"),
            "design_quality": ("design_quality", "maximize"),
            "false_discovery": ("false_discovery", "minimize"),
            "validity": ("valid", "maximize"),
        },
    )

    outcomes = [
        {"name": "development_score", "direction": "maximize", "material_epsilon": 0.01},
        {"name": "sealed_score", "direction": "maximize", "material_epsilon": 0.01},
        {"name": "mechanism_score", "direction": "maximize", "material_epsilon": 0.01},
        {"name": "prediction_score", "direction": "maximize", "material_epsilon": 0.01},
        {"name": "false_discovery_rate", "direction": "minimize", "material_epsilon": 0.0},
        {"name": "validity", "direction": "maximize", "material_epsilon": 0.0},
        {"name": "experiment_cost", "direction": "minimize", "material_epsilon": 0.0},
    ]
    gates = [
        {"metric": "validity", "operator": ">=", "threshold": 1.0},
        {"metric": "false_discovery_rate", "operator": "<=", "threshold": 0.10},
    ]

    reaction_input_hash = _sha256(reaction_path)
    reaction_common = _common("reaction", reaction_input_hash)
    reaction_parent_hash = _stable_hash({
        "task": "reaction", "policy": "always_abstain", "input": reaction_input_hash,
    })
    reaction_child_hash = _stable_hash({
        "task": "reaction", "policy": "truth_blind_classical", "input": reaction_input_hash,
    })
    reaction_parent = _treatment(
        reaction_parent_hash, reaction_parent_hash, reaction_common,
        _reaction_metrics(reaction["always_abstain_baseline"]), parent=True,
    )
    reaction_full = _treatment(
        reaction_child_hash, reaction_parent_hash, reaction_common,
        _reaction_metrics(reaction["truth_blind_classical_fit"]),
    )
    reaction_nonseparable = {
        "artifact_sha256": _stable_hash({"reaction": "compound_nonseparable"}),
        "built_from_parent_sha256": reaction_parent_hash,
        "executable": False,
        "non_separable": True,
        "reason": (
            "assay choice, support selection, parameter fitting and refusal logic "
            "are bundled in the historical classical policy"
        ),
    }

    convection_input_hash = _sha256(convection_path)
    convection_common = _common("convection", convection_input_hash)
    convection_parent_hash = _stable_hash({
        "task": "convection", "policy": "one_experiment", "input": convection_input_hash,
    })
    convection_child_hash = _stable_hash({
        "task": "convection", "policy": "two_experiments", "input": convection_input_hash,
    })
    convection_parent = _treatment(
        convection_parent_hash, convection_parent_hash, convection_common,
        _convection_metrics(convection["truth_blind_one_experiment_policy"]),
        parent=True,
    )
    convection_full = _treatment(
        convection_child_hash, convection_parent_hash, convection_common,
        _convection_metrics(convection["truth_blind_two_experiment_policy"]),
    )
    convection_rollback_hash = _stable_hash({
        "task": "convection", "policy": "rollback_to_one_experiment",
        "input": convection_input_hash,
    })
    convection_rollback = _treatment(
        convection_rollback_hash, convection_parent_hash, convection_common,
        _convection_metrics(convection["truth_blind_one_experiment_policy"]),
    )

    manifest = {
        "schema_version": 1,
        "cohort_id": "ma1_e52_task_calibration_positive_controls_2026-07-24",
        "evidence_class": "positive_control",
        "preregistration": PREREGISTRATION,
        "preregistration_sha256": preregistration_sha,
        "outcomes": outcomes,
        "hard_gates": gates,
        "milestones": [
            {
                "milestone_id": "reaction_classical_bundle_control",
                "task": "ChemicalKinetics/ReactionMechanismFitting",
                "parent_sha256": reaction_parent_hash,
                "child_sha256": reaction_child_hash,
                "eligible": True,
                "sampled": True,
                "factors": ["D", "M", "I", "O"],
                "visible_outcome": "development_score",
                "sealed_outcomes": ["sealed_score", "mechanism_score"],
                "attribution_outcomes": ["sealed_score", "mechanism_score"],
                "data_changed": True,
                "method_changed": True,
                "data_method_non_separable": True,
                "data_method_non_separable_reason": (
                    "the historical task-calibration policy does not expose old/new data "
                    "and old/new method as independently executable cells"
                ),
                "common_replay": reaction_common,
                "factorials": [],
                "paired_world_effects": reaction_world_effects,
                "treatments": {
                    "parent": reaction_parent,
                    "full_child": reaction_full,
                    "component_only:D": reaction_nonseparable,
                    "component_only:M": dict(reaction_nonseparable),
                    "component_only:I": dict(reaction_nonseparable),
                    "component_only:O": dict(reaction_nonseparable),
                },
            },
            {
                "milestone_id": "convection_off_axis_evidence_control",
                "task": "HeatTransfer/ConvectionDiffusionOpt",
                "parent_sha256": convection_parent_hash,
                "child_sha256": convection_child_hash,
                "eligible": True,
                "sampled": True,
                "factors": ["D"],
                "visible_outcome": "development_score",
                "sealed_outcomes": ["sealed_score", "mechanism_score"],
                "attribution_outcomes": ["sealed_score", "mechanism_score"],
                "data_changed": True,
                "method_changed": False,
                "common_replay": convection_common,
                "factorials": [],
                "paired_world_effects": convection_world_effects,
                "treatments": {
                    "parent": convection_parent,
                    "full_child": convection_full,
                    "component_only:D": dict(convection_full),
                    "leave_one_out:D": convection_rollback,
                    "rollback:D": dict(convection_rollback),
                },
            },
        ],
    }
    provenance = {
        "preregistration": {
            "path": PREREGISTRATION,
            "sha256": preregistration_sha,
        },
        "inputs": {
            REACTION_CALIBRATION: _sha256(reaction_path),
            CONVECTION_CALIBRATION: _sha256(convection_path),
            REACTION_ANALYSIS: _sha256(reaction_analysis_path),
            CONVECTION_ANALYSIS: _sha256(convection_analysis_path),
        },
        "agent_milestone_sampling_frame": _agent_sampling_frame(
            reaction_analysis, convection_analysis,
        ),
    }
    return manifest, provenance


def analyze_positive_controls() -> dict[str, Any]:
    manifest, input_provenance = build_positive_control_manifest()
    analysis = analyze_manifest(manifest)
    sampling = input_provenance["agent_milestone_sampling_frame"]
    decisions = {
        row["milestone_id"]: row["decision"] for row in analysis["milestones"]
    }
    execution_passed = bool(
        sampling["eligible_agent_milestone_count"] == 0
        and sampling["reaction_blind_selected_excluded"] is True
        and analysis["milestone_count"] == 2
        and analysis["eligible_milestone_count"] == 2
        and analysis["sampled_milestone_count"] == 2
        and analysis["bounded_attribution_count"] == 1
        and analysis["non_separable_treatment_count"] == 4
        and decisions["reaction_classical_bundle_control"]
        == "reliability_or_validity_gate_failed"
        and decisions["convection_off_axis_evidence_control"]
        == "bounded_component_attribution"
        and manifest["milestones"][0]["paired_world_effects"]["summaries"][
            "false_discovery"
        ]["negative_world_count"] == 2
        and manifest["milestones"][1]["paired_world_effects"]["summaries"][
            "mechanism_quality"
        ]["positive_world_count"] >= 7
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "MA1_E52_ANALYZER_POSITIVE_CONTROLS_NOT_AGENT_MILESTONE_"
            "FEEDBACK_CAUSAL_POPULATION_PHYSICAL_OR_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_provenance": input_provenance,
        "manifest": manifest,
        "analysis": analysis,
        "descriptive_findings": {
            "reaction_bundle_improves_development": True,
            "reaction_bundle_fails_false_discovery_gate": True,
            "reaction_component_attribution_resolved": False,
            "convection_second_experiment_improves_development": True,
            "convection_evidence_effect_survives_sealed_and_mechanism_axes": True,
            "current_agent_milestone_sampling_frame_is_empty": True,
        },
        "limitations": [
            "Both replay rows are deterministic task-calibration controls, not sampled agent milestones.",
            "The Reaction control is historically bundled and has a 0.5 heldout false-discovery rate; its component attribution is intentionally unresolved.",
            "The Convection control changes only the experiment plan while retaining the same truth-blind fitting/design pipeline; it identifies the value of an added off-axis observation in this synthetic benchmark, not a discovered transport mechanism.",
            "No current Reaction or Convection normal GPT-5.5 trajectory contains an eligible positive adjacent milestone; the positive selection-blind Reaction candidate is an offline frozen-parent proposal and is excluded.",
            "A future agent-milestone report still requires frozen artifact/evidence manifests, dependency-closed component construction, key factorials where applicable and unused fresh confirmation.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = {
            "schema_version": 1,
            "trust_status": "MA1_MANIFEST_ANALYSIS",
            "evidence_scope": "USER_SUPPLIED_MA1_MANIFEST_ANALYSIS",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_provenance": source_provenance(ROOT),
            "manifest_path": str(args.manifest),
            "manifest_sha256": _sha256(args.manifest),
            "analysis": analyze_manifest(manifest),
        }
        finalize_report_trust(report, True)
    else:
        report = analyze_positive_controls()
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
