#!/usr/bin/env python3
"""Reproduce admission failures in six high-priority candidate tasks.

These checks deliberately exercise evaluator behavior directly.  They are not model
performance measurements: their purpose is to prevent scientifically invalid or fail-open
tasks from consuming search/model budget before the task family is rebuilt.
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
    metrics = oracle.evaluate(
        lambda _x, _spectrum: {
            "centers": [np.nan], "widths": [np.nan], "amplitudes": [np.nan]
        }
    )
    residual_is_finite = bool(np.isfinite(metrics["residual_rms"]))
    return {
        "task": "Spectroscopy/NMRSpectrumFitting",
        "admission": "quarantine",
        "defect": (
            "non-finite peak parameters pass validation and receive full score; the fixed "
            "single spectrum also scores reconstruction only, not peak/mechanism recovery"
        ),
        "nonfinite_candidate_score": float(metrics["combined_score"]),
        "nonfinite_candidate_marked_valid": bool(metrics["valid"]),
        "reported_residual_is_finite": residual_is_finite,
        "instance_count": 1,
        "passed": (
            metrics["combined_score"] == 1.0
            and bool(metrics["valid"])
            and not residual_is_finite
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
        lambda _n_bus, n_gen, *_args: np.full(n_gen, np.nan, dtype=float)
    )
    finite_cost = bool(np.isfinite(metrics["cost"]))
    finite_violation = bool(np.isfinite(metrics["line_violations_mw"]))
    equal = oracle.evaluate(
        lambda _n_bus, n_gen, demand, *_args: np.full(
            n_gen, sum(demand) / n_gen, dtype=float
        )
    )
    return {
        "task": "PowerSystems/OptimalPowerFlow",
        "admission": "quarantine",
        "defect": (
            "non-finite dispatch passes all balance/flow checks and receives full score; the "
            "candidate interface omits line susceptances and generator-bus assignments, while "
            "the declared baseline is itself line-infeasible"
        ),
        "nonfinite_candidate_score": float(metrics["combined_score"]),
        "nonfinite_candidate_marked_valid": bool(metrics["valid"]),
        "reported_cost_is_finite": finite_cost,
        "reported_violation_is_finite": finite_violation,
        "equal_dispatch_feasibility_rate": float(equal["feasibility_rate"]),
        "equal_dispatch_line_violation_mw": float(equal["line_violations_mw"]),
        "passed": (
            metrics["combined_score"] == 1.0
            and bool(metrics["valid"])
            and not finite_cost
            and not finite_violation
            and equal["feasibility_rate"] == 0.0
        ),
    }


def _truss():
    oracle = _oracle("StructuralEngineering/TrussWeightMinimization")
    undirected = [tuple(sorted(map(int, pair))) for pair in oracle.ELEMENTS]
    unique = sorted(set(undirected))
    duplicates = sorted({pair for pair in undirected if undirected.count(pair) > 1})
    baseline = oracle.evaluate(lambda n_bars: np.full(n_bars, oracle.A_MAX))
    return {
        "task": "StructuralEngineering/TrussWeightMinimization",
        "admission": "quarantine",
        "defect": (
            "the purported canonical 10-bar topology contains the same middle vertical "
            "member twice, so its FEM and cited 5060-lb reference describe different problems"
        ),
        "declared_member_count": int(len(oracle.ELEMENTS)),
        "unique_undirected_member_count": int(len(unique)),
        "duplicated_undirected_members": [list(pair) for pair in duplicates],
        "all_max_baseline_weight_lbs": float(baseline["weight_lbs"]),
        "passed": len(oracle.ELEMENTS) == 10 and len(unique) == 9 and bool(duplicates),
    }


def _antenna_array():
    oracle = _oracle("Electromagnetics/AntennaArraySynthesis")
    zero = oracle.evaluate(
        lambda n_elements, _spacing, _width: np.zeros(n_elements, dtype=complex)
    )
    uniform = oracle.evaluate(
        lambda n_elements, _spacing, _width: np.ones(n_elements, dtype=complex)
    )
    finite_zero_psll = [
        bool(np.isfinite(row["psll_dB"])) for row in zero["per_instance"]
    ]
    measured_uniform = [float(row["psll_dB"]) for row in uniform["per_instance"]]
    declared_uniform = [float(row["psll_baseline"]) for row in oracle.INSTANCES]
    mismatch = [abs(a - b) for a, b in zip(measured_uniform, declared_uniform)]
    return {
        "task": "Electromagnetics/AntennaArraySynthesis",
        "admission": "quarantine",
        "defect": (
            "the zero array normalizes 0/0 and receives full score; additionally the fixed "
            "mainlobe mask measures the uniform arrays near -9 dB while normalization claims "
            "-13.3 dB, so the score and stated beam constraint are inconsistent"
        ),
        "zero_array_score": float(zero["combined_score"]),
        "zero_array_marked_valid": bool(zero["valid"]),
        "zero_array_psll_is_finite": finite_zero_psll,
        "measured_uniform_psll_db": measured_uniform,
        "declared_uniform_psll_db": declared_uniform,
        "absolute_baseline_mismatch_db": mismatch,
        "passed": (
            zero["combined_score"] == 1.0
            and bool(zero["valid"])
            and not any(finite_zero_psll)
            and all(delta > 3.0 for delta in mismatch)
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
