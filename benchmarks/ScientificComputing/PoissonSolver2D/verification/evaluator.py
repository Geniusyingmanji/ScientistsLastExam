"""Frozen oracle for PoissonSolver2D (hidden from the agent).

Solves -laplacian(u) = f on the unit square with homogeneous Dirichlet BCs. The exact
solution is a held-out sum of sine modes; only the sampled right-hand side is passed to the
candidate. The score is the log-scaled error reduction between a weak Jacobi baseline and
a near-exact spectral-sine reference on the N=127 interior grid.
"""

from __future__ import annotations

import numpy as np

N = 127
MODES = [(1, 1, 1.0), (3, 5, 0.6), (7, 2, -0.35), (9, 8, 0.2), (13, 4, -0.15)]
E_BASELINE = 8.981737822457003e-01
E_REFERENCE = 1.0e-10


def _h() -> float:
    return 1.0 / (N + 1)


def f_grid() -> np.ndarray:
    h = _h()
    xs = (np.arange(1, N + 1)) * h
    X, Y = np.meshgrid(xs, xs, indexing="ij")
    f = np.zeros_like(X)
    for k, m, c in MODES:
        f += c * ((k * np.pi) ** 2 + (m * np.pi) ** 2) * np.sin(k * np.pi * X) * np.sin(m * np.pi * Y)
    return f


def u_true_grid() -> np.ndarray:
    h = _h()
    xs = (np.arange(1, N + 1)) * h
    X, Y = np.meshgrid(xs, xs, indexing="ij")
    u = np.zeros_like(X)
    for k, m, c in MODES:
        u += c * np.sin(k * np.pi * X) * np.sin(m * np.pi * Y)
    return u


def evaluate(solve_poisson) -> dict:
    U = u_true_grid()
    rhs = f_grid()
    try:
        u = np.asarray(solve_poisson(N, rhs.copy()), dtype=float)
    except Exception as exc:  # noqa: BLE001
        return {"combined_score": 0.0, "valid": 0.0, "error_message": f"raised: {exc}"}
    if u.shape != (N, N) or not np.all(np.isfinite(u)):
        return {"combined_score": 0.0, "valid": 0.0, "error_message": "bad shape or non-finite"}
    err = float(np.linalg.norm(u - U) / np.linalg.norm(U))
    lo, hi = np.log10(E_BASELINE), np.log10(E_REFERENCE)
    score = (np.log10(max(err, 1e-16)) - lo) / (hi - lo)
    score = float(min(1.0, max(0.0, score)))
    return {
        "combined_score": score,
        "valid": 1.0,
        "rel_l2_error": err,
        "e_baseline": E_BASELINE,
        "e_reference": E_REFERENCE,
    }
