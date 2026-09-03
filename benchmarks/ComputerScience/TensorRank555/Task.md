# TensorRank555 — numerical complex decompositions for 5×5 and 6×6 multiplication

## Scientific background

The number of scalar multiplications needed to multiply two matrices is a fundamental open
problem in algebraic complexity. This repository already scores `<2,2,2>`, `<3,3,3>` and
`<4,4,4>`. Those cells are a different task. Here the tensors are **new sizes**:
`⟨5,5,5⟩` and `⟨6,6,6⟩`. Moosbauer–Poole (ISSAC 2025) give exact constructions of
ranks 93 and 153 over arbitrary ground fields. This task instead accepts finite real or
complex coefficients and checks them at a fixed numerical tolerance. The published exact
ranks are contextual normalization anchors, not claims that this verifier certifies the same
mathematical object. There is **no required algorithm**.

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

The evaluator calls it for `<5,5,5>` and `<6,6,6>`, verifies tensor reconstruction to the
published numerical tolerance (and checks random integer matrices), and reads off `R`.

## Scoring

For each size, with `R_naive = m·n·p` and `R_anchor` the published exact count:

```
score(size) = max(0, (R_naive − R_found) / (R_naive − R_anchor))      # UNCAPPED above
```

So the naive algorithm scores 0, a numerically accepted decomposition at the anchor count
scores 1.0, and a smaller accepted decomposition scores above 1.0. `combined_score` is the
mean over sizes. An invalid decomposition scores 0 for that size. Because acceptance is
numerical, even a score above 1.0 is only a candidate result for this benchmark. A claim about
exact tensor rank or a new algebraic-complexity record additionally requires an exact
rational, integer, or independently checkable symbolic certificate.

## Rules

- Only edit `solution.py`; keep the `build_algorithm(m, n, p)` signature and `(U, V, W)` output.
- The decomposition must reconstruct the complex-valued tensor within `1e-7`; this is a
  deterministic numerical verifier, not a formal exact-arithmetic certificate. `numpy` only, CPU.
- Do not describe a numerically accepted result as an exact or arbitrary-field rank record.
- Do not read anything under `verification/` or `frontier_eval/`.
