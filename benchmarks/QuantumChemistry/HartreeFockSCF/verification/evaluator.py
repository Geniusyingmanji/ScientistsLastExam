"""Multi-system restricted Hartree--Fock self-consistent-field oracle, version 2.

Candidates return occupied spatial-orbital coefficients for public finite-basis AO
Hamiltonians.  The trusted oracle reconstructs the density, Fock matrix, electronic
energy and Roothaan--Hall residual.  Nominal development utility controls search;
held-out molecules, physically regenerated nearby geometries, representation changes
and occupied--virtual stability diagnostics remain sealed.

The frozen references are fixed-seed, internally stable, multistart finite-basis RHF
witnesses cross-checked against an independent NumPy/SciPy SCF implementation.  They
are not exact correlated energies or proofs of the global HF minimum.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy.linalg import expm


HARTREE_FOCK_V2 = True
DATA_PATH = Path(__file__).resolve().with_name("rhf_instances_v2.npz")
ORTHONORMALITY_TOLERANCE = 2.0e-6
ELECTRON_COUNT_TOLERANCE = 2.0e-6
IDEMPOTENCY_TOLERANCE = 2.0e-6
SCF_RESIDUAL_TOLERANCE = 2.0e-6
STABILITY_STEP = 3.0e-3
STABILITY_TOLERANCE = -2.0e-4
# Mean nominal utility of the public conventional single-core-guess DIIS policy.
# The aggregate task score measures improvement above this reproducible policy,
# while per-instance raw utilities retain the physical energy normalization.
BASELINE_DEVELOPMENT_RAW_SCORE = 0.7544181838180334
BASELINE_DEVELOPMENT_ROBUSTNESS_SCORE = 0.75


def _load_instances():
    with np.load(DATA_PATH, allow_pickle=False) as archive:
        manifest = json.loads(str(archive["manifest_json"].item()))
        records = []
        for metadata in manifest["cases"]:
            prefix = "case_%d_" % int(metadata["index"])
            records.append(
                {
                    **metadata,
                    "overlap": archive[prefix + "overlap"].copy(),
                    "core_hamiltonian": archive[
                        prefix + "core_hamiltonian"
                    ].copy(),
                    "eri": archive[prefix + "eri"].copy(),
                    "nuclear_repulsion": float(
                        archive[prefix + "nuclear_repulsion"]
                    ),
                    "nuclear_charges": archive[
                        prefix + "nuclear_charges"
                    ].copy(),
                    "coordinates_angstrom": archive[
                        prefix + "coordinates_angstrom"
                    ].copy(),
                    "reference_coefficients": archive[
                        prefix + "reference_coefficients"
                    ].copy(),
                    "reference_energy": float(
                        archive[prefix + "reference_energy"]
                    ),
                    "shifted_overlap": archive[
                        prefix + "shifted_overlap"
                    ].copy(),
                    "shifted_core_hamiltonian": archive[
                        prefix + "shifted_core_hamiltonian"
                    ].copy(),
                    "shifted_eri": archive[prefix + "shifted_eri"].copy(),
                    "shifted_nuclear_repulsion": float(
                        archive[prefix + "shifted_nuclear_repulsion"]
                    ),
                    "shifted_coordinates_angstrom": archive[
                        prefix + "shifted_coordinates_angstrom"
                    ].copy(),
                    "shifted_reference_coefficients": archive[
                        prefix + "shifted_reference_coefficients"
                    ].copy(),
                    "shifted_reference_energy": float(
                        archive[prefix + "shifted_reference_energy"]
                    ),
                    "permutation_transform": archive[
                        prefix + "permutation_transform"
                    ].copy(),
                    "dense_transform": archive[
                        prefix + "dense_transform"
                    ].copy(),
                }
            )
    return manifest, tuple(records)


DATA_MANIFEST, INSTANCES = _load_instances()
DEVELOPMENT_INSTANCES = tuple(
    instance for instance in INSTANCES if instance["split"] == "development"
)
HELDOUT_INSTANCES = tuple(
    instance for instance in INSTANCES if instance["split"] == "heldout"
)


def _public_problem(instance, shifted=False):
    overlap = instance["shifted_overlap"] if shifted else instance["overlap"]
    core = (
        instance["shifted_core_hamiltonian"]
        if shifted
        else instance["core_hamiltonian"]
    )
    eri = instance["shifted_eri"] if shifted else instance["eri"]
    nuclear_repulsion = (
        instance["shifted_nuclear_repulsion"]
        if shifted
        else instance["nuclear_repulsion"]
    )
    coordinates = (
        instance["shifted_coordinates_angstrom"]
        if shifted
        else instance["coordinates_angstrom"]
    )
    return {
        "overlap": overlap.copy(),
        "core_hamiltonian": core.copy(),
        "electron_repulsion_integrals": eri.copy(),
        "nuclear_repulsion": float(nuclear_repulsion),
        "electron_count": int(instance["electron_count"]),
        "occupied_orbital_count": int(instance["occupied_orbital_count"]),
        "nuclear_charges": instance["nuclear_charges"].copy(),
        "coordinates_angstrom": coordinates.copy(),
        "integral_convention": "chemist_pqrs",
        "method": "restricted_closed_shell_hartree_fock",
        "artifact": "occupied_spatial_orbital_coefficients",
    }


def _fock_matrix(density, core_hamiltonian, eri):
    coulomb = np.einsum("rs,pqrs->pq", density, eri, optimize=True)
    exchange = np.einsum("rs,prqs->pq", density, eri, optimize=True)
    return core_hamiltonian + coulomb - 0.5 * exchange


def _raw_energy(coefficients, core_hamiltonian, eri, nuclear_repulsion):
    density = 2.0 * coefficients @ coefficients.T
    fock = _fock_matrix(density, core_hamiltonian, eri)
    return float(
        0.5 * np.sum(density * (core_hamiltonian + fock))
        + nuclear_repulsion
    )


def _symmetric_matrix_power(matrix, exponent):
    values, vectors = np.linalg.eigh(matrix)
    if np.min(values) <= 1.0e-10:
        raise ValueError("overlap is not positive definite")
    return (vectors * values ** exponent) @ vectors.T


def _core_guess(problem):
    overlap = np.asarray(problem["overlap"], dtype=float)
    core = np.asarray(problem["core_hamiltonian"], dtype=float)
    orthogonalizer = _symmetric_matrix_power(overlap, -0.5)
    _, vectors = np.linalg.eigh(orthogonalizer @ core @ orthogonalizer)
    return orthogonalizer @ vectors[:, : int(problem["occupied_orbital_count"])]


def _validate_coefficients(value, overlap, occupied):
    coefficients = np.asarray(value)
    if np.iscomplexobj(coefficients):
        if not np.all(np.isfinite(coefficients)):
            raise ValueError("non-finite orbital coefficient")
        if float(np.max(np.abs(np.imag(coefficients)))) > 1.0e-12:
            raise ValueError("complex orbitals are outside this real-RHF contract")
        coefficients = np.real(coefficients)
    coefficients = np.asarray(coefficients, dtype=float)
    expected = (overlap.shape[0], int(occupied))
    if coefficients.shape != expected:
        raise ValueError("occupied coefficient matrix has wrong shape")
    if not np.all(np.isfinite(coefficients)):
        raise ValueError("non-finite orbital coefficient")
    gram = coefficients.T @ overlap @ coefficients
    orthonormality_error = float(np.linalg.norm(gram - np.eye(occupied)))
    if orthonormality_error > ORTHONORMALITY_TOLERANCE:
        raise ValueError("occupied orbitals are not overlap-orthonormal")
    return coefficients, orthonormality_error


def _diagnostics(coefficients, overlap, core, eri, nuclear_repulsion):
    occupied = coefficients.shape[1]
    density = 2.0 * coefficients @ coefficients.T
    fock = _fock_matrix(density, core, eri)
    energy = float(
        0.5 * np.sum(density * (core + fock)) + nuclear_repulsion
    )
    electron_count = float(np.trace(density @ overlap))
    electron_error = abs(electron_count - 2.0 * occupied)
    density_orthogonal = (
        _symmetric_matrix_power(overlap, 0.5)
        @ density
        @ _symmetric_matrix_power(overlap, 0.5)
    )
    idempotency_error = float(
        np.linalg.norm(density_orthogonal @ density_orthogonal - 2.0 * density_orthogonal)
    )
    commutator = fock @ density @ overlap - overlap @ density @ fock
    residual_scale = max(
        np.linalg.norm(fock) * np.linalg.norm(density) * np.linalg.norm(overlap),
        1.0e-15,
    )
    scf_residual = float(np.linalg.norm(commutator) / residual_scale)
    return {
        "energy_hartree": energy,
        "electron_count": electron_count,
        "electron_count_error": electron_error,
        "density_idempotency_error": idempotency_error,
        "scf_residual": scf_residual,
        "density": density,
        "fock": fock,
    }


def _normalized_energy_score(baseline_energy, reference_energy, energy):
    denominator = float(baseline_energy - reference_energy)
    if denominator <= 1.0e-8:
        raise ValueError("uncalibrated energy normalization")
    return float(np.clip((baseline_energy - energy) / denominator, 0.0, 1.0))


def _normalized_policy_score(raw_score, baseline_score):
    denominator = 1.0 - float(baseline_score)
    if denominator <= 1.0e-8:
        raise ValueError("uncalibrated policy normalization")
    if float(raw_score) <= float(baseline_score) + 1.0e-8:
        return 0.0
    return float(np.clip(
        (float(raw_score) - float(baseline_score)) / denominator,
        0.0,
        1.0,
    ))


def _transform_problem(problem, transform):
    """Change AO representation: new basis functions = old functions @ transform."""
    overlap = np.asarray(problem["overlap"], dtype=float)
    core = np.asarray(problem["core_hamiltonian"], dtype=float)
    eri = np.asarray(problem["electron_repulsion_integrals"], dtype=float)
    transformed = dict(problem)
    transformed["overlap"] = transform.T @ overlap @ transform
    transformed["core_hamiltonian"] = transform.T @ core @ transform
    transformed["electron_repulsion_integrals"] = np.einsum(
        "pi,qj,rk,sl,pqrs->ijkl",
        transform,
        transform,
        transform,
        transform,
        eri,
        optimize=True,
    )
    return transformed


def _rotation_context(coefficients, overlap):
    square_root = _symmetric_matrix_power(overlap, 0.5)
    inverse_square_root = _symmetric_matrix_power(overlap, -0.5)
    occupied = coefficients.shape[1]
    orthogonal_coefficients = square_root @ coefficients
    left, _, right = np.linalg.svd(orthogonal_coefficients, full_matrices=False)
    occupied_space = left[:, :occupied] @ right[:occupied, :]
    _, _, vh = np.linalg.svd(occupied_space.T, full_matrices=True)
    virtual_space = vh[occupied:].T
    full_coefficients = inverse_square_root @ np.column_stack(
        (occupied_space, virtual_space)
    )
    return full_coefficients


def _minimum_stability_curvature(
    coefficients, overlap, core, eri, nuclear_repulsion, step=STABILITY_STEP
):
    """Finite-difference occupied--virtual orbital-rotation Hessian eigenvalue."""
    full_coefficients = _rotation_context(coefficients, overlap)
    basis_size = overlap.shape[0]
    occupied = coefficients.shape[1]
    directions = []
    for occupied_index in range(occupied):
        for virtual_index in range(basis_size - occupied):
            direction = np.zeros((basis_size, basis_size), dtype=float)
            direction[occupied + virtual_index, occupied_index] = 1.0
            direction[occupied_index, occupied + virtual_index] = -1.0
            directions.append(direction)

    def rotated_energy(generator):
        rotated = full_coefficients @ expm(generator)[:, :occupied]
        return _raw_energy(rotated, core, eri, nuclear_repulsion)

    dimension = len(directions)
    hessian = np.zeros((dimension, dimension), dtype=float)
    zero = np.zeros((basis_size, basis_size), dtype=float)
    central_energy = rotated_energy(zero)
    for first in range(dimension):
        plus = step * directions[first]
        hessian[first, first] = (
            rotated_energy(plus)
            + rotated_energy(-plus)
            - 2.0 * central_energy
        ) / step ** 2
        for second in range(first):
            first_direction = directions[first]
            second_direction = directions[second]
            mixed = (
                rotated_energy(step * (first_direction + second_direction))
                - rotated_energy(step * (first_direction - second_direction))
                - rotated_energy(step * (-first_direction + second_direction))
                + rotated_energy(-step * (first_direction + second_direction))
            ) / (4.0 * step ** 2)
            hessian[first, second] = mixed
            hessian[second, first] = mixed
    eigenvalues = np.linalg.eigvalsh(hessian)
    return float(eigenvalues[0]), eigenvalues


def _evaluate_problem(solve_restricted_hf, problem, reference_energy):
    overlap = np.asarray(problem["overlap"], dtype=float)
    occupied = int(problem["occupied_orbital_count"])
    returned = solve_restricted_hf(problem)
    coefficients, orthonormality_error = _validate_coefficients(
        returned, overlap, occupied
    )
    diagnostics = _diagnostics(
        coefficients,
        overlap,
        np.asarray(problem["core_hamiltonian"], dtype=float),
        np.asarray(problem["electron_repulsion_integrals"], dtype=float),
        float(problem["nuclear_repulsion"]),
    )
    feasible = bool(
        diagnostics["electron_count_error"] <= ELECTRON_COUNT_TOLERANCE
        and diagnostics["density_idempotency_error"] <= IDEMPOTENCY_TOLERANCE
        and diagnostics["scf_residual"] <= SCF_RESIDUAL_TOLERANCE
    )
    if not feasible:
        raise ValueError("artifact fails RHF feasibility gate")
    baseline_coefficients = _core_guess(problem)
    baseline_energy = _raw_energy(
        baseline_coefficients,
        np.asarray(problem["core_hamiltonian"], dtype=float),
        np.asarray(problem["electron_repulsion_integrals"], dtype=float),
        float(problem["nuclear_repulsion"]),
    )
    energy_score = _normalized_energy_score(
        baseline_energy, reference_energy, diagnostics["energy_hartree"]
    )
    residual_factor = math.exp(-(
        diagnostics["scf_residual"] / 4.0e-7
    ) ** 2)
    score = energy_score * residual_factor
    return {
        "valid": True,
        "score": float(score),
        "energy_score": energy_score,
        "residual_factor": residual_factor,
        "energy_hartree": diagnostics["energy_hartree"],
        "reference_energy_hartree": float(reference_energy),
        "baseline_energy_hartree": baseline_energy,
        "energy_error_hartree": diagnostics["energy_hartree"] - reference_energy,
        "orthonormality_error": orthonormality_error,
        "electron_count": diagnostics["electron_count"],
        "electron_count_error": diagnostics["electron_count_error"],
        "density_idempotency_error": diagnostics["density_idempotency_error"],
        "scf_residual": diagnostics["scf_residual"],
        "coefficients": coefficients,
    }


def _invalid_record(instance, reason):
    return {
        "name": instance["name"],
        "split": instance["split"],
        "valid": False,
        "reason": reason,
        "score": 0.0,
        "energy_score": 0.0,
        "scf_residual": 1.0,
        "shifted_valid": False,
        "shifted_score": 0.0,
        "permutation_valid": False,
        "permutation_score": 0.0,
        "dense_transform_valid": False,
        "dense_transform_score": 0.0,
        "representation_invariance_score": 0.0,
        "minimum_stability_curvature": -1.0,
        "internally_stable": False,
        "robustness_score": 0.0,
        "candidate_problem_call_count": 1,
    }


def _reset_candidate_session(solve_restricted_hf):
    reset = getattr(solve_restricted_hf, "reset_session", None)
    if callable(reset):
        reset()


def _evaluate_instance(solve_restricted_hf, instance):
    candidate_calls = 1
    try:
        nominal_problem = _public_problem(instance)
        nominal = _evaluate_problem(
            solve_restricted_hf, nominal_problem, instance["reference_energy"]
        )
    except Exception as exc:
        return _invalid_record(
            instance, "%s: %s" % (type(exc).__name__, exc)
        )

    # Evaluator-only checks never change nominal validity or the search-visible
    # score.  A candidate failure under a sealed shift/representation contributes
    # zero only to the corresponding validation axis.
    _reset_candidate_session(solve_restricted_hf)
    candidate_calls += 1
    try:
        shifted = _evaluate_problem(
            solve_restricted_hf,
            _public_problem(instance, shifted=True),
            instance["shifted_reference_energy"],
        )
        shifted_valid = True
        shifted_reason = None
    except Exception as exc:
        shifted = None
        shifted_valid = False
        shifted_reason = "%s: %s" % (type(exc).__name__, exc)

    representation_rows = []
    nominal_density = 2.0 * nominal["coefficients"] @ nominal["coefficients"].T
    for label, transform in (
        ("permutation", instance["permutation_transform"]),
        ("dense_transform", instance["dense_transform"]),
    ):
        _reset_candidate_session(solve_restricted_hf)
        candidate_calls += 1
        try:
            transformed_problem = _transform_problem(nominal_problem, transform)
            transformed = _evaluate_problem(
                solve_restricted_hf,
                transformed_problem,
                instance["reference_energy"],
            )
            mapped_coefficients = transform @ transformed["coefficients"]
            mapped_density = 2.0 * mapped_coefficients @ mapped_coefficients.T
            density_error = float(
                np.linalg.norm(mapped_density - nominal_density)
                / max(np.linalg.norm(nominal_density), 1.0e-15)
            )
            energy_difference = abs(
                transformed["energy_hartree"] - nominal["energy_hartree"]
            )
            invariance = float(
                transformed["score"]
                * math.exp(-(density_error / 2.0e-5) ** 2)
                * math.exp(-(energy_difference / 2.0e-8) ** 2)
            )
            representation_rows.append(
                {
                    "name": label,
                    "valid": True,
                    "score": transformed["score"],
                    "mapped_density_relative_error": density_error,
                    "energy_difference_hartree": energy_difference,
                    "invariance_score": invariance,
                }
            )
        except Exception as exc:
            representation_rows.append(
                {
                    "name": label,
                    "valid": False,
                    "reason": "%s: %s" % (type(exc).__name__, exc),
                    "score": 0.0,
                    "mapped_density_relative_error": None,
                    "energy_difference_hartree": None,
                    "invariance_score": 0.0,
                }
            )

    minimum_curvature, curvature_eigenvalues = _minimum_stability_curvature(
        nominal["coefficients"],
        nominal_problem["overlap"],
        nominal_problem["core_hamiltonian"],
        nominal_problem["electron_repulsion_integrals"],
        nominal_problem["nuclear_repulsion"],
    )
    stable = minimum_curvature >= STABILITY_TOLERANCE
    stability_factor = 1.0 if stable else 0.0
    representation_score = float(np.mean([
        row["invariance_score"] for row in representation_rows
    ]))
    shifted_score = shifted["score"] if shifted_valid else 0.0
    robustness_score = float(
        (max(shifted_score, 0.0) * max(representation_score, 0.0))
        ** 0.5
        * stability_factor
    )
    return {
        "name": instance["name"],
        "split": instance["split"],
        "valid": True,
        "score": nominal["score"],
        "energy_score": nominal["energy_score"],
        "energy_hartree": nominal["energy_hartree"],
        "reference_energy_hartree": nominal["reference_energy_hartree"],
        "baseline_energy_hartree": nominal["baseline_energy_hartree"],
        "energy_error_hartree": nominal["energy_error_hartree"],
        "scf_residual": nominal["scf_residual"],
        "orthonormality_error": nominal["orthonormality_error"],
        "electron_count_error": nominal["electron_count_error"],
        "density_idempotency_error": nominal["density_idempotency_error"],
        "shifted_valid": shifted_valid,
        "shifted_reason": shifted_reason,
        "shifted_score": shifted_score,
        "shifted_energy_error_hartree": (
            shifted["energy_error_hartree"] if shifted_valid else None
        ),
        "shifted_scf_residual": (
            shifted["scf_residual"] if shifted_valid else None
        ),
        "permutation_valid": representation_rows[0]["valid"],
        "permutation_score": representation_rows[0]["invariance_score"],
        "dense_transform_valid": representation_rows[1]["valid"],
        "dense_transform_score": representation_rows[1]["invariance_score"],
        "representation_invariance_score": representation_score,
        "minimum_stability_curvature": minimum_curvature,
        "stability_eigenvalues": curvature_eigenvalues.tolist(),
        "internally_stable": stable,
        "robustness_score": robustness_score,
        "candidate_problem_call_count": candidate_calls,
        "nominal": {
            key: value
            for key, value in nominal.items()
            if key not in ("coefficients", "valid")
        },
        "shifted": (
            {
                key: value
                for key, value in shifted.items()
                if key not in ("coefficients", "valid")
            }
            if shifted_valid else None
        ),
        "representation_checks": representation_rows,
    }


def evaluate(solve_restricted_hf):
    records = []
    for index, instance in enumerate(INSTANCES):
        if index:
            _reset_candidate_session(solve_restricted_hf)
        records.append(_evaluate_instance(solve_restricted_hf, instance))
    development = [row for row in records if row["split"] == "development"]
    heldout = [row for row in records if row["split"] == "heldout"]
    development_valid = all(row["valid"] for row in development)
    heldout_valid = all(row["valid"] for row in heldout)
    development_raw_score = float(np.mean([
        row["score"] for row in development
    ]))
    development_score = _normalized_policy_score(
        development_raw_score, BASELINE_DEVELOPMENT_RAW_SCORE
    )
    heldout_score = float(np.mean([row["score"] for row in heldout]))
    result = {
        "combined_score": development_score if development_valid else 0.0,
        "valid": 1.0 if development_valid else 0.0,
        "feasibility_rate": float(np.mean([row["valid"] for row in development])),
        "raw_score": development_raw_score if development_valid else 0.0,
        "robustness_score": _normalized_policy_score(
            float(np.mean([
                row["robustness_score"] for row in development
            ])),
            BASELINE_DEVELOPMENT_ROBUSTNESS_SCORE,
        ),
        "heldout_policy_score": heldout_score if heldout_valid else 0.0,
        "heldout_robustness_score": float(np.mean([
            row["robustness_score"] for row in heldout
        ])),
        "heldout_feasibility_rate": float(np.mean([
            row["valid"] for row in heldout
        ])),
        "development_shifted_score": float(np.mean([
            row["shifted_score"] for row in development
        ])),
        "heldout_shifted_score": float(np.mean([
            row["shifted_score"] for row in heldout
        ])),
        "development_representation_invariance_score": float(np.mean([
            row["representation_invariance_score"] for row in development
        ])),
        "heldout_representation_invariance_score": float(np.mean([
            row["representation_invariance_score"] for row in heldout
        ])),
        "development_stability_rate": float(np.mean([
            row["internally_stable"] for row in development
        ])),
        "heldout_stability_rate": float(np.mean([
            row["internally_stable"] for row in heldout
        ])),
        "development_mean_energy_error_hartree": float(np.mean([
            row.get("energy_error_hartree", 0.0) for row in development
        ])),
        "heldout_mean_energy_error_hartree": float(np.mean([
            row.get("energy_error_hartree", 0.0) for row in heldout
        ])),
        "development_maximum_scf_residual": float(max(
            row["scf_residual"] for row in development
        )),
        "heldout_maximum_scf_residual": float(max(
            row["scf_residual"] for row in heldout
        )),
        "candidate_problem_call_count": int(sum(
            row["candidate_problem_call_count"] for row in records
        )),
        "candidate_instance_valid_rate": float(np.mean([
            row["valid"] for row in records
        ])),
        "per_instance": records,
    }
    if not development_valid:
        result["error_message"] = "candidate invalid on a development RHF instance"
    return result


def reference_policy(problem, shifted=False):
    """Return the frozen witness associated with an exact public problem."""
    overlap = np.asarray(problem["overlap"], dtype=float)
    core = np.asarray(problem["core_hamiltonian"], dtype=float)
    matches = []
    for instance in INSTANCES:
        for use_shifted in (False, True):
            candidate_problem = _public_problem(instance, shifted=use_shifted)
            if (
                overlap.shape == candidate_problem["overlap"].shape
                and core.shape == candidate_problem["core_hamiltonian"].shape
                and np.array_equal(overlap, candidate_problem["overlap"])
                and np.array_equal(core, candidate_problem["core_hamiltonian"])
            ):
                coefficients = (
                    instance["shifted_reference_coefficients"]
                    if use_shifted
                    else instance["reference_coefficients"]
                )
                matches.append(coefficients.copy())
        for transform in (
            instance["permutation_transform"], instance["dense_transform"]
        ):
            candidate_problem = _transform_problem(
                _public_problem(instance), transform
            )
            if (
                overlap.shape == candidate_problem["overlap"].shape
                and core.shape == candidate_problem["core_hamiltonian"].shape
                and np.allclose(overlap, candidate_problem["overlap"], atol=1e-13)
                and np.allclose(core, candidate_problem["core_hamiltonian"], atol=1e-13)
            ):
                matches.append(
                    np.linalg.solve(transform, instance["reference_coefficients"])
                )
    if len(matches) != 1:
        raise ValueError("unknown or ambiguous RHF problem")
    return matches[0]
