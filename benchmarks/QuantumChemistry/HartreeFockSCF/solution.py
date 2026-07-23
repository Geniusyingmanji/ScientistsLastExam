"""Conventional single-start DIIS baseline for finite-basis closed-shell RHF."""

from __future__ import annotations

import numpy as np
from scipy.linalg import eigh


def _fock_matrix(density, core_hamiltonian, eri):
    coulomb = np.einsum("rs,pqrs->pq", density, eri, optimize=True)
    exchange = np.einsum("rs,prqs->pq", density, eri, optimize=True)
    return core_hamiltonian + coulomb - 0.5 * exchange


def solve_restricted_hf(problem):
    """Return occupied spatial-orbital coefficients from one core-Hamiltonian start.

    This deliberately conventional baseline uses Pulay DIIS but no multistart search,
    direct energy minimization, or stability-driven orbital rotations.  It therefore
    converges reliably on the easy regimes while retaining headroom on a multi-solution
    symmetry-breaking case.
    """
    overlap = np.asarray(problem["overlap"], dtype=float)
    core = np.asarray(problem["core_hamiltonian"], dtype=float)
    eri = np.asarray(problem["electron_repulsion_integrals"], dtype=float)
    occupied = int(problem["occupied_orbital_count"])

    _, coefficients = eigh(core, overlap, check_finite=True)
    coefficients = coefficients[:, :occupied]
    fock_history = []
    error_history = []

    for _iteration in range(100):
        density = 2.0 * coefficients @ coefficients.T
        fock = _fock_matrix(density, core, eri)
        error = fock @ density @ overlap - overlap @ density @ fock
        fock_history.append(fock.copy())
        error_history.append(error.ravel().copy())
        if len(fock_history) > 8:
            fock_history.pop(0)
            error_history.pop(0)

        extrapolated = fock
        if len(fock_history) >= 2:
            count = len(fock_history)
            pulay = np.empty((count + 1, count + 1), dtype=float)
            for first in range(count):
                for second in range(count):
                    pulay[first, second] = np.dot(
                        error_history[first], error_history[second]
                    )
            pulay[:count, count] = -1.0
            pulay[count, :count] = -1.0
            pulay[count, count] = 0.0
            right_hand_side = np.zeros(count + 1, dtype=float)
            right_hand_side[count] = -1.0
            try:
                weights = np.linalg.solve(pulay, right_hand_side)[:count]
                extrapolated = sum(
                    weights[index] * fock_history[index]
                    for index in range(count)
                )
            except np.linalg.LinAlgError:
                pass

        _, full_coefficients = eigh(
            extrapolated, overlap, check_finite=True
        )
        updated = full_coefficients[:, :occupied]
        updated_density = 2.0 * updated @ updated.T
        coefficients = updated
        if (
            np.linalg.norm(updated_density - density) < 1.0e-10
            and np.linalg.norm(error) < 1.0e-9
        ):
            break

    return coefficients
