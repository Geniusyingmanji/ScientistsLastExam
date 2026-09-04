"""Truth-blind reference for NonlinearCodeRecords: the largest linear code, by greedy parity check.

Reads only n and d. A binary linear code has minimum distance at least d exactly when every d-1
columns of its parity check are independent, so the construction is to grow a column set over
F_2^r in which no column is a sum of at most d-2 of the others, taking the smallest r that admits
n columns, and then read off the nullspace. Under a second for every instance here.

**This is the whole of the standard toolkit, and it is deliberately not the record.** Every
published record at these parameters is held by a *nonlinear* code - the Kerdock and Preparata
families and long computer searches - and linear codes stop between a fifth and a half short:
64 against 80 at (23, 10), 64 against 136 at (24, 10), 128 against 192, 256 against 384. Leaving
linearity is the headroom, and it is not a small step: a union of cosets, the obvious first attempt,
cannot even start here, because the covering radius of these codes is below d and so no coset
representative sits far enough from the code to be admissible.
"""
from __future__ import annotations

import numpy as np


def _parity_check_columns(n, d):
    for r in range(2, n + 1):
        by_size = [{0}] + [set() for _ in range(d - 2)]
        columns = []
        for value in range(1, 1 << r):
            if len(columns) >= n:
                break
            if any(value in level for level in by_size):
                continue
            for j in range(len(by_size) - 1, 0, -1):
                by_size[j] |= {previous ^ value for previous in by_size[j - 1]}
            columns.append(value)
        if len(columns) >= n:
            return columns, r
    return [], n


def linear_code(n, d):
    columns, r = _parity_check_columns(n, d)
    if not columns:
        return np.zeros((1, n), dtype=np.uint8)
    matrix = [[(col >> bit) & 1 for col in columns] for bit in range(r)]
    pivots, row = [], 0
    for col in range(n):
        pivot = next((i for i in range(row, r) if matrix[i][col]), None)
        if pivot is None:
            continue
        matrix[row], matrix[pivot] = matrix[pivot], matrix[row]
        for i in range(r):
            if i != row and matrix[i][col]:
                matrix[i] = [a ^ b for a, b in zip(matrix[i], matrix[row])]
        pivots.append(col)
        row += 1
        if row == r:
            break
    basis = []
    for free in [c for c in range(n) if c not in pivots]:
        vector = np.zeros(n, dtype=np.uint8)
        vector[free] = 1
        for index, col in enumerate(pivots):
            vector[col] = matrix[index][free]
        basis.append(vector)
    words = np.zeros((1, n), dtype=np.uint8)
    for vector in basis:
        words = np.vstack([words, words ^ vector])
    return words


def build_code(n, d):
    return linear_code(n, d).tolist()
