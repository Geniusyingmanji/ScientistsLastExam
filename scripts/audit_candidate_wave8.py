#!/usr/bin/env python3
"""Audit wave-8 raw-instrument QCM candidate admission gates."""

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


TASK_ID = "Sensors/QuartzCrystalMicrobalanceLab"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit():
    calibration = _load(
        ROOT / "scripts/calibrate_qcm_raw_pipeline.py",
        "wave8_qcm_raw_calibration",
    ).calibrate()
    reference = calibration["truth_blind_reference"]
    baseline = calibration["secure_weak_baseline"]
    classification = calibration["classification_and_missingness_checks"]
    isolation = calibration["secure_isolation_and_failure_checks"]
    resonance = calibration["independent_resonance_checks"]
    affine = calibration["complex_affine_calibration_checks"]
    robustness_shifts = calibration["sealed_robustness_shift_checks"]
    record = {
        "task": TASK_ID,
        "admission": "candidate",
        "resolved_capability_gap": (
            "adds an I6 raw-instrument-to-scientific-conclusion pipeline rather "
            "than another clean-array optimizer: quantized I/Q standards, "
            "time-varying complex calibration, missing samples, multi-harmonic "
            "BVD extraction, Sauerbrey inference, sealed prediction and stop "
            "decision, evidence lineage, physical-model refusal and distinct "
            "instrument-fault diagnosis"
        ),
        **calibration["task_dimensions"],
        "baseline_score": baseline["combined_score"],
        "truth_blind_development_score": reference["combined_score"],
        "truth_blind_heldout_score": reference["heldout_policy_score"],
        "truth_blind_development_robustness": reference[
            "robustness_score"
        ],
        "truth_blind_heldout_robustness": reference[
            "heldout_robustness_score"
        ],
        "development_supported_claim_coverage": reference[
            "development_supported_claim_coverage"
        ],
        "heldout_supported_claim_coverage": reference[
            "heldout_supported_claim_coverage"
        ],
        "development_unsupported_refusal_rate": reference[
            "development_unsupported_refusal_rate"
        ],
        "heldout_unsupported_refusal_rate": reference[
            "heldout_unsupported_refusal_rate"
        ],
        "development_fault_diagnosis_accuracy": reference[
            "development_fault_diagnosis_accuracy"
        ],
        "heldout_fault_diagnosis_accuracy": reference[
            "heldout_fault_diagnosis_accuracy"
        ],
        "development_false_discovery_rate": reference[
            "development_false_discovery_rate"
        ],
        "heldout_false_discovery_rate": reference[
            "heldout_false_discovery_rate"
        ],
        "independent_resonance_checks_passed": resonance["passed"],
        "complex_affine_calibration_checks_passed": affine["passed"],
        "missing_supported_recovery_passed": classification[
            "missing_supported_recovery_passed"
        ],
        "physical_anomaly_classification_passed": classification[
            "physical_anomaly_classification_passed"
        ],
        "instrument_fault_classification_passed": classification[
            "instrument_fault_classification_passed"
        ],
        "sealed_rate_and_sauerbrey_shift_checks_passed": robustness_shifts[
            "passed"
        ],
        "fresh_process_per_world_passed": isolation[
            "fresh_process_per_world_passed"
        ],
        "fail_closed_passed": isolation["fail_closed_passed"],
        "search_visible_metric_keys": calibration[
            "search_visible_metric_keys"
        ],
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
        and record["truth_blind_development_score"] > 0.98
        and record["truth_blind_heldout_score"] > 0.98
        and record["truth_blind_development_robustness"] > 0.80
        and record["truth_blind_heldout_robustness"] > 0.90
        and record["development_supported_claim_coverage"] == 1.0
        and record["heldout_supported_claim_coverage"] == 1.0
        and record["development_unsupported_refusal_rate"] == 1.0
        and record["heldout_unsupported_refusal_rate"] == 1.0
        and record["development_fault_diagnosis_accuracy"] == 1.0
        and record["heldout_fault_diagnosis_accuracy"] == 1.0
        and record["development_false_discovery_rate"] == 0.0
        and record["heldout_false_discovery_rate"] == 0.0
        and record["independent_resonance_checks_passed"]
        and record["complex_affine_calibration_checks_passed"]
        and record["missing_supported_recovery_passed"]
        and record["physical_anomaly_classification_passed"]
        and record["instrument_fault_classification_passed"]
        and record["sealed_rate_and_sauerbrey_shift_checks_passed"]
        and record["fresh_process_per_world_passed"]
        and record["fail_closed_passed"]
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_CANDIDATE_ADMISSION_AUDIT",
        "evidence_scope": (
            "INTERNAL_SYNTHETIC_RAW_IQ_QCM_PIPELINE_ADMISSION_NOT_PHYSICAL_"
            "INSTRUMENT_FILM_MATERIAL_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
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
