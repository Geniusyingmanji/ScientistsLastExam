#!/usr/bin/env python3
"""Calibrate the stateful CatalystDeactivationLab-v1 task and references."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Chemistry/CatalystDeactivationLab"
sys.path.insert(0, str(ROOT))

from sle.evaluate import evaluate_candidate  # noqa: E402
from sle.metric_visibility import search_visible_metrics  # noqa: E402
from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402
from sle.registry import find_task  # noqa: E402


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("catalyst_lab_calibration", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load catalyst laboratory oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _independent_integral_checks(oracle):
    rows = []
    maximum_product_gap = 0.0
    maximum_activity_gap = 0.0
    for index, spec in enumerate(
        oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS
    ):
        world = oracle._make_world(spec)
        values = (
            0.92 - 0.025 * index,
            world["log10_a"],
            world["activation_energy"],
            world["d_ref"],
            450.0 + 13.0 * index,
            0.22 + 0.09 * index,
            4.0 + 0.85 * index,
        )
        exact = oracle._closed_form_reaction(*values)
        independent = oracle._numerical_reaction(*values)
        product_gap = abs(exact[0] - independent[0])
        activity_gap = abs(exact[1] - independent[1])
        maximum_product_gap = max(maximum_product_gap, product_gap)
        maximum_activity_gap = max(maximum_activity_gap, activity_gap)
        rows.append({
            "seed": int(spec[0]),
            "kind": str(spec[1]),
            "closed_form_product": exact[0],
            "independent_product": independent[0],
            "product_abs_gap": product_gap,
            "closed_form_post_activity": exact[1],
            "independent_post_activity": independent[1],
            "post_activity_abs_gap": activity_gap,
        })
    return {
        "records": rows,
        "maximum_product_abs_gap": maximum_product_gap,
        "maximum_post_activity_abs_gap": maximum_activity_gap,
        "passed": maximum_product_gap < 3e-9 and maximum_activity_gap < 1e-12,
    }


def _state_machine_checks(oracle):
    laboratory = oracle._StatefulLaboratory(
        oracle._make_world(oracle.DEVELOPMENT_SPECS[0])
    )
    problem = laboratory.public_problem()
    coupon = problem["coupon_ids"][0]
    request = {
        "request_id": "calibration-reaction",
        "kind": "reaction",
        "lab_state_version": 0,
        "coupon_id": coupon,
        "coupon_state_version": 0,
        "temperature_k": 445.0,
        "feed_concentration": 0.25,
        "duration_min": 15.0,
    }
    first = laboratory.experiment([
        request,
        {"request_id": "calibration-blank", "kind": "blank",
         "lab_state_version": 0},
        {"request_id": "calibration-standard", "kind": "standard",
         "lab_state_version": 0},
    ])
    first_physical_acts = laboratory.physical_acts
    first_version = laboratory.lab_state_version
    reaction_event = next(
        event for event in first["events"]
        if event["request_id"] == request["request_id"]
    )
    retry = laboratory.experiment([request])
    exact_retry_is_idempotent = bool(
        laboratory.physical_acts == first_physical_acts
        and laboratory.lab_state_version == first_version
        and retry["events"][0]["event_id"] == reaction_event["event_id"]
    )

    failure_checks = {}
    for name in ("stale_parent", "conflicting_retry"):
        lab = oracle._StatefulLaboratory(
            oracle._make_world(oracle.DEVELOPMENT_SPECS[1])
        )
        current = lab.public_problem()
        if name == "stale_parent":
            lab.experiment([{
                "request_id": "first", "kind": "blank", "lab_state_version": 0,
            }])
            value = {"request_id": "stale", "kind": "blank", "lab_state_version": 0}
        else:
            original = {"request_id": "repeat", "kind": "blank", "lab_state_version": 0}
            lab.experiment([original])
            value = {"request_id": "repeat", "kind": "standard", "lab_state_version": 0}
        try:
            lab.experiment([value])
            rejected = False
        except Exception:
            rejected = lab.failure == name
        failure_checks[name] = bool(rejected)

    return {
        "out_of_order_completion": laboratory.out_of_order_batch_count == 1,
        "exact_retry_is_idempotent": exact_retry_is_idempotent,
        "exact_retry_count": laboratory.exact_retry_count,
        "duplicate_physical_act_count": laboratory.duplicate_physical_act_count,
        "reaction_post_coupon_version": reaction_event["post_coupon_state_version"],
        "reaction_remaining_uses": reaction_event["remaining_coupon_uses"],
        "failure_checks": failure_checks,
        "passed": bool(
            laboratory.out_of_order_batch_count == 1
            and exact_retry_is_idempotent
            and laboratory.exact_retry_count == 1
            and laboratory.duplicate_physical_act_count == 0
            and reaction_event["post_coupon_state_version"] == 1
            and reaction_event["remaining_coupon_uses"]
            == oracle.COUPON_MAX_REACTIONS - 1
            and all(failure_checks.values())
        ),
    }


def calibrate():
    oracle = _load_oracle()
    spec = find_task(
        "Catalysis/CatalystDeactivationLab", include_uncertified=True
    )
    solution_spec = importlib.util.spec_from_file_location(
        "catalyst_lab_baseline", TASK / "solution.py"
    )
    solution = importlib.util.module_from_spec(solution_spec)
    solution_spec.loader.exec_module(solution)
    direct_baseline = oracle.evaluate(solution.investigate_catalyst)
    secure_baseline = evaluate_candidate(
        spec, spec.initial_program_path, timeout_s=120
    )
    reference = oracle.evaluate(oracle._reference_agent)
    truth_rows = [
        oracle._evaluate_truth_world(spec_value, split, index)
        for split, specs in (
            ("development", oracle.DEVELOPMENT_SPECS),
            ("heldout", oracle.HELDOUT_SPECS),
        )
        for index, spec_value in enumerate(specs)
    ]
    integrals = _independent_integral_checks(oracle)
    state_machine = _state_machine_checks(oracle)
    visible = search_visible_metrics(secure_baseline)
    direct_json = json.loads(json.dumps(direct_baseline, allow_nan=False))
    direct_json["raw_score"] = direct_json["combined_score"]
    supported_reference = [
        row for row in reference["per_world"] if row["kind"] == "in_library"
    ]
    unsupported_reference = [
        row for row in reference["per_world"] if row["kind"] != "in_library"
    ]
    execution_passed = bool(
        oracle.CATALYST_DEACTIVATION_LAB_V1
        and len(oracle.DEVELOPMENT_SPECS) == 5
        and len(oracle.HELDOUT_SPECS) == 3
        and integrals["passed"]
        and state_machine["passed"]
        and secure_baseline == direct_json
        and secure_baseline["valid"] == 1.0
        and secure_baseline["combined_score"] == 0.0
        and secure_baseline["robustness_score"] == 0.0
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
        and reference["duplicate_physical_act_count"] == 0
        and reference["stale_parent_attempt_count"] == 0
        and reference["development_mean_exact_retries"] == 1.0
        and reference["heldout_mean_exact_retries"] == 1.0
        and all(row["joint_quality"] == 1.0 for row in truth_rows)
        and all(row["robust_joint_quality"] > 0.80 for row in truth_rows)
        and all(not row["abstained"] for row in supported_reference)
        and all(row["abstained"] for row in unsupported_reference)
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "SYNTHETIC_STATEFUL_CATALYST_KINETICS_AND_INSTRUMENT_DRIFT_"
            "CALIBRATION_NOT_REACTOR_CATALYST_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {
            "python": sys.version,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "task": "Catalysis/CatalystDeactivationLab",
        "task_source_sha256": {
            str(path.relative_to(ROOT)): _sha256(path)
            for path in (
                TASK / "Task.md", TASK / "TASK_CARD.yaml", TASK / "solution.py",
                TASK / "verification/evaluator.py",
                TASK / "frontier_eval/metadata.yaml",
            )
        },
        "task_dimensions": {
            "development_world_count": len(oracle.DEVELOPMENT_SPECS),
            "heldout_world_count": len(oracle.HELDOUT_SPECS),
            "coupon_count_per_world": oracle.COUPON_COUNT,
            "maximum_reactions_per_coupon": oracle.COUPON_MAX_REACTIONS,
            "physical_act_budget": oracle.PHYSICAL_ACT_BUDGET,
            "maximum_batch_size": oracle.MAX_BATCH_SIZE,
            "supported_world_count": sum(
                spec_value[1] == "in_library"
                for spec_value in oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS
            ),
            "unsupported_world_count": sum(
                spec_value[1] != "in_library"
                for spec_value in oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS
            ),
        },
        "independent_integral_checks": integrals,
        "state_machine_checks": state_machine,
        "direct_weak_baseline": direct_baseline,
        "secure_weak_baseline": secure_baseline,
        "secure_baseline_exactly_matches_direct": secure_baseline == direct_json,
        "truth_blind_reference": reference,
        "truth_reference_records": truth_rows,
        "search_visible_metric_keys": sorted(visible),
        "limitations": [
            "This is a deterministic procedural reduced-order state machine, not a physical reactor or instrument.",
            "The kinetic family omits transport, thermal gradients, complex adsorption, catalyst characterization and safety constraints.",
            "Out-of-order completion is deterministic latency replay, not a real asynchronous laboratory service.",
            "Fixed public equations and repository-visible worlds require server-held cohorts and contamination auditing.",
            "Reference policies are reproducible normalization witnesses, not global optima or catalyst discoveries.",
            "Engineering and discovery claims require independent catalysis review, real instrumentation, fresh catalysts and experimental replication.",
        ],
        "execution_passed": execution_passed,
    }
    finalize_report_trust(report, execution_passed)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = calibrate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "execution_passed": report["execution_passed"],
        "trust_decision": report["trust_decision"],
        "reference_development": report["truth_blind_reference"]["combined_score"],
        "reference_heldout": report["truth_blind_reference"]["heldout_policy_score"],
    }, indent=2))
    print("Report: %s" % args.output.resolve())
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
