#!/usr/bin/env python3
"""Audit wave-10 DOI-held alloy-hardness candidate admission gates."""

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

from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


TASK_ID = "MaterialsScience/AlloyHardnessOptimization"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit(csv_path):
    calibration = _load(
        ROOT / "scripts/calibrate_alloy_hardness_optimization.py",
        "wave10_alloy_hardness_calibration",
    ).calibrate(csv_path)
    baseline = calibration["secure_baseline_metrics"]
    reference = calibration["truth_blind_assay_metrics"]
    counts = calibration["counts"]
    checks = calibration["checks"]
    isolation = calibration["secure_isolation_and_failure_checks"]
    record = {
        "task": TASK_ID,
        "admission": "candidate",
        "resolved_capability_gap": (
            "replaces a source-free five-element polynomial with a hash-bound "
            "Borg MPEA literature replay: full-DOI grouping, leakage-free "
            "historical proxy, two charged study assays, three-alloy batch "
            "selection, forced unmeasured prediction, calibrated intervals, "
            "hash-held study transfer and sparse exact-recipe confirmation "
            "reserved from proxy fitting"
        ),
        **counts,
        "development_world_count": 8,
        "heldout_world_count": 5,
        "assay_budget": 2,
        "batch_size": 3,
        "baseline_score": baseline["combined_score"],
        "truth_blind_development_score": reference["combined_score"],
        "truth_blind_heldout_score": reference["heldout_policy_score"],
        "truth_blind_development_prediction_score": reference[
            "development_prediction_score"
        ],
        "truth_blind_heldout_prediction_score": reference[
            "heldout_prediction_score"
        ],
        "development_unmeasured_interval_coverage": reference[
            "development_unmeasured_interval_coverage"
        ],
        "heldout_unmeasured_interval_coverage": reference[
            "heldout_unmeasured_interval_coverage"
        ],
        "development_selected_confirmation_coverage": reference[
            "development_selected_confirmation_coverage"
        ],
        "heldout_selected_confirmation_coverage": reference[
            "heldout_selected_confirmation_coverage"
        ],
        "source_target_dois_disjoint": checks["source_target_dois_disjoint"],
        "source_target_exact_recipes_disjoint": checks[
            "source_target_exact_recipes_disjoint"
        ],
        "confirmation_not_in_proxy_source": checks[
            "confirmation_not_in_proxy_source"
        ],
        "data_rebuild_exact_match": calibration["data_rebuild"]["exact_match"],
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
        and baseline["heldout_policy_score"] == 0.0
        and set(record["search_visible_metric_keys"]) == {
            "combined_score", "valid", "feasibility_rate", "raw_score"
        }
        and record["historical_proxy_recipes"] == 197
        and record["historical_proxy_studies"] == 44
        and record["reserved_confirmation_recipes"] == 9
        and record["target_recipes"] == 65
        and record["target_studies"] == 13
        and record["truth_blind_development_score"] > 0.30
        and record["truth_blind_heldout_score"] > 0.30
        and record["truth_blind_development_prediction_score"] > 0.50
        and record["truth_blind_heldout_prediction_score"] > 0.50
        and record["development_unmeasured_interval_coverage"] >= 0.90
        and record["heldout_unmeasured_interval_coverage"] >= 0.90
        and record["source_target_dois_disjoint"]
        and record["source_target_exact_recipes_disjoint"]
        and record["confirmation_not_in_proxy_source"]
        and record["data_rebuild_exact_match"]
        and record["fresh_process_per_world_passed"]
        and record["fail_closed_passed"]
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_CANDIDATE_ADMISSION_AUDIT",
        "evidence_scope": (
            "INTERNAL_RETROSPECTIVE_DOI_GROUPED_MPEA_HARDNESS_ADMISSION_"
            "NOT_PROSPECTIVE_SYNTHESIS_MECHANICAL_VALIDATION_OR_AUTONOMOUS_"
            "DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
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
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
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
