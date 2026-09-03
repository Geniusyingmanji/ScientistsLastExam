#!/usr/bin/env python3
"""Classify task measurement health before allocating long-horizon runs.

The audit consumes the task-maturity ledger instead of rediscovering raw run
binding.  It deliberately separates a result-selected exploratory screen from
confirmatory eligibility: observed short-run headroom may justify a 2 h pilot,
but can never establish post-2 h headroom or long-horizon readiness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402
from scripts.audit_task_maturity import build_report as build_maturity_report  # noqa: E402


SCHEMA_VERSION = 1
DEFAULT_MATURITY = ROOT / "experiments/task_maturity_audit_2026-09-03_v11.json"

EXPLORATORY_LONG_HORIZON_SCREEN = "exploratory_long_horizon_screen"
REPAIR_FIRST = "repair_first"
SATURATED_ON_RAMP = "saturated_on_ramp"
CONTROL_ONLY = "control_only"
QUARANTINED = "quarantined"

CLASSIFICATION_ORDER = (
    EXPLORATORY_LONG_HORIZON_SCREEN,
    REPAIR_FIRST,
    SATURATED_ON_RAMP,
    CONTROL_ONLY,
    QUARANTINED,
)

# These roles were inferred after inspecting current GPT-5.5 calibration results.
# They allocate exploratory measurement only and are prohibited from serving as
# a confirmatory cohort for claims about the same model or selection procedure.
EXPLORATORY_TASKS = {
    "Electrochemistry/ElectrolyteConductivityDesign",
    "Optics/DiffractionGratingDesign",
    "RNAEngineering/RNAInverseDesign",
    "Semiconductor/MOSFETDoping",
    "StructuralEngineering/TrussWeightMinimization",
    "Thermodynamics/HeatExchangerDesign",
    "Turbulence/RANSCalibration",
}

CONTROL_ONLY_TASKS = {
    "DynamicalSystems/ActiveLawDiscovery": (
        "repeated mechanism/refusal and feedback-protocol control; the current "
        "normal-minus-selection-blind contrast identifies no normal-feedback advantage"
    ),
    "ControlTheory/InvertedPendulumSwingUp": (
        "known-answer positive control with three matched short-budget repetitions"
    ),
}

KNOWN_SATURATED_TASKS = {
    "BayesianInference/OptimalExperimentDesign",
    "Chemistry/LennardJonesCluster",
    "DynamicalSystems/LyapunovControl",
    "Electromagnetics/AntennaArraySynthesis",
    "FluidDynamics/LidDrivenCavity",
    "Geophysics/GravityInversion",
    "Geophysics/SeismicInversion",
    "NuclearEngineering/NeutronDiffusionCriticality",
    "Photovoltaics/PhotovoltaicTandemDesign",
    "Physics/SpinGlassGroundState",
    "PowerSystems/OptimalPowerFlow",
    "QuantumChemistry/HartreeFockSCF",
    "QuantumControl/GateSynthesis",
    "ScientificComputing/PoissonSolver2D",
    "SignalProcessing/SparseRecovery",
    "Thermodynamics/RankineCycleOpt",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_maturity(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("trusted_evidence") is not True:
        raise ValueError("maturity input must be trusted evidence")
    if report.get("execution_passed") is not True or report.get("issues"):
        raise ValueError("maturity input did not pass")
    if not isinstance(report.get("tasks"), list):
        raise ValueError("maturity input lacks task records")
    return report


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _mean(measurement: dict[str, Any], key: str) -> Optional[float]:
    summary = measurement.get(key)
    if not isinstance(summary, dict):
        return None
    return _finite(summary.get("mean"))


def _health_checks(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    measurement = row["model_measurement"]
    trajectory = measurement.get("proposal_trajectory_health") or {}
    b3_health = trajectory.get("normal_budget_three") or {}
    b1 = _mean(measurement, "normal_budget_one")
    b3 = _mean(measurement, "normal_budget_three")
    blind = _mean(measurement, "selection_blind_budget_three")
    gain = measurement.get("post_first_valid_gain") or {}
    gain_max = _finite(gain.get("maximum"))
    material_gain_count = int(gain.get("material_gain_count") or 0)

    b1_not_saturated = b1 is not None and b1 < 0.95
    short_run_material_gain = bool(
        material_gain_count > 0 and gain_max is not None and gain_max >= 0.05
    )
    nonfloor_b3 = b3 is not None and b3 > 0.01
    if b3 is None:
        observed_first_valid = False
    elif b3_health.get("run_count"):
        observed_first_valid = b3_health.get("observed_first_valid_run_rate") == 1.0
    else:
        # Old maturity ledgers did not expose proposal-level health.  The task
        # remains auditable, but cannot pass the complete measurement gate.
        observed_first_valid = False

    return {
        "current_model_measurement": {
            "passed": measurement.get("current_or_migrated_run_count", 0) > 0,
            "value": measurement.get("current_or_migrated_run_count", 0),
        },
        "normal_budget_one_observed": {
            "passed": b1 is not None,
            "value": b1,
        },
        "normal_budget_three_observed": {
            "passed": b3 is not None,
            "value": b3,
        },
        "selection_blind_budget_three_observed": {
            "passed": blind is not None,
            "value": blind,
        },
        "observed_first_valid_in_normal_budget_three": {
            "passed": observed_first_valid,
            "value": b3_health.get("observed_first_valid_run_rate"),
            "run_count": b3_health.get("run_count", 0),
        },
        "budget_one_below_observed_ceiling_warning": {
            "passed": b1_not_saturated,
            "value": b1,
            "threshold": 0.95,
        },
        "normal_budget_three_above_floor": {
            "passed": nonfloor_b3,
            "value": b3,
            "threshold": 0.01,
        },
        "material_short_run_post_first_valid_gain": {
            "passed": short_run_material_gain,
            "value": gain_max,
            "threshold": 0.05,
            "supporting_run_count": int(gain.get("run_count") or 0),
            "material_gain_run_count": material_gain_count,
        },
        "at_least_three_matched_controls": {
            "passed": measurement.get("maximum_matched_control_replicates", 0) >= 3,
            "value": measurement.get("maximum_matched_control_replicates", 0),
        },
        "fresh_postcommit_confirmation": {
            "passed": bool(row.get("fresh_confirmation")),
            "value": len(row.get("fresh_confirmation") or []),
        },
        "fixed_artifact_noise_quantified": {
            "passed": False,
            "value": None,
        },
        "evaluator_resolution_quantified": {
            "passed": False,
            "value": None,
        },
        "baseline_reference_separation_quantified": {
            "passed": False,
            "value": None,
        },
        "shortcut_resistance_for_long_horizon_passed": {
            "passed": False,
            "value": None,
        },
        "material_post_2h_headroom_demonstrated": {
            "passed": False,
            "value": None,
        },
    }


def _classification(row: dict[str, Any], checks: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
    task = row["task"]
    certification_status = row.get("certification_status")
    if certification_status == "quarantined":
        return QUARANTINED, ["internal science admission failed"]
    if task in CONTROL_ONLY_TASKS:
        return CONTROL_ONLY, [CONTROL_ONLY_TASKS[task]]
    if (task in EXPLORATORY_TASKS
            and not row["gates"]["internal_science_admission"]["passed"]):
        return REPAIR_FIRST, [
            "current science admission failed",
            "refresh the baseline and certification evidence before measurement allocation",
        ]
    if task in EXPLORATORY_TASKS:
        reasons = [
            "result-selected current-contract task for an exploratory 2 h measurement screen",
            "not eligible for a confirmatory cohort selected independently of current GPT-5.5 outcomes",
        ]
        if checks["material_short_run_post_first_valid_gain"]["passed"]:
            reasons.append("observed at least one material within-three-proposal gain")
        if task == "Optics/DiffractionGratingDesign":
            reasons.append("has repeated controls and fresh procedural confirmation but high short-run variance")
        return EXPLORATORY_LONG_HORIZON_SCREEN, reasons
    if task in KNOWN_SATURATED_TASKS or checks[
        "budget_one_below_observed_ceiling_warning"
    ]["passed"] is False and checks["normal_budget_one_observed"]["passed"]:
        return SATURATED_ON_RAMP, [
            "observed one-step or near-ceiling behavior, or retained as a known-answer/on-ramp control",
            "requires a harder procedural or multifidelity contract before long-horizon allocation",
            # Said out loud because this verdict retires tasks. The only score a searcher receives
            # is `combined_score`; robustness, mechanism recovery and every per-instance metric are
            # evaluator-only by the visibility contract, and none of them reach this classifier.
            # `CalorimeterDesign` reads 1.0121 here - past its reference witness - while its
            # `robustness_score` sits at exactly 0.0, the shipped baseline. Half that task is
            # untouched. `scripts/report_saturation_hidden_axes.py` scores the best recorded
            # candidate again to say which half.
            "saturation is observed on combined_score only, which is the one metric a searcher "
            "receives; evaluator-only axes are not visible to this classifier and may be "
            "untouched - see scripts/report_saturation_hidden_axes.py",
        ]
    if not row["gates"]["internal_science_admission"]["passed"]:
        return REPAIR_FIRST, [
            "current science admission failed",
            "refresh the baseline and certification evidence before measurement allocation",
        ]
    return REPAIR_FIRST, [
        "current contract lacks sufficient non-saturated, valid, repeated trajectory evidence",
        "repair contract or run a short measurement calibration before allocating 2--12 h",
    ]


def _missing_gate_checks(checks: dict[str, dict[str, Any]]) -> list[str]:
    required = (
        "observed_first_valid_in_normal_budget_three",
        "normal_budget_three_above_floor",
        "budget_one_below_observed_ceiling_warning",
        "fixed_artifact_noise_quantified",
        "evaluator_resolution_quantified",
        "baseline_reference_separation_quantified",
        "shortcut_resistance_for_long_horizon_passed",
        "material_post_2h_headroom_demonstrated",
    )
    return [name for name in required if checks[name]["passed"] is not True]


def build_report(maturity_path: Path = DEFAULT_MATURITY) -> dict[str, Any]:
    maturity_path = maturity_path.resolve()
    maturity = _load_maturity(maturity_path)
    current_maturity = build_maturity_report()
    if current_maturity.get("execution_passed") is not True:
        raise ValueError("current maturity reconstruction failed")
    frozen_tasks = {row["task"] for row in maturity["tasks"]}
    current_tasks = {row["task"] for row in current_maturity["tasks"]}
    if not frozen_tasks <= current_tasks:
        raise ValueError("frozen maturity contains tasks absent from the current inventory")

    task_records = []
    for row in current_maturity["tasks"]:
        checks = _health_checks(row)
        classification, reasons = _classification(row, checks)
        missing = _missing_gate_checks(checks)
        task_records.append({
            "task": row["task"],
            "certification_status": row["certification_status"],
            "internal_science_admission": row["gates"]["internal_science_admission"]["passed"],
            "provenance_class": row["task_card"]["provenance_class"],
            "classification": classification,
            "classification_reasons": reasons,
            "checks": checks,
            "complete_measurement_health_passed": not missing,
            "missing_complete_gate_checks": missing,
            "confirmatory_cohort_eligible": False,
            "confirmatory_ineligibility_reasons": [
                "current portfolio roles were assigned after inspecting current GPT-5.5 calibration outcomes",
                "no task demonstrates material post-2h headroom",
                "no task has a complete measurement-health gate",
            ],
        })

    counts = Counter(row["classification"] for row in task_records)
    complete_count = sum(row["complete_measurement_health_passed"] for row in task_records)
    exploratory = [
        row["task"] for row in task_records
        if row["classification"] == EXPLORATORY_LONG_HORIZON_SCREEN
    ]
    issues = []
    if len(task_records) != current_maturity.get("inventory_count"):
        issues.append("measurement-health inventory differs from maturity inventory")
    if sum(counts.values()) != len(task_records):
        issues.append("classification counts do not cover the inventory")
    if set(exploratory) != EXPLORATORY_TASKS:
        issues.append("exploratory cohort differs from the frozen result-selected set")
    if complete_count:
        issues.append("a task unexpectedly passed the complete measurement-health gate")

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "trust_status": "TRUSTED_MEASUREMENT_HEALTH_CLASSIFICATION",
        "evidence_scope": (
            "RESULT_SELECTED_EXPLORATORY_LONG_HORIZON_ALLOCATION_AUDIT_NOT_"
            "CONFIRMATORY_COHORT_POST_2H_HEADROOM_FEEDBACK_CAUSAL_SCALING_LAW_"
            "EXTERNAL_VALIDATION_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input": {
            "path": str(maturity_path.relative_to(ROOT)),
            "sha256": _sha256(maturity_path),
            "source_revision": maturity["source_provenance"]["git_revision"],
            "head_revision": maturity["head_revision"],
        },
        "policy": {
            "classification_order": list(CLASSIFICATION_ORDER),
            "score_floor_warning": 0.01,
            "score_ceiling_warning": 0.95,
            "material_short_run_gain": 0.05,
            "complete_gate_requires": [
                "observed first-valid behavior",
                "baseline/reference separation",
                "fixed-artifact evaluator noise",
                "evaluator resolution and scientific materiality",
                "floor and ceiling mass",
                "shortcut resistance",
                "material headroom after two hours",
            ],
            "selection_rule": (
                "exploratory roles are frozen after inspecting current GPT-5.5 results; "
                "they allocate pilots only and cannot support an unbiased confirmatory cohort"
            ),
        },
        "inventory_count": len(task_records),
        "classification_counts": {
            name: counts.get(name, 0) for name in CLASSIFICATION_ORDER
        },
        "complete_measurement_health_passed_count": complete_count,
        "confirmatory_cohort_eligible_count": sum(
            row["confirmatory_cohort_eligible"] for row in task_records
        ),
        "exploratory_cohort": exploratory,
        "confirmatory_cohort": [],
        "tasks": task_records,
        "issues": issues,
        "next_actions": [
            "Freeze the seven-task result-selected exploratory cohort before any 2 h run.",
            "Measure fixed-artifact noise, evaluator resolution, first-valid rate, and baseline/reference separation before long runs.",
            "Run every exploratory task for 2 h with t=0, first-valid, submission, fixed-grid, commit, and terminal sentinels.",
            "Retain a random audit tranche to 12 h; do not deterministically stop all apparent 2 h failures.",
            "Select any confirmatory cohort independently of these GPT-5.5 outcomes, ideally with sealed tasks or a different builder/model split.",
        ],
        "important_limits": [
            "Short proposal-budget gain is not evidence of material post-2h headroom.",
            "A single observed run is not a provider-side probability or variance estimate.",
            "Known-answer and public-data tasks may measure optimization or reconstruction without scientific discovery.",
            "No current task is long-horizon-ready, externally validated, or autonomous-discovery evidence.",
        ],
    }
    finalize_report_trust(report, not issues)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    counts = report["classification_counts"]
    lines = [
        "# Measurement-health task allocation",
        "",
        "This audit allocates the current inventory for the next measurement stage. It does not",
        "promote any task to long-horizon-ready. The exploratory cohort was selected after",
        "inspecting current GPT-5.5 outcomes and therefore cannot double as a confirmatory cohort.",
        "",
        "## Counts",
        "",
        "| Classification | Tasks | Meaning |",
        "|---|---:|---|",
        "| Exploratory long-horizon screen | %d | Freeze for a sentinel-complete 2 h pilot; not confirmatory |" % counts[EXPLORATORY_LONG_HORIZON_SCREEN],
        "| Repair first | %d | Repair contract or measurement path before allocating 2--12 h |" % counts[REPAIR_FIRST],
        "| Saturated/on-ramp | %d | Useful reconstruction/on-ramp; harden before long-horizon use |" % counts[SATURATED_ON_RAMP],
        "| Control only | %d | Retain for mechanism/protocol/positive-control studies |" % counts[CONTROL_ONLY],
        "| Quarantined | %d | Failed internal science admission |" % counts[QUARANTINED],
        "",
        "Complete measurement-health passes: **%d**. Confirmatory-cohort eligible: **%d**." % (
            report["complete_measurement_health_passed_count"],
            report["confirmatory_cohort_eligible_count"],
        ),
        "",
        "## Allocation",
        "",
        "| Task | Class | b1 | b3 | blind | max later gain | controls | fresh |",
        "|---|---|---:|---:|---:|---:|---:|:---:|",
    ]
    for row in report["tasks"]:
        if not row["internal_science_admission"]:
            continue
        checks = row["checks"]
        values = []
        for key in (
            "normal_budget_one_observed",
            "normal_budget_three_observed",
            "selection_blind_budget_three_observed",
            "material_short_run_post_first_valid_gain",
        ):
            value = checks[key]["value"]
            values.append("--" if value is None else "%.3f" % float(value))
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %d | %s |" % (
                row["task"], row["classification"].replace("_", " "),
                values[0], values[1], values[2], values[3],
                checks["at_least_three_matched_controls"]["value"],
                "yes" if checks["fresh_postcommit_confirmation"]["passed"] else "no",
            )
        )

    lines.extend([
        "",
        "## Frozen exploratory cohort",
        "",
    ])
    lines.extend("- %s" % task for task in report["exploratory_cohort"])
    lines.extend([
        "",
        "Diffraction has repeated controls and fresh procedural confirmation, but its short-run",
        "distribution is high-variance. ActiveLaw is kept outside this optimization cohort as a",
        "mechanism/refusal control because the repeated common-token normal-minus-blind estimate",
        "did not identify a normal-feedback advantage.",
        "",
        "## Next actions",
        "",
    ])
    lines.extend("%d. %s" % (index, item) for index, item in enumerate(report["next_actions"], 1))
    lines.extend([
        "",
        "The machine-readable report is authoritative for per-task checks, classification reasons,",
        "selection limits, evidence binding, and next-stage restrictions.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--maturity", type=Path, default=DEFAULT_MATURITY)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()
    report = build_report(args.maturity)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "inventory_count": report["inventory_count"],
        "classification_counts": report["classification_counts"],
        "complete_measurement_health_passed_count": report["complete_measurement_health_passed_count"],
        "confirmatory_cohort_eligible_count": report["confirmatory_cohort_eligible_count"],
        "exploratory_cohort": report["exploratory_cohort"],
        "issues": report["issues"],
        "execution_passed": report["execution_passed"],
        "trusted_evidence": report["trusted_evidence"],
    }, indent=2))
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
