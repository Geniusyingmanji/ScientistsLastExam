#!/usr/bin/env python3
"""Calibrate the raw-I/Q QuartzCrystalMicrobalanceLab-v1 task."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Sensors/QuartzCrystalMicrobalanceLab"
sys.path.insert(0, str(ROOT))

from frontier_science.evaluate import evaluate_candidate  # noqa: E402
from frontier_science.metric_visibility import search_visible_metrics  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402
from frontier_science.registry import find_task  # noqa: E402


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _independent_peak_and_q(frequencies, values):
    frequencies = np.asarray(frequencies, dtype=float)
    conductance = np.real(np.asarray(values, dtype=complex))
    peak_index = int(np.argmax(conductance))
    peak_frequency = float(frequencies[peak_index])
    half_peak = float(conductance[peak_index]) / 2.0

    def crossing(pairs):
        for left, right in pairs:
            y0 = float(conductance[left] - half_peak)
            y1 = float(conductance[right] - half_peak)
            if y0 == 0.0:
                return float(frequencies[left])
            if y0 * y1 <= 0.0:
                weight = -y0 / (y1 - y0)
                return float(
                    frequencies[left]
                    + weight * (frequencies[right] - frequencies[left])
                )
        raise ValueError("half-power crossing is not bracketed")

    lower = crossing(
        (index, index + 1) for index in range(peak_index - 1, -1, -1)
    )
    upper = crossing(
        (index, index + 1)
        for index in range(peak_index, len(frequencies) - 1)
    )
    return peak_frequency, peak_frequency / (upper - lower)


def _independent_resonance_checks(oracle):
    records = []
    for harmonic in oracle.HARMONICS:
        resonance = harmonic * oracle.NOMINAL_FUNDAMENTAL_HZ - 31.5
        quality = {1: 31000.0, 3: 26000.0, 5: 20500.0}[harmonic]
        capacitance = {1: 31e-15, 3: 9.5e-15, 5: 5.8e-15}[harmonic]
        frequencies = np.linspace(
            resonance - 7.0 * resonance / quality,
            resonance + 7.0 * resonance / quality,
            4001,
        )
        values = oracle._bvd_admittance(
            frequencies, resonance, quality, capacitance
        )
        problem = {
            "motional_capacitance_initial_f_by_harmonic": {
                "1": 30e-15, "3": 10e-15, "5": 6e-15,
            },
            "shunt_capacitance_f": oracle.SHUNT_CAPACITANCE_F,
        }
        fitted_frequency, fitted_q, fitted_rms = oracle._fit_bvd(
            frequencies, values, harmonic, problem
        )
        independent_frequency, independent_q = _independent_peak_and_q(
            frequencies, values
        )
        record = {
            "harmonic": harmonic,
            "truth_frequency_hz": resonance,
            "bvd_frequency_hz": fitted_frequency,
            "independent_peak_frequency_hz": independent_frequency,
            "bvd_frequency_abs_error_hz": abs(fitted_frequency - resonance),
            "independent_frequency_abs_error_hz": abs(
                independent_frequency - resonance
            ),
            "truth_quality_factor": quality,
            "bvd_quality_factor": fitted_q,
            "independent_quality_factor": independent_q,
            "bvd_quality_relative_error": abs(fitted_q / quality - 1.0),
            "independent_quality_relative_error": abs(
                independent_q / quality - 1.0
            ),
            "bvd_scaled_rms": fitted_rms,
        }
        record["passed"] = bool(
            record["bvd_frequency_abs_error_hz"] < 1.0e-4
            and record["independent_frequency_abs_error_hz"] < 0.1
            and record["bvd_quality_relative_error"] < 2.0e-6
            and record["independent_quality_relative_error"] < 0.002
            and fitted_rms < 1.0e-8
        )
        records.append(record)
    return {
        "records": records,
        "passed": all(record["passed"] for record in records),
    }


def _calibration_recovery_checks(oracle):
    records = []
    for spec_value in oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS:
        world = oracle._make_world(spec_value)
        problem = oracle._public_problem(world)
        start = oracle._fit_affine(problem["calibration_blocks"][0])
        end = oracle._fit_affine(problem["calibration_blocks"][1])
        expected_recoverable = world["kind"] != "iq_conjugated"
        record = {
            "seed": int(spec_value[0]),
            "kind": world["kind"],
            "expected_recoverable": expected_recoverable,
            "start_offset_abs_error_counts": abs(
                start[0] - world["start_offset"]
            ),
            "end_offset_abs_error_counts": abs(end[0] - world["end_offset"]),
            "start_gain_relative_error": abs(
                start[1] - world["start_gain"]
            ) / abs(world["start_gain"]),
            "end_gain_relative_error": abs(
                end[1] - world["end_gain"]
            ) / abs(world["end_gain"]),
            "start_fit_rms_counts": start[2],
            "end_fit_rms_counts": end[2],
        }
        if expected_recoverable:
            record["passed"] = bool(
                record["start_offset_abs_error_counts"] < 7.0
                and record["end_offset_abs_error_counts"] < 7.0
                and record["start_gain_relative_error"] < 4.0e-4
                and record["end_gain_relative_error"] < 4.0e-4
                and max(start[2], end[2]) < 10.0
            )
        else:
            record["passed"] = bool(
                end[2] > 45.0
                and record["end_gain_relative_error"] > 0.10
            )
        records.append(record)
    recoverable = [
        record for record in records if record["expected_recoverable"]
    ]
    return {
        "records": records,
        "maximum_recoverable_offset_abs_error_counts": max(
            max(
                record["start_offset_abs_error_counts"],
                record["end_offset_abs_error_counts"],
            )
            for record in recoverable
        ),
        "maximum_recoverable_gain_relative_error": max(
            max(
                record["start_gain_relative_error"],
                record["end_gain_relative_error"],
            )
            for record in recoverable
        ),
        "passed": all(record["passed"] for record in records),
    }


def _classification_checks(oracle, reference):
    expected = {
        "rigid_linear": "supported",
        "rigid_missing": "supported",
        "viscoelastic": "physical_anomaly",
        "rate_change": "physical_anomaly",
        "iq_conjugated": "instrument_fault",
        "clipped": "instrument_fault",
    }
    records = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        for index, spec_value in enumerate(specs):
            world = oracle._make_world(spec_value)
            problem = oracle._public_problem(world)
            submission = oracle._reference_pipeline(problem)
            evaluator_record = next(
                row for row in reference["per_world"]
                if row["split"] == split and row["world_index"] == index
            )
            record = {
                "split": split,
                "world_index": index,
                "seed": int(spec_value[0]),
                "kind": world["kind"],
                "expected_diagnosis": expected[world["kind"]],
                "observed_diagnosis": submission["diagnosis"],
                "observed_abstain": submission["abstain"],
                "joint_quality": evaluator_record["joint_quality"],
                "robust_joint_quality": evaluator_record[
                    "robust_joint_quality"
                ],
                "missing_fraction": evaluator_record["missing_fraction"],
                "saturation_fraction": evaluator_record[
                    "saturation_fraction"
                ],
                "calibration_rms_counts": evaluator_record[
                    "calibration_rms_counts"
                ],
            }
            record["passed"] = bool(
                submission["diagnosis"] == expected[world["kind"]]
                and submission["abstain"]
                == (world["kind"] not in oracle.SUPPORTED_KINDS)
                and evaluator_record["diagnosis_quality"] == 1.0
            )
            records.append(record)
    missing_supported = [
        record for record in records if record["kind"] == "rigid_missing"
    ]
    physical = [
        record for record in records
        if record["kind"] in oracle.PHYSICAL_ANOMALY_KINDS
    ]
    instrument = [
        record for record in records
        if record["kind"] in oracle.INSTRUMENT_FAULT_KINDS
    ]
    return {
        "records": records,
        "missing_supported_recovery_passed": bool(
            missing_supported
            and all(
                record["passed"]
                and not record["observed_abstain"]
                and record["missing_fraction"] > 0.05
                and record["joint_quality"] > 0.98
                for record in missing_supported
            )
        ),
        "physical_anomaly_classification_passed": bool(
            physical
            and all(
                record["passed"]
                and record["observed_diagnosis"] == "physical_anomaly"
                for record in physical
            )
        ),
        "instrument_fault_classification_passed": bool(
            instrument
            and all(
                record["passed"]
                and record["observed_diagnosis"] == "instrument_fault"
                for record in instrument
            )
        ),
        "passed": all(record["passed"] for record in records),
    }


def _robustness_shift_checks(oracle):
    records = []
    for spec_value in oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS:
        world = oracle._make_world(spec_value)
        if world["kind"] not in oracle.SUPPORTED_KINDS:
            continue
        horizon = oracle.PREDICTION_TIME_S
        nominal = oracle._mass_at(world, horizon)
        joint_shift = oracle._robust_mass_at(world, horizon)
        rate_only_world = dict(world)
        rate_only_world["sealed_sauerbrey_scale"] = 1.0
        sensitivity_only_world = dict(world)
        sensitivity_only_world["sealed_rate_scale"] = 1.0
        rate_only = oracle._robust_mass_at(rate_only_world, horizon)
        sensitivity_only = oracle._robust_mass_at(
            sensitivity_only_world, horizon
        )
        last_observed = oracle.DEPOSITION_TIMES_S[-1]
        independent_joint = (
            oracle._mass_at(world, last_observed)
            / world["sealed_sauerbrey_scale"]
            + world["rate"] * world["sealed_rate_scale"]
            / world["sealed_sauerbrey_scale"]
            * (horizon - last_observed)
        )
        record = {
            "seed": int(spec_value[0]),
            "kind": world["kind"],
            "nominal_mass_ug_cm2": nominal,
            "rate_shift_only_mass_ug_cm2": rate_only,
            "sauerbrey_shift_only_mass_ug_cm2": sensitivity_only,
            "joint_shift_mass_ug_cm2": joint_shift,
            "independent_joint_shift_mass_ug_cm2": independent_joint,
            "rate_axis_effect_ug_cm2": abs(joint_shift - sensitivity_only),
            "sauerbrey_axis_effect_ug_cm2": abs(joint_shift - rate_only),
            "joint_formula_abs_gap_ug_cm2": abs(
                joint_shift - independent_joint
            ),
        }
        record["passed"] = bool(
            record["rate_axis_effect_ug_cm2"] > 1.0e-6
            and record["sauerbrey_axis_effect_ug_cm2"] > 1.0e-6
            and record["joint_formula_abs_gap_ug_cm2"] < 1.0e-12
        )
        records.append(record)
    return {
        "records": records,
        "passed": bool(records and all(record["passed"] for record in records)),
    }


def _candidate_source(mode):
    mutation = {
        "valid": "pass",
        "fabricated_evidence": "value['evidence_ids'] = ['fabricated']",
        "incomplete_sweep_map": (
            "value['resonance_frequency_hz_by_sweep'].pop("
            "next(iter(value['resonance_frequency_hz_by_sweep'])))"
        ),
        "nonfinite": (
            "value['mass_loading_ug_cm2'] = float('nan')"
        ),
        "malformed": "value['unexpected'] = True",
    }[mode]
    return textwrap.dedent(
        """
        calls = 0

        def analyze_qcm(problem):
            global calls
            calls += 1
            if MODE == 'valid' and calls != 1:
                raise RuntimeError('candidate process state leaked across worlds')
            sweeps = problem['sweeps']
            nominal = problem['nominal_frequency_hz_by_harmonic']
            value = {
                'calibration': {
                    'start_offset_counts': [0.0, 0.0],
                    'end_offset_counts': [0.0, 0.0],
                    'start_complex_gain_counts_per_siemens': [700000.0, 0.0],
                    'end_complex_gain_counts_per_siemens': [700000.0, 0.0]},
                'resonance_frequency_hz_by_sweep': {
                    row['sweep_id']: nominal[str(row['harmonic'])]
                    for row in sweeps},
                'quality_factor_by_sweep': {
                    row['sweep_id']: 20000.0 for row in sweeps},
                'mass_loading_ug_cm2': 0.0,
                'deposition_rate_ug_cm2_s': 0.0,
                'predicted_mass_ug_cm2': 0.0,
                'additional_deposition_time_s': 0.0,
                'diagnosis': 'undetermined',
                'confidence': 0.0,
                'abstain': True,
                'evidence_ids': [
                    block['calibration_id']
                    for block in problem['calibration_blocks']
                ] + [row['sweep_id'] for row in sweeps]}
            MUTATION
            return value
        """
    ).replace("MODE", repr(mode)).replace("MUTATION", mutation)


def _secure_isolation_and_failure_checks(spec):
    records = []
    with tempfile.TemporaryDirectory(prefix="qcm_calibration_") as temporary:
        root = Path(temporary)
        for mode in (
            "valid", "malformed", "nonfinite", "fabricated_evidence",
            "incomplete_sweep_map",
        ):
            candidate = root / (mode + ".py")
            candidate.write_text(_candidate_source(mode), encoding="utf-8")
            result = evaluate_candidate(spec, candidate, timeout_s=90)
            if mode == "valid":
                passed = bool(
                    result.get("valid") == 1.0
                    and result.get("combined_score") == 0.0
                    and result.get("candidate_instance_call_count") == 10
                    and result.get("candidate_instance_valid_rate") == 1.0
                )
            else:
                passed = bool(
                    result.get("valid") == 0.0
                    and float(result.get("combined_score", 1.0)) <= 0.0
                    and result.get("infrastructure_failure") is None
                )
            records.append({
                "mode": mode,
                "combined_score": result.get("combined_score"),
                "valid": result.get("valid"),
                "candidate_failure_kind": result.get(
                    "candidate_failure_kind"
                ),
                "candidate_instance_call_count": result.get(
                    "candidate_instance_call_count"
                ),
                "candidate_instance_valid_rate": result.get(
                    "candidate_instance_valid_rate"
                ),
                "passed": passed,
            })
    return {
        "records": records,
        "fresh_process_per_world_passed": next(
            record["passed"] for record in records
            if record["mode"] == "valid"
        ),
        "fail_closed_passed": all(
            record["passed"] for record in records
            if record["mode"] != "valid"
        ),
        "passed": all(record["passed"] for record in records),
    }


def calibrate():
    oracle = _load(
        TASK / "verification/evaluator.py", "qcm_raw_calibration_oracle"
    )
    baseline = _load(TASK / "solution.py", "qcm_raw_calibration_baseline")
    spec = find_task(
        "Sensors/QuartzCrystalMicrobalanceLab", include_uncertified=True
    )
    direct_baseline = oracle.evaluate(baseline.analyze_qcm)
    secure_baseline = evaluate_candidate(
        spec, spec.initial_program_path, timeout_s=90
    )
    reference = oracle.evaluate(oracle._reference_agent)
    direct_json = json.loads(json.dumps(direct_baseline, allow_nan=False))
    direct_json["raw_score"] = direct_json["combined_score"]
    visible = search_visible_metrics(secure_baseline)
    resonance_checks = _independent_resonance_checks(oracle)
    calibration_checks = _calibration_recovery_checks(oracle)
    classification_checks = _classification_checks(oracle, reference)
    robustness_checks = _robustness_shift_checks(oracle)
    isolation_checks = _secure_isolation_and_failure_checks(spec)
    truth_rows = [
        oracle._evaluate_truth_world(spec_value, split, index)
        for split, specs in (
            ("development", oracle.DEVELOPMENT_SPECS),
            ("heldout", oracle.HELDOUT_SPECS),
        )
        for index, spec_value in enumerate(specs)
    ]
    execution_passed = bool(
        oracle.QCM_RAW_PIPELINE_V1
        and len(oracle.DEVELOPMENT_SPECS) == 6
        and len(oracle.HELDOUT_SPECS) == 4
        and resonance_checks["passed"]
        and calibration_checks["passed"]
        and classification_checks["passed"]
        and classification_checks["missing_supported_recovery_passed"]
        and classification_checks["physical_anomaly_classification_passed"]
        and classification_checks["instrument_fault_classification_passed"]
        and robustness_checks["passed"]
        and isolation_checks["passed"]
        and secure_baseline == direct_json
        and secure_baseline["valid"] == 1.0
        and secure_baseline["combined_score"] == 0.0
        and secure_baseline["robustness_score"] == 0.0
        and set(visible) == {
            "combined_score", "valid", "feasibility_rate", "raw_score"
        }
        and reference["combined_score"] > 0.98
        and reference["heldout_policy_score"] > 0.98
        and reference["robustness_score"] > 0.80
        and reference["heldout_robustness_score"] > 0.90
        and reference["development_supported_claim_coverage"] == 1.0
        and reference["heldout_supported_claim_coverage"] == 1.0
        and reference["development_unsupported_refusal_rate"] == 1.0
        and reference["heldout_unsupported_refusal_rate"] == 1.0
        and reference["development_fault_diagnosis_accuracy"] == 1.0
        and reference["heldout_fault_diagnosis_accuracy"] == 1.0
        and reference["development_false_discovery_rate"] == 0.0
        and reference["heldout_false_discovery_rate"] == 0.0
        and reference["candidate_instance_call_count"] == 10
        and reference["candidate_instance_valid_rate"] == 1.0
        and all(row["joint_quality"] == 1.0 for row in truth_rows)
    )
    source_paths = (
        TASK / "Task.md",
        TASK / "TASK_CARD.yaml",
        TASK / "solution.py",
        TASK / "verification/evaluator.py",
        TASK / "frontier_eval/metadata.yaml",
        TASK / "frontier_eval/run_eval.py",
        Path(__file__).resolve(),
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "SYNTHETIC_REDUCED_ORDER_QCM_RAW_IQ_PIPELINE_CALIBRATION_NOT_"
            "PHYSICAL_INSTRUMENT_FILM_MATERIAL_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {
            "python": sys.version,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "task": "Sensors/QuartzCrystalMicrobalanceLab",
        "task_source_sha256": {
            str(path.relative_to(ROOT)): _sha256(path) for path in source_paths
        },
        "task_dimensions": {
            "development_world_count": len(oracle.DEVELOPMENT_SPECS),
            "heldout_world_count": len(oracle.HELDOUT_SPECS),
            "harmonic_count": len(oracle.HARMONICS),
            "deposition_time_count": len(oracle.DEPOSITION_TIMES_S),
            "sweep_count_per_world": (
                len(oracle.HARMONICS) * len(oracle.DEPOSITION_TIMES_S)
            ),
            "supported_world_count": sum(
                spec_value[1] in oracle.SUPPORTED_KINDS
                for spec_value in (
                    oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS
                )
            ),
            "physical_anomaly_world_count": sum(
                spec_value[1] in oracle.PHYSICAL_ANOMALY_KINDS
                for spec_value in (
                    oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS
                )
            ),
            "instrument_fault_world_count": sum(
                spec_value[1] in oracle.INSTRUMENT_FAULT_KINDS
                for spec_value in (
                    oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS
                )
            ),
        },
        "independent_resonance_checks": resonance_checks,
        "complex_affine_calibration_checks": calibration_checks,
        "classification_and_missingness_checks": classification_checks,
        "sealed_robustness_shift_checks": robustness_checks,
        "secure_isolation_and_failure_checks": isolation_checks,
        "direct_weak_baseline": direct_baseline,
        "secure_weak_baseline": secure_baseline,
        "secure_baseline_exactly_matches_direct": secure_baseline == direct_json,
        "truth_blind_reference": reference,
        "truth_reference_records": truth_rows,
        "search_visible_metric_keys": sorted(visible),
        "limitations": [
            "This is a deterministic synthetic reduced-order QCM and electronics model, not a physical instrument or deposition experiment.",
            "The model omits temperature drift, electrode roughness, fluid loading, distributed films, nonlinear electronics and closed-loop actuator hazards.",
            "The two-point linear complex-drift family is narrower than calibration behavior in real QCM electronics.",
            "Fixed public equations and repository-visible worlds require server-held traces and contamination auditing.",
            "The reference preprocessing policy is a reproducible calibration witness, not a globally optimal estimator or a discovered material law.",
            "Instrument, film and discovery claims require independent sensing/thin-film review, real raw traces and prospective physical replication.",
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
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "execution_passed": report["execution_passed"],
        "trust_decision": report["trust_decision"],
        "reference_development": report["truth_blind_reference"][
            "combined_score"
        ],
        "reference_heldout": report["truth_blind_reference"][
            "heldout_policy_score"
        ],
        "reference_robustness": report["truth_blind_reference"][
            "robustness_score"
        ],
    }, indent=2))
    print("Report: %s" % args.output.resolve())
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
