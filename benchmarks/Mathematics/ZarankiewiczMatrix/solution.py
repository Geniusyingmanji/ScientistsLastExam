"""Initial baseline for ZarankiewiczMatrix.

Fills exactly 2 full columns (every row gets a 1 in each of columns 0 and 1) and leaves every
other column all-zero. Since only 2 columns ever contain a 1, no 3 columns can ever be
simultaneously all-ones for any 3 rows -- an s x t = 3x3 all-ones submatrix is structurally
impossible, so this is valid for any m, n >= 2 by construction, with zero search. It wastes almost
all of the matrix: only 2*m ones out of a possible m*n. Edit this file to do better -- a real
search should try to use far more columns while still avoiding any 3-rows-by-3-columns all-ones
block.
"""
from __future__ import annotations


def construct_matrix(m: int, n: int, s: int, t: int):
    """Return an m x n 0/1 matrix (list of lists) with no s x t all-ones submatrix."""
    return [[1 if j < 2 else 0 for j in range(n)] for _ in range(m)]
