#!/usr/bin/env python3
"""Calibrate HartreeFockSCF-v2 references, invariants and difficulty.

PySCF is used only by the separate offline data-generation utility.  This calibration
recomputes the production equations with an independent NumPy/SciPy implementation and
binds the frozen archive hash, conventional baseline, stable witnesses, physical shifts,
representation checks and fail-closed behavior into one provenance-aware report.
"""

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
TASK = ROOT / "benchmarks/QuantumChemistry/HartreeFockSCF"
DATA_PATH = TASK / "verification/rhf_instances_v2.npz"
sys.path.insert(0, str(ROOT))

from frontier_science.metric_visibility import search_visible_metrics  # noqa: E402
from frontier_science.evaluate import evaluate_candidate  # noqa: E402
from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)
from frontier_science.registry import find_task  # noqa: E402


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _independent_matrix_power(matrix, exponent):
    values, vectors = np.linalg.eigh(np.asarray(matrix, dtype=float))
    if float(np.min(values)) <= 1.0e-10:
        raise ValueError("non-positive overlap")
    return (vectors * values ** exponent) @ vectors.T


def _independent_diagnostics(problem, coefficients):
    overlap = np.asarray(problem["overlap"], dtype=float)
    core = np.asarray(problem["core_hamiltonian"], dtype=float)
    eri = np.asarray(problem["electron_repulsion_integrals"], dtype=float)
    coefficients = np.asarray(coefficients, dtype=float)
    density = 2.0 * coefficients @ coefficients.T
    coulomb = np.einsum("rs,pqrs->pq", density, eri, optimize=True)
    exchange = np.einsum("rs,prqs->pq", density, eri, optimize=True)
    fock = core + coulomb - 0.5 * exchange
    energy = float(
        0.5 * np.sum(density * (core + fock))
        + float(problem["nuclear_repulsion"])
    )
    square_root = _independent_matrix_power(overlap, 0.5)
    density_orthogonal = square_root @ density @ square_root
    commutator = fock @ density @ overlap - overlap @ density @ fock
    commutator_scale = max(
        np.linalg.norm(fock) * np.linalg.norm(density) * np.linalg.norm(overlap),
        1.0e-15,
    )
    occupied = coefficients.shape[1]
    return {
        "energy_hartree": energy,
        "overlap_orthonormality_error": float(np.linalg.norm(
            coefficients.T @ overlap @ coefficients - np.eye(occupied)
        )),
        "electron_count_error": float(abs(
            np.trace(density @ overlap) - 2.0 * occupied
        )),
        "density_idempotency_error": float(np.linalg.norm(
            density_orthogonal @ density_orthogonal
            - 2.0 * density_orthogonal
        )),
        "scf_residual": float(np.linalg.norm(commutator) / commutator_scale),
    }


def _compact(metrics):
    keys = (
        "combined_score", "valid", "feasibility_rate", "raw_score",
        "robustness_score", "heldout_policy_score",
        "heldout_robustness_score", "heldout_feasibility_rate",
        "development_shifted_score", "heldout_shifted_score",
        "development_representation_invariance_score",
        "heldout_representation_invariance_score",
        "development_stability_rate", "heldout_stability_rate",
        "development_mean_energy_error_hartree",
        "heldout_mean_energy_error_hartree",
        "development_maximum_scf_residual",
        "heldout_maximum_scf_residual",
        "candidate_problem_call_count", "candidate_instance_valid_rate",
        "error_message",
    )
    return {key: metrics[key] for key in keys if key in metrics}


def _invalid_checks(oracle, baseline):
    def nominal(problem):
        return baseline.solve_restricted_hf(problem)

    factories = {
        "wrong_shape": lambda problem: np.zeros((
            len(problem["overlap"]),
            int(problem["occupied_orbital_count"]) + 1,
        )),
        "nonfinite": lambda problem: np.full((
            len(problem["overlap"]),
            int(problem["occupied_orbital_count"]),
        ), np.nan),
        "complex": lambda problem: (
            nominal(problem).astype(complex) + 1.0e-3j
        ),
        "nonorthonormal": lambda problem: 1.01 * nominal(problem),
        "nonstationary": lambda problem: oracle._core_guess(problem),
    }
    return {
        name: _compact(oracle.evaluate(factory))
        for name, factory in factories.items()
    }


def calibrate():
    oracle = _load(
        TASK / "verification/evaluator.py", "hartree_fock_v2_calibration_oracle"
    )
    baseline_module = _load(
        TASK / "solution.py", "hartree_fock_v2_calibration_baseline"
    )
    baseline = oracle.evaluate(baseline_module.solve_restricted_hf)
    baseline_replay = oracle.evaluate(baseline_module.solve_restricted_hf)
    secure_baseline = evaluate_candidate(
        find_task(
            "QuantumChemistry/HartreeFockSCF", include_uncertified=True
        ),
        TASK / "solution.py",
        timeout_s=60,
    )
    reference = oracle.evaluate(oracle.reference_policy)
    reference_replay = oracle.evaluate(oracle.reference_policy)

    independent = []
    maximum_energy_error = 0.0
    maximum_orthonormality_error = 0.0
    maximum_electron_error = 0.0
    maximum_idempotency_error = 0.0
    maximum_residual = 0.0
    for instance in oracle.INSTANCES:
        conditions = (
            ("nominal", False, instance["reference_coefficients"],
             instance["reference_energy"]),
            ("geometry_shift", True, instance["shifted_reference_coefficients"],
             instance["shifted_reference_energy"]),
        )
        rows = []
        for label, shifted, coefficients, expected_energy in conditions:
            problem = oracle._public_problem(instance, shifted=shifted)
            diagnostics = _independent_diagnostics(problem, coefficients)
            energy_error = abs(
                diagnostics["energy_hartree"] - float(expected_energy)
            )
            maximum_energy_error = max(maximum_energy_error, energy_error)
            maximum_orthonormality_error = max(
                maximum_orthonormality_error,
                diagnostics["overlap_orthonormality_error"],
            )
            maximum_electron_error = max(
                maximum_electron_error, diagnostics["electron_count_error"]
            )
            maximum_idempotency_error = max(
                maximum_idempotency_error,
                diagnostics["density_idempotency_error"],
            )
            maximum_residual = max(
                maximum_residual, diagnostics["scf_residual"]
            )
            rows.append({
                "condition": label,
                "stored_energy_hartree": float(expected_energy),
                "energy_error_hartree": energy_error,
                **diagnostics,
            })
        independent.append({
            "name": instance["name"],
            "split": instance["split"],
            "basis": instance["basis"],
            "ao_count": int(instance["ao_count"]),
            "electron_count": int(instance["electron_count"]),
            "conditions": rows,
        })

    invalid = _invalid_checks(oracle, baseline_module)
    deterministic = bool(
        json.dumps(baseline, sort_keys=True, allow_nan=False)
        == json.dumps(baseline_replay, sort_keys=True, allow_nan=False)
        and json.dumps(reference, sort_keys=True, allow_nan=False)
        == json.dumps(reference_replay, sort_keys=True, allow_nan=False)
    )
    visible = search_visible_metrics(reference)
    sealed_keys = (
        "robustness_score", "heldout_policy_score",
        "heldout_robustness_score", "development_shifted_score",
        "development_representation_invariance_score",
        "development_stability_rate", "per_instance",
    )
    metric_sealing_passed = all(key not in visible for key in sealed_keys)

    baseline_rows = {row["name"]: row for row in baseline["per_instance"]}
    reference_rows = {row["name"]: row for row in reference["per_instance"]}
    hard_development = baseline_rows[
        "dev_h8_ring_symmetry_breaking_sto3g"
    ]
    hard_heldout = baseline_rows[
        "heldout_h4_ring_symmetry_breaking_sto3g"
    ]
    difficulty_passed = bool(
        baseline["valid"] == 1.0
        and baseline["combined_score"] == 0.0
        and baseline["robustness_score"] == 0.0
        and baseline["development_stability_rate"] == 0.75
        and baseline["heldout_stability_rate"] < 1.0
        and hard_development["minimum_stability_curvature"] < -0.20
        and hard_heldout["minimum_stability_curvature"] < -0.20
        and reference["combined_score"] > 0.999
        and reference["robustness_score"] > 0.999
        and reference["heldout_policy_score"] > 0.99
        and reference["heldout_robustness_score"] > 0.99
        and reference["development_stability_rate"] == 1.0
        and reference["heldout_stability_rate"] == 1.0
        and reference_rows["dev_h8_ring_symmetry_breaking_sto3g"][
            "minimum_stability_curvature"
        ] > 0.20
        and reference_rows["heldout_h4_ring_symmetry_breaking_sto3g"][
            "minimum_stability_curvature"
        ] > 0.05
    )
    independent_passed = bool(
        maximum_energy_error <= 2.0e-10
        and maximum_orthonormality_error <= 2.0e-8
        and maximum_electron_error <= 2.0e-8
        and maximum_idempotency_error <= 2.0e-8
        and maximum_residual <= 5.0e-8
    )
    invalid_passed = all(
        row.get("combined_score") == 0.0
        and row.get("valid") == 0.0
        for row in invalid.values()
    )
    archive_sha256 = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()
    archive_passed = archive_sha256 == (
        "230fa7bf2ee359dcdcc9f06e62629f5f827d14f5331e5359dd8903f8e21d7bd5"
    )
    passed = bool(
        oracle.HARTREE_FOCK_V2
        and len(oracle.DEVELOPMENT_INSTANCES) == 4
        and len(oracle.HELDOUT_INSTANCES) == 3
        and deterministic
        and archive_passed
        and independent_passed
        and difficulty_passed
        and invalid_passed
        and metric_sealing_passed
        and baseline["candidate_problem_call_count"] == 28
        and reference["candidate_problem_call_count"] == 28
        and secure_baseline["valid"] == 1.0
        and secure_baseline["combined_score"] == 0.0
        and secure_baseline["candidate_problem_call_count"] == 28
        and abs(
            secure_baseline["raw_score"] - baseline["raw_score"]
        ) <= 1.0e-7
    )
    return {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "task": "QuantumChemistry/HartreeFockSCF",
        "dataset_sha256": archive_sha256,
        "dataset_manifest": oracle.DATA_MANIFEST,
        "baseline": _compact(baseline),
        "secure_sandbox_baseline": _compact(secure_baseline),
        "reference": _compact(reference),
        "hard_cases": {
            "development_baseline": {
                key: hard_development[key] for key in (
                    "score", "energy_hartree", "reference_energy_hartree",
                    "energy_error_hartree", "minimum_stability_curvature",
                    "internally_stable", "robustness_score",
                )
            },
            "heldout_baseline": {
                key: hard_heldout[key] for key in (
                    "score", "energy_hartree", "reference_energy_hartree",
                    "energy_error_hartree", "minimum_stability_curvature",
                    "internally_stable", "robustness_score",
                )
            },
        },
        "independent_reference_checks": independent,
        "independent_maximum_energy_error_hartree": maximum_energy_error,
        "independent_maximum_overlap_orthonormality_error": (
            maximum_orthonormality_error
        ),
        "independent_maximum_electron_count_error": maximum_electron_error,
        "independent_maximum_density_idempotency_error": (
            maximum_idempotency_error
        ),
        "independent_maximum_scf_residual": maximum_residual,
        "invalid_artifact_checks": invalid,
        "deterministic": deterministic,
        "archive_hash_passed": archive_passed,
        "independent_equations_passed": independent_passed,
        "difficulty_passed": difficulty_passed,
        "invalid_artifacts_passed": invalid_passed,
        "metric_sealing_passed": metric_sealing_passed,
        "passed": passed,
        "limitations": [
            "The frozen references are internally stable finite-basis RHF witnesses, not proofs of the global determinant minimum or correlated exact energies.",
            "The seven public small systems permit matrix-specific branching; future release work requires server-held procedural molecules, geometries and basis families.",
            "Only internal real-RHF stability is scored; external unrestricted instabilities, basis-set convergence and correlated-method accuracy remain outside scope.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = calibrate()
    execution_passed = bool(report.pop("passed"))
    report.update({
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "source_provenance": source_provenance(ROOT),
    })
    finalize_report_trust(report, execution_passed)
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if execution_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
