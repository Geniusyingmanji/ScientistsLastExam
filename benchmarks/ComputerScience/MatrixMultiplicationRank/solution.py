"""Initial baseline for MatrixMultiplicationRank (the naive algorithm).

Returns the trivial rank-(m*n*p) decomposition: one scalar multiplication per (i, c, j)
triple, i.e. the schoolbook algorithm. It is exact but uses the maximum number of
multiplications, so it scores 0. Edit this file to emit a lower-rank bilinear algorithm
(e.g. Strassen for 2x2, Laderman for 3x3, recursive Strassen for 4x4, or better).
"""

import numpy as np


def build_algorithm(m: int, n: int, p: int):
    """Return (U, V, W) with shapes (R, m*n), (R, n*p), (m*p, R).

    Convention: a[i*n+c]=A[i,c], b[c*p+j]=B[c,j], c[i*p+j]=C[i,j].
    Algorithm: P_r = (U[r]·a)(V[r]·b);  C_k = sum_r W[k,r] P_r.
    """
    R = m * n * p
    U = np.zeros((R, m * n))
    V = np.zeros((R, n * p))
    W = np.zeros((m * p, R))
    r = 0
    for i in range(m):
        for c in range(n):
            for j in range(p):
                U[r, i * n + c] = 1.0
                V[r, c * p + j] = 1.0
                W[i * p + j, r] = 1.0
                r += 1
    return U, V, W
