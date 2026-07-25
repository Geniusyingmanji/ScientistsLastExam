#!/usr/bin/env python3
"""Audit the wave-5 evidence-synthesis candidate admission gates."""

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

from frontier_science.evaluate import evaluate_candidate  # noqa: E402
from frontier_science.metric_visibility import search_visible_metrics  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402
from frontier_science.registry import find_task  # noqa: E402


TASK_ID = "EvidenceSynthesis/ProspectiveMetaAnalysis"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit():
    task = ROOT / "benchmarks" / TASK_ID
    oracle = _load(task / "verification/evaluator.py", "wave5_meta_oracle")
    calibration = _load(
        ROOT / "scripts/calibrate_prospective_meta_analysis.py",
        "wave5_meta_calibration",
    ).calibrate()
    spec = find_task(TASK_ID, include_uncertified=True)
    secure = evaluate_candidate(spec, spec.initial_program_path, timeout_s=120)
    reference = oracle.evaluate(oracle.reference_policy)
    truth = oracle.evaluate(oracle.oracle_reference_policy)
    visible = search_visible_metrics(secure)
    world_checks = calibration["world_checks"]
    record = {
        "task": TASK_ID,
        "admission": "candidate",
        "resolved_capability_gap": (
            "adds a prospective evidence-synthesis workflow rather than another clean-"
            "simulator scalar optimizer: registry screening, participant-lineage de-"
            "duplication, preregistered-primary extraction, selective-report flags, "
            "heterogeneous inference, model-family refusal, immutable pre-result forecast/"
            "study commit and one fresh prospective confirmation"
        ),
        "development_world_count": len(oracle.DEVELOPMENT_SPECS),
        "heldout_world_count": len(oracle.HELDOUT_SPECS),
        "eligible_lineages_per_world": 14,
        "supported_world_count": sum(
            kind != "nonlinear"
            for _, kind in oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS
        ),
        "unsupported_world_count": sum(
            kind == "nonlinear"
            for _, kind in oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS
        ),
        "baseline_score": secure["combined_score"],
        "truth_blind_development_score": reference["combined_score"],
        "truth_blind_heldout_score": reference["heldout_policy_score"],
        "truth_blind_development_robustness": reference["robustness_score"],
        "truth_blind_heldout_robustness": reference["heldout_robustness_score"],
        "truth_blind_development_false_discovery_rate": reference[
            "development_false_discovery_rate"
        ],
        "truth_blind_heldout_false_discovery_rate": reference[
            "heldout_false_discovery_rate"
        ],
        "truth_blind_development_unsupported_refusal_rate": reference[
            "development_unsupported_refusal_rate"
        ],
        "truth_blind_heldout_unsupported_refusal_rate": reference[
            "heldout_unsupported_refusal_rate"
        ],
        "oracle_reference_score": truth["combined_score"],
        "oracle_reference_robustness": truth["robustness_score"],
        "maximum_independent_beta_gap": world_checks[
            "maximum_independent_beta_gap"
        ],
        "minimum_nonlinear_lack_of_fit_z": world_checks[
            "minimum_nonlinear_lack_of_fit_z"
        ],
        "maximum_supported_lack_of_fit_z": world_checks[
            "maximum_supported_lack_of_fit_z"
        ],
        "minimum_naive_highlighted_article_intercept_bias": world_checks[
            "minimum_naive_highlighted_article_intercept_bias"
        ],
        "search_visible_metric_keys": sorted(visible),
        "limitations": calibration["limitations"],
    }
    record["passed"] = bool(
        oracle.PROSPECTIVE_META_ANALYSIS_V1
        and calibration["execution_passed"]
        and calibration["world_checks"]["passed"]
        and calibration["invalid_artifact_checks"]["passed"]
        and secure["valid"] == 1.0
        and secure["combined_score"] == 0.0
        and secure["robustness_score"] == 0.0
        and set(visible) == {
            "combined_score", "valid", "feasibility_rate", "raw_score"
        }
        and 0.75 < reference["combined_score"] < 0.99
        and 0.70 < reference["heldout_policy_score"] < 0.99
        and reference["development_evidence_integrity_score"] == 1.0
        and reference["heldout_evidence_integrity_score"] == 1.0
        and reference["development_false_discovery_rate"] == 0.0
        and reference["heldout_false_discovery_rate"] == 0.0
        and reference["development_unsupported_refusal_rate"] == 1.0
        and reference["heldout_unsupported_refusal_rate"] == 1.0
        and reference["development_mean_confirmation_calls"] == 1.0
        and reference["heldout_mean_confirmation_calls"] == 1.0
        and truth["combined_score"] == 1.0
        and truth["robustness_score"] == 1.0
        and truth["heldout_policy_score"] == 1.0
        and truth["heldout_robustness_score"] == 1.0
        and world_checks["minimum_nonlinear_lack_of_fit_z"] > 2.0
        and world_checks["maximum_supported_lack_of_fit_z"] < 2.0
        and world_checks["minimum_naive_highlighted_article_intercept_bias"] > 0.01
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_ADMISSION_AUDIT",
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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        key: report[key]
        for key in ("passed", "execution_passed", "trust_decision", "trusted_evidence")
    }, indent=2))
    print("Report: %s" % args.output.resolve())
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
