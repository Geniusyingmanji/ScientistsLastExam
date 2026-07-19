"""Initial baseline for PoissonSolver2D (weak but valid).

Solves the discrete Poisson system with 50 Jacobi sweeps — nowhere near converged, so the
error is large. Edit this file to do better: a direct sparse solve of the 5-point system,
a higher-order stencil, multigrid, or a sine/spectral method.
"""

import numpy as np


def solve_poisson(n: int, rhs: np.ndarray) -> np.ndarray:
    h = 1.0 / (n + 1)
    u = np.zeros((n + 2, n + 2))
    f = np.zeros((n + 2, n + 2))
    f[1:-1, 1:-1] = np.asarray(rhs, dtype=float) * h * h
    for _ in range(50):  # far from converged
        u[1:-1, 1:-1] = 0.25 * (u[:-2, 1:-1] + u[2:, 1:-1] + u[1:-1, :-2] + u[1:-1, 2:]
                                + f[1:-1, 1:-1])
    return u[1:-1, 1:-1]
