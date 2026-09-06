"""Readable statement of the two checks the oracle performs.

This module is the reference text for the rules. The oracle in ``evaluator.py`` carries its own
inlined copy, because the trusted driver loads that file by path rather than as a package and a
sibling import raises ModuleNotFoundError inside the candidate sandbox. The task's tests compare
the two copies.

Two objects are checked, and they bound the Shannon capacity of an odd cycle from opposite sides.

**Below.** ``Theta(G) >= alpha(G^{box k})^{1/k}`` for every ``k``, where ``G^{box k}`` is the k-th
strong product power: distinct vertices ``u`` and ``v`` are adjacent when in every coordinate they
are equal or adjacent. An independent set in that power is a zero-error code of block length ``k``,
and exhibiting one is a proof. Checking it is a membership test, not a search: for each codeword,
none of the ``3^k - 1`` non-zero shifts by ``{0, +1, -1}`` may also be a codeword.

**Above.** Lovasz's ``theta`` bounds the capacity because it is multiplicative under the strong
product. Its dual-side form is the one that certifies: for any symmetric real matrix ``A`` with
``A[i][i] = 1`` and ``A[i][j] = 1`` at every *non-adjacent* pair ``i != j``, ``lambda_max(A)`` is an
upper bound for ``theta(G)`` and hence for ``Theta(G)``. Free entries sit exactly on the edges.
A rational ``A`` together with a rational ``b`` proves ``Theta(G) <= b`` as soon as ``b*I - A`` is
positive definite, and that is decided here by exact rational elimination with no tolerance.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import product


def cycle_adjacent(n: int, i: int, j: int) -> bool:
    """Adjacency in the cycle C_n on the vertex set Z_n."""
    return (i - j) % n in (1, n - 1)


def strong_power_shifts(n: int, power: int):
    """The non-zero difference vectors that make two codewords adjacent."""
    return [shift for shift in product((0, 1, n - 1), repeat=power) if any(shift)]


def is_independent(n: int, power: int, vertices) -> bool:
    """True when no two distinct members of ``vertices`` are adjacent in C_n^{box power}."""
    members = set(vertices)
    for shift in strong_power_shifts(n, power):
        for vertex in members:
            moved = tuple((vertex[i] + shift[i]) % n for i in range(power))
            if moved in members:
                return False
    return True


def theta_pattern_is_respected(n: int, matrix) -> bool:
    """The forced entries of the Lovasz matrix: the diagonal and every non-edge."""
    for i in range(n):
        for j in range(n):
            if matrix[i][j] != matrix[j][i]:
                return False
            if i == j or not cycle_adjacent(n, i, j):
                if matrix[i][j] != 1:
                    return False
    return True


def is_positive_definite(matrix) -> bool:
    """Exact rational LDL^T without pivoting; positive definite iff every pivot is positive.

    Unlike the sum-of-squares setting, elimination is affordable here and needs no trust from the
    candidate, because the matrix is not submitted at a size of the candidate's choosing: it is
    ``n x n`` with ``n`` fixed by the instance at 7, 13, 19 or 23, and the entries are capped. The
    work is a few hundred rational operations whose numerators cannot exceed the cap raised to
    the twenty-third power.
    """
    size = len(matrix)
    work = [[Fraction(entry) for entry in row] for row in matrix]
    for k in range(size):
        pivot = work[k][k]
        if pivot <= 0:
            return False
        for i in range(k + 1, size):
            factor = work[i][k] / pivot
            if factor:
                for j in range(k, size):
                    work[i][j] -= factor * work[k][j]
            work[i][k] = Fraction(0)
    return True
