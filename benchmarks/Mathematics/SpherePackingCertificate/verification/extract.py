"""Exact rational SOS extraction on the half-line: p(w) = sigma0(w) + w*sigma1(w)."""
from __future__ import annotations

from fractions import Fraction

import numpy as np
from scipy.optimize import minimize

from lp_algebra import nonnegative_on_half_line


def _sizes(degree):
    m0 = degree // 2
    m1 = max(0, (degree - 1) // 2)
    return m0 + 1, m1 + 1


def _groups(n0, n1, width):
    """Which Gram cells feed each output coefficient. Cells partition by output degree."""
    table = {k: ([], []) for k in range(width)}
    for i in range(n0):
        for j in range(n0):
            table[i + j][0].append((i, j))
    for i in range(n1):
        for j in range(n1):
            table[i + j + 1][1].append((i, j))
    return table


def _numeric(target, n0, n1, width, margin=1e-3, tries=12):
    """Fit the coefficient identity with Gram matrices held strictly inside the PSD cone.

    G = a^T a + margin*I makes the interiority structural, which matters because the rounding that
    follows must not fall out of the cone: an optimum on the boundary does not survive being
    written down as a rational. With interiority structural the objective is a smooth least-squares
    fit and has an analytic gradient, where maximising a minimum eigenvalue directly is non-smooth
    and defeated L-BFGS on even the trivial target w.
    """
    goal = np.zeros(width)
    for i, value in enumerate(target):
        goal[i] = float(value)
    table = _groups(n0, n1, width)
    # Which output coefficient each Gram cell feeds, as flat index arrays.
    idx0 = np.empty(n0 * n0, dtype=np.int64)
    idx1 = np.empty(max(1, n1 * n1), dtype=np.int64)
    for k, (gc, hc) in table.items():
        for i, j in gc:
            idx0[i * n0 + j] = k
        for i, j in hc:
            idx1[i * n1 + j] = k
    eye0 = np.eye(n0) * margin
    eye1 = np.eye(n1) * margin

    def value_and_gradient(x):
        a = x[:n0 * n0].reshape(n0, n0)
        b = x[n0 * n0:].reshape(n1, n1)
        G = a.T @ a + eye0
        H = b.T @ b + eye1
        produced = (np.bincount(idx0, weights=G.ravel(), minlength=width)
                    + np.bincount(idx1, weights=H.ravel(), minlength=width))
        residual = produced - goal
        outer0 = (2.0 * residual)[idx0].reshape(n0, n0)
        outer1 = (2.0 * residual)[idx1].reshape(n1, n1)
        grad = np.concatenate([(a @ (outer0 + outer0.T)).ravel(),
                               (b @ (outer1 + outer1.T)).ravel()])
        return float(residual @ residual), grad

    for attempt in range(tries):
        rng = np.random.default_rng(attempt)
        x = rng.normal(scale=0.5, size=n0 * n0 + n1 * n1)
        result = minimize(value_and_gradient, x, jac=True, method="L-BFGS-B",
                          options={"maxiter": 40000, "maxfun": 80000, "ftol": 1e-20,
                                   "gtol": 1e-18})
        a = result.x[:n0 * n0].reshape(n0, n0)
        b = result.x[n0 * n0:].reshape(n1, n1)
        G = a.T @ a + eye0
        H = b.T @ b + eye1
        produced = (np.bincount(idx0, weights=G.ravel(), minlength=width)
                    + np.bincount(idx1, weights=H.ravel(), minlength=width))
        if np.max(np.abs(produced - goal)) < 1e-10:
            return G, H, table
    return None


def _psd_squares(gram, size):
    """Exact LDL of a rational PSD matrix into weighted squares; None if not semidefinite."""
    work = [[Fraction(v) for v in row] for row in gram]
    squares = []
    for k in range(size):
        pivot = max(range(k, size), key=lambda r: work[r][r])
        if work[pivot][pivot] < 0:
            return None
        if work[pivot][pivot] == 0:
            if any(work[r][c] != 0 for r in range(k, size) for c in range(k, size)):
                return None
            break
        if work[k][k] == 0:
            work[k], work[pivot] = work[pivot], work[k]
            for r in range(size):
                work[r][k], work[r][pivot] = work[r][pivot], work[r][k]
        head = work[k][k]
        vector = [Fraction(0)] * size
        vector[k] = Fraction(1)
        for c in range(k + 1, size):
            vector[c] = work[k][c] / head
        squares.append((head, vector))
        for r in range(k + 1, size):
            factor = work[r][k]
            if factor == 0:
                continue
            factor /= head
            for c in range(k + 1, size):
                work[r][c] -= factor * work[k][c]
    return squares


def extract(target, denominator=10 ** 12):
    """Return (sigma0, sigma1) proving target >= 0 on [0, infinity), or None."""
    poly = [Fraction(v) for v in target]
    while poly and poly[-1] == 0:
        poly.pop()
    if not poly:
        return [], []
    degree = len(poly) - 1
    n0, n1 = _sizes(degree)
    width = max(2 * (n0 - 1), 2 * (n1 - 1) + 1) + 1
    found = _numeric(poly, n0, n1, width)
    if found is None:
        return None
    G, H, table = found
    gram0 = [[Fraction(round(G[i, j] * denominator), denominator) for j in range(n0)]
             for i in range(n0)]
    gram1 = [[Fraction(round(H[i, j] * denominator), denominator) for j in range(n1)]
             for i in range(n1)]
    for grid in (gram0, gram1):
        n = len(grid)
        for i in range(n):
            for j in range(i + 1, n):
                mid = (grid[i][j] + grid[j][i]) / 2
                grid[i][j] = grid[j][i] = mid
    # Exact repair: every Gram cell belongs to exactly one output coefficient, so distributing
    # each deficit over its own group restores the identity without touching any other.
    for k, (gc, hc) in table.items():
        want = poly[k] if k < len(poly) else Fraction(0)
        have = sum(gram0[i][j] for i, j in gc) + sum(gram1[i][j] for i, j in hc)
        cells = len(gc) + len(hc)
        if cells == 0:
            if want != 0:
                return None
            continue
        shift = (want - have) / cells
        for i, j in gc:
            gram0[i][j] += shift
        for i, j in hc:
            gram1[i][j] += shift
    squares0 = _psd_squares(gram0, n0)
    squares1 = _psd_squares(gram1, n1)
    if squares0 is None or squares1 is None:
        return None
    sigma0 = [(w, v) for w, v in squares0 if w != 0]
    sigma1 = [(w, v) for w, v in squares1 if w != 0]
    if not nonnegative_on_half_line(poly, sigma0, sigma1):
        return None
    return sigma0, sigma1
