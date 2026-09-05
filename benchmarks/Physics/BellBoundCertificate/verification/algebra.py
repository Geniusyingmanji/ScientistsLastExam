"""Exact arithmetic for sum-of-squares certificates in a bipartite Bell scenario.

Everything here is rational. Nothing is scored from a float, and nothing is scored from a
tolerance: a certificate either satisfies the operator identity exactly or it does not. That
choice is the point of the task rather than an implementation detail - a numerical SDP solution
is not a proof, and turning one into a proof is the work.

The algebra is the free product of two groups of involutions. Alice's observables `A_x` and
Bob's `B_y` take values in {-1, +1}, so `A_x^2 = B_y^2 = I`, distinct observables of the same
party do not commute, and every observable of one party commutes with every observable of the
other. A word is therefore canonical when it is written as a reduced A-part followed by a
reduced B-part, "reduced" meaning no two adjacent letters are equal.
"""
from __future__ import annotations

from fractions import Fraction


def reduce_side(letters) -> tuple:
    """Free reduction under X_i^2 = I."""
    out: list = []
    for x in letters:
        if out and out[-1] == x:
            out.pop()
        else:
            out.append(x)
    return tuple(out)


def canonical(a, b) -> tuple:
    return (reduce_side(a), reduce_side(b))


def dagger(word: tuple) -> tuple:
    a, b = word
    return (tuple(reversed(a)), tuple(reversed(b)))


def multiply(u: tuple, v: tuple) -> tuple:
    """u * v, using [A_x, B_y] = 0 to keep the A-part and B-part separate."""
    return canonical(u[0] + v[0], u[1] + v[1])


def expand(matrix, basis):
    """Collect ``u^dagger Q u`` into {canonical word: rational coefficient}.

    `u` is the column vector of basis words, so the operator is the double sum over basis
    pairs of ``Q[i][j] * basis[i]^dagger * basis[j]``.
    """
    products = {}
    for i, s in enumerate(basis):
        di = dagger(s)
        row = matrix[i]
        for j, t in enumerate(basis):
            coefficient = row[j]
            if coefficient == 0:
                continue
            word = multiply(di, t)
            products[word] = products.get(word, Fraction(0)) + coefficient
    return {word: value for word, value in products.items() if value != 0}


def is_positive_semidefinite(matrix, size) -> bool:
    """Exact PSD test by symmetric Gaussian elimination with diagonal pivoting.

    Each step takes the Schur complement about the largest remaining diagonal entry, which keeps
    the working matrix symmetric and never needs a square root. A negative pivot exhibits a
    direction of negative curvature. A zero pivot is admissible only when the entire remaining
    block vanishes: if the largest remaining diagonal entry is zero but some off-diagonal entry
    is not, the two-by-two minor through it has determinant ``-m^2 < 0``.

    The caller has already bounded the size and the entry magnitudes, so the rationals cannot
    grow without limit.
    """
    work = [[Fraction(value) for value in row] for row in matrix]
    for k in range(size):
        pivot_row = max(range(k, size), key=lambda r: work[r][r])
        if work[pivot_row][pivot_row] < 0:
            return False
        if work[pivot_row][pivot_row] == 0:
            return all(work[r][c] == 0 for r in range(k, size) for c in range(k, size))
        work[k], work[pivot_row] = work[pivot_row], work[k]
        for r in range(size):
            work[r][k], work[r][pivot_row] = work[r][pivot_row], work[r][k]
        pivot = work[k][k]
        for r in range(k + 1, size):
            factor = work[r][k]
            if factor == 0:
                continue
            factor = factor / pivot
            for c in range(k + 1, size):
                work[r][c] -= factor * work[k][c]
    return True
