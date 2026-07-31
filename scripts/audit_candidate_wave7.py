#!/usr/bin/env python3
"""Audit wave-7 stateful catalyst-laboratory candidate admission gates."""

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


TASK_ID = "Catalysis/CatalystDeactivationLab"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit():
    task = find_task(TASK_ID, include_uncertified=True).task_dir
    oracle = _load(task / "verification/evaluator.py", "wave7_catalyst_oracle")
    calibration = _load(
        ROOT / "scripts/calibrate_catalyst_deactivation_lab.py",
        "wave7_catalyst_calibration",
    ).calibrate()
    spec = find_task(TASK_ID, include_uncertified=True)
    secure = evaluate_candidate(spec, spec.initial_program_path, timeout_s=120)
    reference = oracle.evaluate(oracle._reference_agent)
    visible = search_visible_metrics(secure)
    record = {
        "task": TASK_ID,
        "admission": "candidate",
        "resolved_capability_gap": (
            "adds a path-dependent scientific laboratory rather than another static "
            "artifact optimizer: raw calibration drift, finite catalyst coupons, "
            "irreversible deactivation, out-of-order batch completion, idempotent "
            "physical retries, stale-parent rejection, model-family refusal and a "
            "separate sealed fresh-batch operating decision"
        ),
        "development_world_count": len(oracle.DEVELOPMENT_SPECS),
        "heldout_world_count": len(oracle.HELDOUT_SPECS),
        "coupon_count_per_world": oracle.COUPON_COUNT,
        "maximum_reactions_per_coupon": oracle.COUPON_MAX_REACTIONS,
        "physical_act_budget": oracle.PHYSICAL_ACT_BUDGET,
        "maximum_batch_size": oracle.MAX_BATCH_SIZE,
        "baseline_score": secure["combined_score"],
        "truth_blind_development_score": reference["combined_score"],
        "truth_blind_heldout_score": reference["heldout_policy_score"],
        "truth_blind_development_robustness": reference["robustness_score"],
        "truth_blind_heldout_robustness": reference["heldout_robustness_score"],
        "truth_blind_development_refusal_rate": reference[
            "development_unsupported_refusal_rate"
        ],
        "truth_blind_heldout_refusal_rate": reference[
            "heldout_unsupported_refusal_rate"
        ],
        "truth_blind_development_false_discovery_rate": reference[
            "development_false_discovery_rate"
        ],
        "truth_blind_heldout_false_discovery_rate": reference[
            "heldout_false_discovery_rate"
        ],
        "mean_physical_acts": reference["development_mean_physical_acts"],
        "mean_exact_retries": reference["development_mean_exact_retries"],
        "mean_out_of_order_batches": reference[
            "development_mean_out_of_order_batches"
        ],
        "duplicate_physical_act_count": reference[
            "duplicate_physical_act_count"
        ],
        "stale_parent_attempt_count": reference["stale_parent_attempt_count"],
        "maximum_independent_product_gap": calibration[
            "independent_integral_checks"
        ]["maximum_product_abs_gap"],
        "state_machine_checks": calibration["state_machine_checks"],
        "search_visible_metric_keys": sorted(visible),
        "limitations": calibration["limitations"],
    }
    record["passed"] = bool(
        oracle.CATALYST_DEACTIVATION_LAB_V1
        and calibration["execution_passed"]
        and calibration["independent_integral_checks"]["passed"]
        and calibration["state_machine_checks"]["passed"]
        and secure["valid"] == 1.0
        and secure["combined_score"] == 0.0
        and secure["robustness_score"] == 0.0
        and set(visible) == {
            "combined_score", "valid", "feasibility_rate", "raw_score"
        }
        and 0.85 < reference["combined_score"] < 0.995
        and 0.85 < reference["heldout_policy_score"] < 0.995
        and reference["robustness_score"] > 0.75
        and reference["heldout_robustness_score"] > 0.75
        and reference["development_supported_claim_coverage"] == 1.0
        and reference["heldout_supported_claim_coverage"] == 1.0
        and reference["development_unsupported_refusal_rate"] == 1.0
        and reference["heldout_unsupported_refusal_rate"] == 1.0
        and reference["development_false_discovery_rate"] == 0.0
        and reference["heldout_false_discovery_rate"] == 0.0
        and reference["development_mean_physical_acts"] == 12.0
        and reference["development_mean_exact_retries"] == 1.0
        and reference["development_mean_out_of_order_batches"] > 0.0
        and reference["duplicate_physical_act_count"] == 0
        and reference["stale_parent_attempt_count"] == 0
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_CANDIDATE_ADMISSION_AUDIT",
        "evidence_scope": (
            "INTERNAL_SYNTHETIC_STATEFUL_CATALYST_LAB_ADMISSION_NOT_"
            "PHYSICAL_REACTOR_CATALYST_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
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
