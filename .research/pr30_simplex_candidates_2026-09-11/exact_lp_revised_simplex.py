"""Exact Farkas LP used only by tests to pin hidden optimal_delta scalars."""
from __future__ import annotations

from fractions import Fraction

import numpy as np
from scipy.optimize import linprog


def _gaussian(matrix, rhs):
    work = [list(row) + [value] for row, value in zip(matrix, rhs)]
    n = len(rhs)
    for k in range(n):
        pivot = next(i for i in range(k, n) if work[i][k])
        work[k], work[pivot] = work[pivot], work[k]
        scale = work[k][k]
        work[k] = [value / scale for value in work[k]]
        for i in range(n):
            if i != k:
                scale = work[i][k]
                work[i] = [x - scale * y for x, y in zip(work[i], work[k])]
    return [row[-1] for row in work]


def exact_maximum_delta(guards, a, b_vec):
    n = len(a)
    m = len(guards)
    g_rows = [slope for slope, _ in guards]
    d_vec = [intercept for _, intercept in guards]
    i_minus_at = [[Fraction(i == j) - a[j][i] for j in range(n)] for i in range(n)]
    n_rp, n_rn = 0, n
    n_sp, n_sn = 2 * n, 2 * n + 1
    n_delta = 2 * n + 2
    n_lam = 2 * n + 3
    n_mu = n_lam + m
    n_snn = n_mu + m
    n_sdec = n_snn + 1
    nvars = n_sdec + 1

    def zeros():
        return [Fraction(0)] * nvars

    eqs = []
    row = zeros()
    for i in range(n):
        row[n_rp + i] = Fraction(1)
        row[n_rn + i] = Fraction(1)
    eqs.append((row, Fraction(1)))
    for k in range(n):
        row = zeros()
        for j in range(m):
            row[n_lam + j] = g_rows[j][k]
        row[n_rp + k] = Fraction(-1)
        row[n_rn + k] = Fraction(1)
        eqs.append((row, Fraction(0)))
    for k in range(n):
        row = zeros()
        for j in range(m):
            row[n_mu + j] = g_rows[j][k]
        for i in range(n):
            row[n_rp + i] -= i_minus_at[k][i]
            row[n_rn + i] += i_minus_at[k][i]
        eqs.append((row, Fraction(0)))
    row = zeros()
    row[n_sp] = Fraction(1)
    row[n_sn] = Fraction(-1)
    for j in range(m):
        row[n_lam + j] = -d_vec[j]
    row[n_snn] = Fraction(-1)
    eqs.append((row, Fraction(0)))
    row = zeros()
    for i in range(n):
        row[n_rp + i] = -b_vec[i]
        row[n_rn + i] = b_vec[i]
    row[n_delta] = Fraction(-1)
    for j in range(m):
        row[n_mu + j] = -d_vec[j]
    row[n_sdec] = Fraction(-1)
    eqs.append((row, Fraction(0)))

    A = [eq[0] for eq in eqs]
    rhs = [eq[1] for eq in eqs]
    c = [Fraction(0)] * nvars
    c[n_delta] = Fraction(1)
    af = np.array([[float(x) for x in row] for row in A], dtype=float)
    bf = np.array([float(x) for x in rhs], dtype=float)
    cf = np.array([float(x) for x in c], dtype=float)
    result = linprog(-cf, A_eq=af, b_eq=bf, bounds=[(0, None)] * nvars, method="revised simplex")
    if not result.success:
        raise RuntimeError(result.message)
    basic = []
    for idx in np.argsort(-np.abs(result.x)):
        trial = basic + [int(idx)]
        mat = np.array([[float(A[i][j]) for j in trial] for i in range(len(A))], dtype=float)
        if np.linalg.matrix_rank(mat, tol=1e-10) == len(trial):
            basic.append(int(idx))
            if len(basic) == len(A):
                break
    matrix = [[A[i][j] for j in basic] for i in range(len(A))]
    x_basic = _gaussian(matrix, rhs)
    x = [Fraction(0)] * nvars
    for idx, value in zip(basic, x_basic):
        if value < 0:
            if value > Fraction(-1, 10 ** 12):
                value = Fraction(0)
            else:
                raise RuntimeError("negative basic variable")
        x[idx] = value
    for row, value in zip(A, rhs):
        if sum(a_i * xi for a_i, xi in zip(row, x)) != value:
            raise RuntimeError("exact residual")
    r = [x[n_rp + i] - x[n_rn + i] for i in range(n)]
    return {
        "r": r,
        "s": x[n_sp] - x[n_sn],
        "delta": x[n_delta],
        "nonneg_lambdas": x[n_lam:n_lam + m],
        "decrease_lambdas": x[n_mu:n_mu + m],
    }


# Fixed serialization adapter over public instance values only.
def _public_fraction(value):
    if isinstance(value, int) and not isinstance(value, bool):
        return Fraction(value)
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return Fraction(value[0], value[1])
    raise ValueError("public rational must be integer or [numerator, denominator]")


def _public_ratio(value):
    return [value.numerator, value.denominator]


def build_ranking(instance):
    guards = [([_public_fraction(x) for x in row["g"]],
               _public_fraction(row["d"])) for row in instance["guards"]]
    a = [[_public_fraction(x) for x in row] for row in instance["A"]]
    b = [_public_fraction(x) for x in instance["b"]]
    witness = exact_maximum_delta(guards, a, b)
    return {"r": [_public_ratio(x) for x in witness["r"]],
            "s": _public_ratio(witness["s"]),
            "delta": _public_ratio(witness["delta"]),
            "nonneg_lambdas": [_public_ratio(x) for x in witness["nonneg_lambdas"]],
            "decrease_lambdas": [_public_ratio(x) for x in witness["decrease_lambdas"]]}
