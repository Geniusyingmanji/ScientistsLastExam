"""Truth-blind reference for HiddenCouplingNetwork: multi-unit drives, sparse regression per unit,
and a noise-floor test that turns unexplained residual into a refusal.

Reads only the public problem and the budgeted laboratory. Deliberately not at the ceiling: it
spends the whole budget on one fixed Rademacher design, fits each unit by orthogonal matching
pursuit with a BIC stop, and declines whenever two or more units cannot be explained sparsely.
Better designs (adaptive re-drives near ambiguous units), stability selection across
sub-designs, and a sharper hidden-unit test are the headroom a searcher is meant to claim.
"""
from __future__ import annotations

import numpy as np

AMPLITUDE_FRACTION = 0.7
PARTICIPATION = 0.5
EDGE_FLOOR = 0.15          # |A_ij / gamma_i| below this is not an edge (true edges sit >= 0.25)
RESIDUAL_RATIO = 4.0       # sparse-fit residual variance over the noise floor that flags a unit
UNEXPLAINED_UNITS = 2      # this many flagged units means unmeasured units are coupled in


def _design(n, k, amplitude, rng):
    """k drives over n units: each unit joins about half the drives with a random sign."""
    drives = []
    for _ in range(k):
        mask = rng.uniform(size=n) < PARTICIPATION
        if not mask.any():
            mask[int(rng.integers(0, n))] = True
        signs = rng.choice([-1.0, 1.0], size=n)
        drives.append(amplitude * mask * signs)
    return drives


def _omp(y, X, sigma2, always=(), max_terms=4):
    """Orthogonal matching pursuit with a BIC stop. Returns (support, coefficients)."""
    k, p = X.shape
    support = list(always)
    best = None
    for _ in range(max_terms + len(always)):
        beta = np.linalg.lstsq(X[:, support], y, rcond=None)[0] if support else np.zeros(0)
        residual = y - (X[:, support] @ beta if support else 0.0)
        rss = float(residual @ residual)
        bic = rss / sigma2 + len(support) * np.log(k)
        if best is None or bic < best[0] - 1e-9:
            best = (bic, list(support), beta, rss)
        elif len(support) > len(always):
            break
        if len(support) >= max_terms + len(always):
            break
        candidates = [j for j in range(p) if j not in support]
        if not candidates:
            break
        scores = [abs(float(X[:, j] @ residual)) / (np.linalg.norm(X[:, j]) + 1e-12) for j in candidates]
        support.append(candidates[int(np.argmax(scores))])
    _bic, support, beta, rss = best
    return support, beta, rss


def discover_couplings(problem, run_experiment):
    n = int(problem["units"])
    budget = int(problem["experiment_budget"])
    sigma = float(problem["noise_sigma"])
    amplitude = AMPLITUDE_FRACTION * float(problem["drive_bound"])
    rng = np.random.default_rng(12345)
    drives = _design(n, budget, amplitude, rng)
    states = []
    for u in drives:
        states.append(np.asarray(run_experiment(u), dtype=float))
    U = np.asarray(drives)          # (k, n)
    X = np.asarray(states)          # (k, n)
    T = np.tanh(X)
    edges = []
    flagged = 0
    for i in range(n):
        # x_i = sum_j (A_ij/gamma_i) tanh(x_j) + (1/gamma_i) u_i : regress on tanh of the others
        # and on the unit's own drive, which is always in the model.
        others = [j for j in range(n) if j != i]
        design = np.column_stack([T[:, others], U[:, i]])
        drive_column = design.shape[1] - 1
        # Regressor noise propagates into the residual, so the floor is above sigma^2.
        sigma2 = sigma ** 2 * (1.0 + 1.5)
        support, beta, rss = _omp(X[:, i], design, sigma2, always=(drive_column,))
        dof = max(1, len(X[:, i]) - len(support))
        if rss / dof > RESIDUAL_RATIO * sigma2:
            flagged += 1
        for column, coefficient in zip(support, beta):
            if column == drive_column:
                continue
            if abs(coefficient) >= EDGE_FLOOR:
                edges.append([int(others[column]), int(i), 1.0 if coefficient > 0 else -1.0])
    if flagged >= UNEXPLAINED_UNITS:
        return {"abstain": True, "confidence": 0.7}
    return {"edges": edges, "abstain": False, "confidence": 0.7}
