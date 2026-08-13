#!/usr/bin/env python3
"""Audit wave-9 active force-field hypothesis candidate admission gates."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402


TASK_ID = "MolecularDynamics/ForceFieldCalibration"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit():
    calibration = _load(
        ROOT / "scripts/calibrate_force_field_hypothesis_lab.py",
        "wave9_force_field_calibration",
    ).calibrate()
    reference = calibration["truth_blind_reference"]
    baseline = calibration["secure_weak_baseline"]
    pair_checks = calibration["independent_pair_energy_force_checks"]
    virial_checks = calibration["independent_second_virial_boyle_checks"]
    screening = calibration["screening_hypothesis_and_reference_checks"]
    acquisition = calibration["acquisition_contrast_checks"]
    isolation = calibration["secure_isolation_and_failure_checks"]
    record = {
        "task": TASK_ID,
        "admission": "candidate",
        "resolved_capability_gap": (
            "replaces a generic trigonometric clone with an HP1-style active "
            "model-discrimination laboratory: preregistered Mie/Morse/unsupported "
            "hypothesis weights and monotone retention, informative three-particle "
            "energy/force acquisition, parameter intervals, sealed short/tail and "
            "temperature prediction, second-virial/Boyle decisions, immutable "
            "evidence lineage and Buckingham/three-body/state-dependent refusal"
        ),
        **calibration["task_dimensions"],
        "baseline_score": baseline["combined_score"],
        "truth_blind_development_score": reference["combined_score"],
        "truth_blind_heldout_score": reference["heldout_policy_score"],
        "truth_blind_development_robustness": reference["robustness_score"],
        "truth_blind_heldout_robustness": reference[
            "heldout_robustness_score"
        ],
        "development_supported_claim_coverage": reference[
            "development_supported_claim_coverage"
        ],
        "heldout_supported_claim_coverage": reference[
            "heldout_supported_claim_coverage"
        ],
        "development_supported_correct_model_rate": reference[
            "development_supported_correct_model_rate"
        ],
        "heldout_supported_correct_model_rate": reference[
            "heldout_supported_correct_model_rate"
        ],
        "development_unsupported_refusal_rate": reference[
            "development_unsupported_refusal_rate"
        ],
        "heldout_unsupported_refusal_rate": reference[
            "heldout_unsupported_refusal_rate"
        ],
        "development_false_discovery_rate": reference[
            "development_false_discovery_rate"
        ],
        "heldout_false_discovery_rate": reference[
            "heldout_false_discovery_rate"
        ],
        "development_interval_coverage": reference[
            "development_interval_coverage"
        ],
        "heldout_interval_coverage": reference["heldout_interval_coverage"],
        "development_true_hypothesis_retention_rate": reference[
            "development_true_hypothesis_retention_rate"
        ],
        "heldout_true_hypothesis_retention_rate": reference[
            "heldout_true_hypothesis_retention_rate"
        ],
        "development_premature_elimination_rate": reference[
            "development_premature_elimination_rate"
        ],
        "heldout_premature_elimination_rate": reference[
            "heldout_premature_elimination_rate"
        ],
        "pair_energy_force_invariants_passed": pair_checks["passed"],
        "second_virial_boyle_checks_passed": virial_checks["passed"],
        "early_ambiguity_passed": screening["early_ambiguity_passed"],
        "supported_model_discrimination_passed": screening[
            "supported_model_discrimination_passed"
        ],
        "hypothesis_retention_passed": screening[
            "hypothesis_retention_passed"
        ],
        "acquisition_contrast_passed": acquisition["passed"],
        "minimum_acquisition_quality_gain": acquisition[
            "minimum_acquisition_quality_gain"
        ],
        "fresh_process_per_world_passed": isolation[
            "fresh_process_per_world_passed"
        ],
        "fail_closed_passed": isolation["fail_closed_passed"],
        "search_visible_metric_keys": calibration["search_visible_metric_keys"],
        "limitations": calibration["limitations"],
    }
    record["passed"] = bool(
        calibration["execution_passed"]
        and calibration["secure_baseline_exactly_matches_direct"]
        and baseline["valid"] == 1.0
        and baseline["combined_score"] == 0.0
        and baseline["robustness_score"] == 0.0
        and set(record["search_visible_metric_keys"]) == {
            "combined_score", "valid", "feasibility_rate", "raw_score"
        }
        and record["truth_blind_development_score"] > 0.93
        and record["truth_blind_heldout_score"] > 0.93
        and record["truth_blind_development_robustness"] > 0.93
        and record["truth_blind_heldout_robustness"] > 0.93
        and record["development_supported_claim_coverage"] == 1.0
        and record["heldout_supported_claim_coverage"] == 1.0
        and record["development_supported_correct_model_rate"] == 1.0
        and record["heldout_supported_correct_model_rate"] == 1.0
        and record["development_unsupported_refusal_rate"] == 1.0
        and record["heldout_unsupported_refusal_rate"] == 1.0
        and record["development_false_discovery_rate"] == 0.0
        and record["heldout_false_discovery_rate"] == 0.0
        and record["development_interval_coverage"] == 1.0
        and record["heldout_interval_coverage"] == 1.0
        and record["development_true_hypothesis_retention_rate"] == 1.0
        and record["heldout_true_hypothesis_retention_rate"] == 1.0
        and record["development_premature_elimination_rate"] == 0.0
        and record["heldout_premature_elimination_rate"] == 0.0
        and record["pair_energy_force_invariants_passed"]
        and record["second_virial_boyle_checks_passed"]
        and record["early_ambiguity_passed"]
        and record["supported_model_discrimination_passed"]
        and record["hypothesis_retention_passed"]
        and record["acquisition_contrast_passed"]
        and record["minimum_acquisition_quality_gain"] > 0.35
        and record["fresh_process_per_world_passed"]
        and record["fail_closed_passed"]
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_CANDIDATE_ADMISSION_AUDIT",
        "evidence_scope": (
            "INTERNAL_SYNTHETIC_ACTIVE_PAIR_POTENTIAL_HYPOTHESIS_ADMISSION_"
            "NOT_MOLECULAR_DYNAMICS_MATERIAL_THERMODYNAMIC_OR_AUTONOMOUS_"
            "DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
        },
        "records": [record],
        "summary": {
            "task_count": 1,
            "recommended_candidate_count": int(record["passed"]),
            "recommended_quarantine_count": int(not record["passed"]),
            "resolved_capability_gap_count": int(record["passed"]),
        },
    }
    finalize_report_trust(report, record["passed"])
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "execution_passed": report["execution_passed"],
        "trust_decision": report["trust_decision"],
        **report["summary"],
    }, indent=2))
    print("Report: %s" % args.output.resolve())
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
