#!/usr/bin/env python3
"""Build and audit fixed-seed MOSFETDoping-v2 Pareto witnesses."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Semiconductor/MOSFETDoping"
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


REFERENCE_SEED_BASE = 260724
REFERENCE_POWER = 11
ARCHIVE_SIZE = 16


def _file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _canonical(value):
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return tuple(_canonical(item) for item in value)
    return value


def _load_oracle():
    verification = TASK / "verification"
    sys.path.insert(0, str(verification))
    try:
        spec = importlib.util.spec_from_file_location(
            "mosfet_v2_calibration_oracle", verification / "evaluator.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError("cannot load MOSFETDoping-v2 oracle")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def _candidate_shortlist(oracle, problem, records_by_condition, allowed):
    selected = set()
    for records in records_by_condition:
        selected.update(oracle._pareto_indices(problem, records))
    for weight in np.linspace(0.0, 1.0, 81):
        ranked = sorted(
            allowed,
            key=lambda index: (
                np.mean([
                    weight * oracle._quality(problem, records[index])[0]
                    + (1.0 - weight)
                    * oracle._quality(problem, records[index])[1]
                    for records in records_by_condition
                ]),
                np.mean([
                    sum(oracle._quality(problem, records[index]))
                    for records in records_by_condition
                ]),
                -index,
            ),
            reverse=True,
        )
        selected.update(ranked[:12])
    selected.intersection_update(allowed)
    return sorted(selected)


def _mean_hypervolume(oracle, problem, records_by_condition, indices):
    if not indices:
        return 0.0
    return float(np.mean([
        oracle._hypervolume(problem, [records[index] for index in indices])
        for records in records_by_condition
    ]))


def _select_archive(oracle, problem, records_by_condition, require_all_feasible):
    if require_all_feasible:
        allowed = [
            index for index in range(len(records_by_condition[0]))
            if all(records[index]["process_feasible"]
                   for records in records_by_condition)
        ]
    else:
        allowed = [
            index for index, record in enumerate(records_by_condition[0])
            if record["process_feasible"]
        ]
    if len(allowed) < ARCHIVE_SIZE:
        raise RuntimeError("reference pool has fewer than 16 allowed designs")
    shortlist = _candidate_shortlist(
        oracle, problem, records_by_condition, allowed
    )
    chosen = []
    remaining = set(shortlist)
    while remaining and len(chosen) < ARCHIVE_SIZE:
        best = max(
            remaining,
            key=lambda index: (
                _mean_hypervolume(
                    oracle, problem, records_by_condition, chosen + [index]
                ),
                np.mean([
                    sum(oracle._quality(problem, records[index]))
                    for records in records_by_condition
                ]),
                -index,
            ),
        )
        chosen.append(best)
        remaining.remove(best)
    if len(chosen) != ARCHIVE_SIZE:
        raise RuntimeError("could not select a 16-design reference archive")
    return tuple(chosen), len(allowed), len(shortlist)


def _finite_record(record):
    for value in record.values():
        if isinstance(value, (float, np.floating)) and not np.isfinite(value):
            return False
    return True


def build_report():
    oracle = _load_oracle()
    instances = []
    reference_literal = {}
    anchors_literal = {}
    overall = True
    for offset, instance in enumerate(oracle.INSTANCES):
        seed = REFERENCE_SEED_BASE + offset
        spec = {"seed": seed, "power": REFERENCE_POWER}
        pool = oracle._sobol_pool(spec)
        nominal_records = oracle._evaluate_archive(pool, instance["device"])
        shifted_records = [
            oracle._evaluate_archive(pool, instance["device"], shift)
            for shift in oracle.SHIFT_SPECS
        ]
        nominal_indices, nominal_allowed, nominal_shortlist = _select_archive(
            oracle, instance["problem"], [nominal_records], False
        )
        robust_indices, robust_allowed, robust_shortlist = _select_archive(
            oracle, instance["problem"], shifted_records, True
        )
        baseline = oracle._baseline_archive(instance["problem"])
        nominal = pool[np.asarray(nominal_indices, dtype=int)]
        robust = pool[np.asarray(robust_indices, dtype=int)]
        baseline_nominal = oracle._evaluate_archive(
            baseline, instance["device"]
        )
        reference_nominal = oracle._evaluate_archive(
            nominal, instance["device"]
        )
        baseline_shifts = [
            oracle._evaluate_archive(baseline, instance["device"], shift)
            for shift in oracle.SHIFT_SPECS
        ]
        reference_shifts = [
            oracle._evaluate_archive(robust, instance["device"], shift)
            for shift in oracle.SHIFT_SPECS
        ]
        baseline_nominal_hv = oracle._hypervolume(
            instance["problem"], baseline_nominal
        )
        reference_nominal_hv = oracle._hypervolume(
            instance["problem"], reference_nominal
        )
        baseline_shift_hv = [
            oracle._hypervolume(instance["problem"], records)
            for records in baseline_shifts
        ]
        reference_shift_hv = [
            oracle._hypervolume(instance["problem"], records)
            for records in reference_shifts
        ]
        baseline_feasible = [
            sum(record["process_feasible"] for record in records)
            for records in [baseline_nominal] + baseline_shifts
        ]
        reference_feasible = [
            sum(record["process_feasible"] for record in records)
            for records in [reference_nominal] + reference_shifts
        ]
        anchors = {
            "baseline_nominal_hypervolume": baseline_nominal_hv,
            "reference_nominal_hypervolume": reference_nominal_hv,
            "baseline_shifted_hypervolumes": baseline_shift_hv,
            "reference_shifted_hypervolumes": reference_shift_hv,
        }
        passed = bool(
            nominal_allowed >= 256
            and robust_allowed >= 128
            and len(set(nominal_indices)) == ARCHIVE_SIZE
            and len(set(robust_indices)) == ARCHIVE_SIZE
            and reference_nominal_hv > baseline_nominal_hv + 1e-3
            and all(
                reference > baseline + 1e-3
                for baseline, reference in zip(
                    baseline_shift_hv, reference_shift_hv
                )
            )
            and baseline_feasible[0] >= oracle.MIN_NOMINAL_FEASIBLE
            and reference_feasible == [ARCHIVE_SIZE] * (1 + len(oracle.SHIFT_SPECS))
            and all(
                _finite_record(record)
                for records in (
                    [baseline_nominal, reference_nominal]
                    + baseline_shifts + reference_shifts
                )
                for record in records
            )
        )
        overall = overall and passed
        reference_literal[instance["name"]] = {
            "seed": seed,
            "power": REFERENCE_POWER,
            "nominal": nominal_indices,
            "robust": robust_indices,
        }
        anchors_literal[instance["name"]] = anchors
        instances.append({
            "name": instance["name"],
            "split": instance["split"],
            "seed": seed,
            "power": REFERENCE_POWER,
            "pool_size": len(pool),
            "nominal_feasible_pool_count": nominal_allowed,
            "all_shift_feasible_pool_count": robust_allowed,
            "nominal_shortlist_size": nominal_shortlist,
            "robust_shortlist_size": robust_shortlist,
            "nominal_indices": list(nominal_indices),
            "robust_indices": list(robust_indices),
            "anchors": anchors,
            "baseline_feasible_counts": baseline_feasible,
            "reference_feasible_counts": reference_feasible,
            "passed": passed,
        })

    committed_literals_match = bool(
        _canonical(reference_literal) == _canonical(oracle.REFERENCE_SOBOL)
        and _canonical(anchors_literal) == _canonical(oracle.CALIBRATED_ANCHORS)
    )
    overall = overall and committed_literals_match

    def policy(kind):
        def design(problem):
            for instance in oracle.INSTANCES:
                if instance["problem"] == problem:
                    if kind == "baseline":
                        return oracle._baseline_archive(problem)
                    return oracle._reference_archive(instance, kind)
            raise ValueError("unknown MOSFET-v2 public problem")
        return design

    baseline_witness = oracle.evaluate(policy("baseline"))
    nominal_witness = oracle.evaluate(policy("nominal"))
    robust_witness = oracle.evaluate(policy("robust"))
    witness_tradeoff_checks = {
        "baseline_is_zero_valid_witness": bool(
            baseline_witness["valid"] == 1.0
            and baseline_witness["combined_score"] == 0.0
            and baseline_witness["heldout_policy_score"] == 0.0
        ),
        "nominal_witness_reaches_nominal_anchors": bool(
            nominal_witness["valid"] == 1.0
            and nominal_witness["combined_score"] > 0.999999
            and nominal_witness["heldout_policy_score"] > 0.999999
        ),
        "nominal_witness_exposes_shift_failure": bool(
            nominal_witness["robustness_score"] < 0.05
            and nominal_witness["development_shift_feasibility_rate"] < 0.90
            and nominal_witness["heldout_shift_feasibility_rate"] < 0.90
        ),
        "robust_witness_reaches_worst_shift_anchors": bool(
            robust_witness["valid"] == 1.0
            and robust_witness["robustness_score"] > 0.999999
            and robust_witness["heldout_robustness_score"] > 0.999999
            and robust_witness["development_shift_feasibility_rate"] == 1.0
            and robust_witness["heldout_shift_feasibility_rate"] == 1.0
        ),
        "robust_witness_trades_nominal_hypervolume": bool(
            0.85 < robust_witness["combined_score"] < 0.98
            and 0.80 < robust_witness["heldout_policy_score"] < 0.98
        ),
    }
    overall = overall and all(witness_tradeoff_checks.values())

    # These probes exercise physical directions independently of the frozen references.
    probe = np.asarray((16.2, 17.1, 17.1, 0.16, 0.84, 0.08))
    device = oracle.INSTANCES[0]["device"]
    nominal_probe = oracle.evaluate_device(probe, device)
    hotter_probe = oracle.evaluate_device(
        probe, device, {"temperature_delta_k": 35.0}
    )
    lower_doping = probe.copy()
    lower_doping[:3] -= 0.5
    lower_record = oracle.evaluate_device(lower_doping, device)
    higher_doping = probe.copy()
    higher_doping[:3] += 0.5
    higher_record = oracle.evaluate_device(higher_doping, device)
    directional_checks = {
        "higher_doping_raises_threshold": (
            higher_record["threshold_voltage_v"]
            > lower_record["threshold_voltage_v"]
        ),
        "higher_doping_reduces_effective_mobility": (
            higher_record["effective_mobility_cm2_vs"]
            < lower_record["effective_mobility_cm2_vs"]
        ),
        "higher_temperature_increases_subthreshold_swing": (
            hotter_probe["subthreshold_swing_mv_dec"]
            > nominal_probe["subthreshold_swing_mv_dec"]
        ),
        "higher_temperature_increases_off_current": (
            hotter_probe["off_current_na_per_um"]
            > nominal_probe["off_current_na_per_um"]
        ),
        "all_finite": all(_finite_record(record) for record in (
            nominal_probe, hotter_probe, lower_record, higher_record
        )),
    }
    overall = overall and all(directional_checks.values())
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "TASK_CALIBRATION_NOT_TCAD_MEASUREMENT_MODEL_PERFORMANCE_OR_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "model_scope": (
            "screened-Poisson drain coupling, MOS threshold electrostatics, "
            "Caughey-Thomas mobility, charge-sheet current and Poisson random-dopant variation"
        ),
        "task": "Semiconductor/MOSFETDoping",
        "task_source_sha256": {
            str(path.relative_to(ROOT)): _file_sha256(path)
            for path in (
                TASK / "verification/device.py",
                TASK / "verification/evaluator.py",
                TASK / "solution.py",
                TASK / "Task.md",
                TASK / "TASK_CARD.yaml",
            )
        },
        "task_dimensions": {
            "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
            "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
            "shift_count": len(oracle.SHIFT_SPECS),
            "sobol_power": REFERENCE_POWER,
            "sobol_pool_size_per_instance": 2 ** REFERENCE_POWER,
            "archive_size": ARCHIVE_SIZE,
        },
        "reference_claim": {
            "deterministic": True,
            "truth_blind_to_candidate": True,
            "global_optimality_claimed": False,
            "normalization_clips_better_feasible_candidates": True,
        },
        "instances": instances,
        "directional_checks": directional_checks,
        "witness_tradeoff_checks": witness_tradeoff_checks,
        "witness_metrics": {
            "baseline": baseline_witness,
            "nominal": nominal_witness,
            "robust": robust_witness,
        },
        "reference_sobol_literal": reference_literal,
        "anchors_literal": anchors_literal,
        "committed_literals_checked": True,
        "committed_literals_match": committed_literals_match,
        "limitations": [
            "The reduced-order compact model is not a two-dimensional self-consistent drift-diffusion, quantum-corrected or commercial TCAD solver.",
            "The Gaussian halo family omits source/drain junction resistance, gate leakage, band-to-band tunnelling, velocity overshoot, interface traps and detailed implant/anneal chemistry.",
            "The fixed repository devices and shifts require server-held procedural conditions before leakage-resistant population claims.",
            "The fixed Sobol witnesses are strong reproducible archives, not global Pareto-optimality certificates.",
            "Task calibration does not measure GPT-5.5, feedback causality, fabricated-device performance or autonomous scientific discovery."
        ],
    }
    finalize_report_trust(report, bool(overall))
    report["passed"] = bool(report["trusted_evidence"])
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build_report()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(output),
        "execution_passed": report["execution_passed"],
        "trust_decision": report["trust_decision"],
        "passed": report["passed"],
    }, indent=2))
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
