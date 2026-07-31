# MatrixMultiplicationRank — discover faster matrix-multiplication algorithms

## Scientific background

The number of scalar multiplications needed to multiply two matrices is a fundamental open
problem in algebraic complexity. Strassen (1969) showed 2×2 needs only 7 (not 8); the
exponent of matrix multiplication is still unknown. In 2022–2025, AlphaTensor and AlphaEvolve
discovered new algorithms by searching the space of **bilinear (tensor) decompositions** —
AlphaEvolve found a 4×4 algorithm using **48** scalar multiplications, the first improvement
on Strassen's recursive 49 in over 50 years. Faster matmul speeds up essentially all of
scientific computing and deep learning.

## Formulation

A bilinear algorithm for multiplying `A` (m×n) by `B` (n×p) is a **rank-R decomposition**
`(U, V, W)` of the matrix-multiplication tensor. Writing `a = vec(A)`, `b = vec(B)`,
`c = vec(C)` with the flattening

```
a[i*n + c] = A[i, c],   b[c*p + j] = B[c, j],   c[i*p + j] = C[i, j],
```

the algorithm computes `R` scalar products and combines them:

```
P_r = ( Σ_i U[r, i] · a[i] ) · ( Σ_j V[r, j] · b[j] )      for r = 0 .. R-1
C[k] = Σ_r W[k, r] · P_r
```

`R` (the number of products) is the cost to minimize. Coefficients may be real or complex.

## Your task

Edit **`solution.py`** so it defines:

```python
def build_algorithm(m: int, n: int, p: int):
    """Return (U, V, W) with shapes (R, m*n), (R, n*p), (m*p, R)."""
```

The evaluator calls it for several sizes, **verifies the decomposition is exact** against the
true matmul tensor (and on random integer matrices), and reads off `R`.

## Scoring

For each size, with `R_naive = m·n·p` and `R_sota` the best published count:

```
score(size) = max(0, (R_naive − R_found) / (R_naive − R_sota))      # UNCAPPED above
```

So the naive algorithm scores 0, matching the published best scores 1.0, and **beating it
scores above 1.0**. `combined_score` is the mean over sizes. Sizes evaluated: 2×2×2 (best 7),
3×3×3 (best 23), 4×4×4 (best **48**, AlphaEvolve 2025, over ℂ — recursive Strassen only reaches
49). An invalid/inexact decomposition scores 0 for that size.

## Rules

- Only edit `solution.py`; keep the `build_algorithm(m, n, p)` signature and `(U, V, W)` output.
- The decomposition must be **exact** (verified to 1e-7), not approximate. `numpy` only, CPU,
  seconds. Do not read anything under `verification/` or `frontier_eval/`.
