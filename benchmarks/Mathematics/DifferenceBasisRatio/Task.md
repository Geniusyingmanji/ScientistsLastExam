# DifferenceBasisRatio — build a difference basis beating the published ratio bound

## Scientific setting

For a natural number `n`, let `Delta(n)` be the size of the smallest set `B` of integers
such that every `k` in `{1,...,n}` is expressible as `|a-b|` for some `a, b` in `B` (a
"difference basis" for `{1,...,n}`). Define `C(n) := Delta(n)^2 / n` and
`C := inf_{n>=1} C(n)`. This constant's published upper bound was pushed from `2.6571` to
`2.6390` by AlphaEvolve in 2025 (arXiv:2511.02864) -- the first improvement in years, and a
genuinely open target: each improvement is a real, explicit difference basis at some `n`,
not merely an existence argument.

## Your task

Implement:

```python
def construct_basis(hint_n: int) -> dict:
    """Return {"n": n, "basis": [b0, b1, ...]}: a difference basis covering every
    k in {1,...,n}. You may return any n you like -- hint_n is only a suggested scale."""
```

You will be called with three different `hint_n` values (500, 2000, 10000), but you are
free to return any positive `n` and any valid basis for it -- the constant `C` is defined
as an infimum over *every* `n`, so a good basis at any scale counts. Your `basis` must be a
list of distinct integers (positive, negative, or zero) whose span (`max - min`) is at most
5 times your chosen `n`. Anything else -- wrong types, duplicate entries, a basis that
fails to cover some `k` in `1..n` -- scores that call zero. Never an infrastructure failure.

## Evaluation

For each call, `ratio = len(basis)**2 / n`, and
`score = (baseline_ratio - ratio) / (baseline_ratio - 2.6390)`, clipped below at 0 and
**unbounded above**:

| hint_n | baseline ratio (naive, always valid) | published ratio bound |
|---|---|---|
| 500 | 12.168 | 2.6390 |
| 2000 | 12.168 | 2.6390 |
| 10000 | 12.3201 | 2.6390 |

`combined_score` is the mean over all three calls. Matching the published bound scores
1.0; a smaller ratio scores above 1.0 -- a real, checkable improvement on the constant `C`,
since the oracle checks your literal submitted basis directly (every difference `1..n`),
not a recalled ratio.

## Available tools and resources

NumPy and the standard library are available. A standard, effective technique ("two-level"
basis): take `{0,...,k-1}` (covers every small difference `1..k-1` directly), its negatives
`{-(k-1),...,-1}`, and the multiples `{0,k,2k,...}` up to `n` (covers every multiple of `k`,
and every multiple-of-k-plus-small-remainder by combining one element from each part).
Searching over `k` for the smallest valid basis, then pruning any element whose removal
still leaves every difference covered, does meaningfully better than a single fixed `k` --
but still falls well short of the published bound. Candidate execution is networkless and
cannot look anything up.

## Rules and scope

- Only edit `solution.py`; keep `construct_basis(hint_n)`.
- Return `{"n": n, "basis": [...]}` with `n > 0` and distinct integer basis entries.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

References: "AlphaEvolve: A coding agent for scientific and algorithmic discovery,"
arXiv:2506.13131; B. Georgiev, J. Gómez-Serrano, T. Tao, A. Z. Wagner, "Mathematical
exploration and discovery at scale," arXiv:2511.02864 (the 2.6390 bound, Section 3,
"Difference bases").
