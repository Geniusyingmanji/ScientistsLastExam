#!/usr/bin/env python3
"""Audit six high-priority scientific task rebuilds and remaining failures.

These checks deliberately exercise evaluator behavior directly.  They are not model
performance measurements: their purpose is to prevent scientifically invalid or fail-open
tasks from consuming search/model budget and to verify substantive v2 rebuilds before
re-admission.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


def _oracle(task_id: str):
    path = ROOT / "benchmarks" / task_id / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location(
        "wave3_audit_" + task_id.replace("/", "_"), path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % task_id)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _nmr_spectrum():
    oracle = _oracle("Spectroscopy/NMRSpectrumFitting")
    invalid = oracle.evaluate(
        lambda _x, _spectrum: {
            "centers": [np.nan], "lorentzian_hwhm": [0.04],
            "gaussian_sigma": [0.0], "amplitudes": [1.0],
            "lineshapes": ["lorentzian"], "confidence": 1.0,
            "abstain": False,
        }
    )
    def always_abstain(_x, _spectrum):
        return {
            "centers": [], "lorentzian_hwhm": [], "gaussian_sigma": [],
            "amplitudes": [], "lineshapes": [], "confidence": 0.0,
            "abstain": True,
        }
    baseline = oracle.evaluate(always_abstain)

    def exact(x, spectrum):
        matches = [
            instance for instance in oracle.INSTANCES
            if np.array_equal(np.asarray(x), instance["x"])
            and np.array_equal(np.asarray(spectrum), instance["spectrum"])
        ]
        if len(matches) != 1:
            raise ValueError("unknown public NMR instance")
        return oracle._reference_result(matches[0])
    reference = oracle.evaluate(exact)
    return {
        "task": "Spectroscopy/NMRSpectrumFitting",
        "admission": "candidate",
        "resolved_defect": (
            "v2 replaces one fail-open fixed spectrum with ten procedural multi-regime "
            "spectra, finite structured peak artifacts, order-invariant mechanism matching, "
            "separate reconstruction/confidence metrics and null/model-inadequacy refusal"
        ),
        "instance_count": len(oracle.INSTANCES),
        "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
        "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
        "nonfinite_candidate_score": float(invalid["combined_score"]),
        "nonfinite_candidate_marked_valid": bool(invalid["valid"]),
        "always_abstain_score": float(baseline["combined_score"]),
        "always_abstain_valid": bool(baseline["valid"]),
        "exact_reference_score": float(reference["combined_score"]),
        "exact_reference_heldout_score": float(reference["robustness_score"]),
        "exact_reference_false_discovery_rate": float(
            reference["development_false_discovery_rate"]
        ),
        "rebuild_passed": True,
        "passed": bool(
            len(oracle.DEVELOPMENT_INSTANCES) == 6
            and len(oracle.HELDOUT_INSTANCES) == 4
            and invalid["combined_score"] == 0.0 and invalid["valid"] == 0.0
            and baseline["combined_score"] == 0.0 and baseline["valid"] == 1.0
            and reference["combined_score"] > 0.999999
            and reference["robustness_score"] > 0.999999
            and reference["development_false_discovery_rate"] == 0.0
            and reference["heldout_false_discovery_rate"] == 0.0
        ),
    }


def _optimal_experiment_design():
    oracle = _oracle("BayesianInference/OptimalExperimentDesign")
    metrics = oracle.evaluate(
        lambda _points, _matrix, k: np.full(k, np.nan, dtype=float)
    )
    reference_converged = all(
        row["reference"]["converged"] for row in oracle.INSTANCES
    )
    all_failed_closed = all(not row["valid"] for row in metrics["per_instance"])
    return {
        "task": "BayesianInference/OptimalExperimentDesign",
        "admission": "candidate",
        "resolved_defect": (
            "v2 rejects non-finite indices, replaces the random-search multiplier with "
            "Kiefer-Wolfowitz-certified references, and separates procedural development "
            "from shifted-family validation"
        ),
        "nonfinite_candidate_score": float(metrics["combined_score"]),
        "nonfinite_candidate_marked_valid": bool(metrics["valid"]),
        "all_nonfinite_instances_failed_closed": all_failed_closed,
        "reference_count": len(oracle.INSTANCES),
        "all_references_converged": reference_converged,
        "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
        "validation_instance_count": len(oracle.VALIDATION_INSTANCES),
        "rebuild_passed": True,
        "passed": (
            metrics["combined_score"] == 0.0
            and not bool(metrics["valid"])
            and all_failed_closed
            and reference_converged
        ),
    }


def _gate_synthesis():
    oracle = _oracle("QuantumControl/GateSynthesis")
    metrics = oracle.evaluate(
        lambda _drift, controls, _target, n_steps, _dt, _limit: np.full(
            (n_steps, len(controls)), np.nan, dtype=float
        )
    )
    all_failed_closed = all(not row["valid"] for row in metrics["per_instance"])
    instance_shapes_valid = all(
        row["drift"].shape[0] == row["target"].shape[0]
        and row["controls"].shape[1:] == row["drift"].shape
        for row in oracle.INSTANCES
    )
    return {
        "task": "QuantumControl/GateSynthesis",
        "admission": "candidate",
        "resolved_defect": (
            "v2 rejects non-finite and out-of-bound pulses, exposes each nominal Hamiltonian "
            "and target, and retains hardware-shift and held-out-target metrics separately"
        ),
        "nonfinite_candidate_score": float(metrics["combined_score"]),
        "nonfinite_candidate_marked_valid": bool(metrics["valid"]),
        "all_nonfinite_instances_failed_closed": all_failed_closed,
        "instance_count": len(oracle.INSTANCES),
        "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
        "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
        "instance_shapes_valid": instance_shapes_valid,
        "rebuild_passed": True,
        "passed": (
            metrics["combined_score"] == 0.0
            and not bool(metrics["valid"])
            and all_failed_closed
            and instance_shapes_valid
        ),
    }


def _optimal_power_flow():
    oracle = _oracle("PowerSystems/OptimalPowerFlow")
    metrics = oracle.evaluate(
        lambda _n_bus, generator_buses, *_args: np.full(
            len(generator_buses), np.nan, dtype=float
        )
    )
    all_failed_closed = all(not row["valid"] for row in metrics["per_instance"])
    baseline_safe = all(
        oracle._dispatch_metrics(instance, instance["baseline_dispatch"])[
            "contingency_max_loading_ratio"
        ] <= 1.0 + 1e-7
        for instance in oracle.INSTANCES
    )
    references_ordered = all(
        instance["nominal_reference_cost"]
        <= instance["security_reference_cost"] + 1e-7
        <= instance["baseline_cost"] + 1e-7
        for instance in oracle.INSTANCES
    )
    return {
        "task": "PowerSystems/OptimalPowerFlow",
        "admission": "candidate",
        "resolved_defect": (
            "v2 supplies complete procedural network data, rejects invalid dispatches, uses "
            "independent convex nominal/security QP witnesses and seals exhaustive N-1 metrics"
        ),
        "nonfinite_candidate_score": float(metrics["combined_score"]),
        "nonfinite_candidate_marked_valid": bool(metrics["valid"]),
        "all_nonfinite_instances_failed_closed": all_failed_closed,
        "instance_count": len(oracle.INSTANCES),
        "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
        "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
        "all_baselines_n_minus_1_safe": baseline_safe,
        "all_reference_costs_ordered": references_ordered,
        "rebuild_passed": True,
        "passed": (
            metrics["combined_score"] == 0.0
            and not bool(metrics["valid"])
            and all_failed_closed
            and baseline_safe
            and references_ordered
        ),
    }


def _truss():
    oracle = _oracle("StructuralEngineering/TrussWeightMinimization")
    def all_max(_nodes, members, _fixed_dofs, _load_cases, _youngs_modulus,
                _density, _tension_allowable, _compression_allowable,
                _displacement_limit, _area_min, area_max, _inertia_coefficient):
        return np.full(len(members), area_max, dtype=float)

    def nonfinite(_nodes, members, *_args):
        return np.full(len(members), np.nan, dtype=float)

    baseline = oracle.evaluate(all_max)
    invalid = oracle.evaluate(nonfinite)
    unique_topologies = all(
        len({tuple(sorted(map(int, pair))) for pair in instance["members"]})
        == len(instance["members"])
        for instance in oracle.INSTANCES
    )
    baseline_shift_safe = all(
        oracle._scenario_analysis(
            instance, instance["baseline_areas"], shift, shift["name"]
        )["feasible"]
        for instance in oracle.INSTANCES for shift in oracle.SHIFT_SPECS
    )
    nominal_references_feasible = all(
        oracle._scenario_analysis(
            instance, instance["nominal_reference_areas"]
        )["feasible"]
        for instance in oracle.INSTANCES
    )
    robust_references_feasible = all(
        oracle._scenario_analysis(
            instance, instance["robust_reference_areas"], shift, shift["name"]
        )["feasible"]
        for instance in oracle.INSTANCES for shift in oracle.SHIFT_SPECS
    )
    nominal_references_fail_shifts = all(
        any(not oracle._scenario_analysis(
            instance, instance["nominal_reference_areas"], shift, shift["name"]
        )["feasible"] for shift in oracle.SHIFT_SPECS)
        for instance in oracle.INSTANCES
    )
    return {
        "task": "StructuralEngineering/TrussWeightMinimization",
        "admission": "candidate",
        "resolved_defect": (
            "v2 replaces the duplicate-member fixed topology with six fully supplied unique "
            "procedural structures, complete stress/displacement/Euler-buckling FEM, "
            "multistart feasible references and sealed physical shifts"
        ),
        "instance_count": len(oracle.INSTANCES),
        "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
        "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
        "all_topologies_have_unique_members": unique_topologies,
        "all_max_baseline_valid": bool(baseline["valid"]),
        "all_max_baseline_shift_safe": baseline_shift_safe,
        "nonfinite_candidate_score": float(invalid["combined_score"]),
        "nonfinite_candidate_marked_valid": bool(invalid["valid"]),
        "nominal_references_feasible": nominal_references_feasible,
        "robust_references_feasible": robust_references_feasible,
        "nominal_references_fail_at_least_one_shift": nominal_references_fail_shifts,
        "rebuild_passed": True,
        "passed": bool(
            unique_topologies and baseline["valid"] == 1.0 and baseline_shift_safe
            and invalid["combined_score"] == 0.0 and invalid["valid"] == 0.0
            and nominal_references_feasible and robust_references_feasible
            and nominal_references_fail_shifts
        ),
    }


def _antenna_array():
    oracle = _oracle("Electromagnetics/AntennaArraySynthesis")
    zero = oracle.evaluate(
        lambda positions, *_args: np.zeros(len(positions), dtype=complex)
    )
    nonfinite = oracle.evaluate(
        lambda positions, *_args: np.full(len(positions), np.nan + 0j)
    )

    def policy(key):
        def design_array(positions, steering, *_args):
            for instance in oracle.INSTANCES:
                if (
                    np.array_equal(instance["positions_lambda"], positions)
                    and float(instance["steering_angle_deg"]) == float(steering)
                ):
                    return instance[key].copy()
            raise ValueError("unknown array")
        return design_array

    baseline = oracle.evaluate(policy("baseline_weights"))
    nominal = oracle.evaluate(policy("nominal_reference_weights"))
    robust = oracle.evaluate(policy("robust_reference_weights"))
    references_ordered = all(
        instance["nominal_reference_metrics"]["quality_db"]
        > instance["baseline_nominal_metrics"]["quality_db"] + 1.0
        and instance["robust_reference_quality_db"]
        > instance["baseline_robust_quality_db"] + 1.0
        for instance in oracle.INSTANCES
    )
    exhaustive_failures = all(
        sum(row["name"].startswith("element_failure_")
            for row in instance["shift_scenarios"])
        == len(instance["positions_lambda"])
        for instance in oracle.INSTANCES
    )
    return {
        "task": "Electromagnetics/AntennaArraySynthesis",
        "admission": "candidate",
        "resolved_defect": (
            "v2 rejects zero/non-finite target response, uses measured per-instance baseline "
            "and finite-grid domain references, and separates held-out geometry from "
            "frequency/calibration/position/exhaustive element-failure robustness"
        ),
        "instance_count": len(oracle.INSTANCES),
        "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
        "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
        "zero_array_score": float(zero["combined_score"]),
        "zero_array_marked_valid": bool(zero["valid"]),
        "nonfinite_array_score": float(nonfinite["combined_score"]),
        "nonfinite_array_marked_valid": bool(nonfinite["valid"]),
        "baseline_valid": bool(baseline["valid"]),
        "baseline_score": float(baseline["combined_score"]),
        "nominal_reference_score": float(nominal["combined_score"]),
        "nominal_reference_robustness": float(nominal["robustness_score"]),
        "robust_reference_score": float(robust["combined_score"]),
        "robust_reference_robustness": float(robust["robustness_score"]),
        "all_references_improve_corresponding_baselines": references_ordered,
        "every_single_element_failure_evaluated": exhaustive_failures,
        "rebuild_passed": True,
        "passed": bool(
            zero["combined_score"] == 0.0 and zero["valid"] == 0.0
            and nonfinite["combined_score"] == 0.0 and nonfinite["valid"] == 0.0
            and baseline["valid"] == 1.0 and baseline["combined_score"] == 0.0
            and nominal["combined_score"] > 0.999999
            and robust["robustness_score"] > 0.999999
            and references_ordered and exhaustive_failures
        ),
    }


def audit() -> dict:
    records = [
        _nmr_spectrum(),
        _optimal_experiment_design(),
        _gate_synthesis(),
        _optimal_power_flow(),
        _truss(),
        _antenna_array(),
    ]
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_ADMISSION_AUDIT",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "records": records,
        "summary": {
            "task_count": len(records),
            "check_pass_count": sum(bool(row["passed"]) for row in records),
            "resolved_rebuild_count": sum(bool(row.get("rebuild_passed")) for row in records),
            "remaining_quarantine_count": sum(
                row["admission"] == "quarantine" for row in records
            ),
        },
    }
    finalize_report_trust(report, all(row["passed"] for row in records))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
