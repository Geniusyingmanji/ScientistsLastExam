# CapSetFrontier — large cap sets in dimensions that are still open

## Scientific background

A **cap set** is a subset of `Z_3^n` containing no three distinct points on a line —
equivalently, no three distinct `x, y, z` with `x + y + z ≡ 0 (mod 3)`. Maximum sizes for
`n ≤ 6` are proven; those dimensions are a different task (`Mathematics/CapSet`) and cannot
be improved. This task is the remaining FunSearch frontier: **n = 7, 8, 9**, where the
maximum is not proven. FunSearch found size 512 in dimension 8; the listed records for n=7
and n=9 are 236 and 1082. There is **no required cap**. A larger verified set in any of
these dimensions is a paper; the score is built to keep climbing.

## Your task

Edit **`solution.py`** so it defines:

```python
def build_capset(n: int) -> list:
    """Return a list of vectors in {0,1,2}^n forming a cap set (no 3 distinct collinear)."""
```

The evaluator calls it for n=7, 8, 9, **verifies the cap property**, and reads off `|S|`.
Bigger valid caps score higher.

## Scoring

For each dimension, with `baseline = 2^n` (the trivial `{0,1}^n` cap) and `sota` the best
known size:

```
score(n) = max(0, (|S| − 2^n) / (sota − 2^n))      # UNCAPPED above
```

So the `{0,1}^n` baseline scores 0, matching the known record scores 1.0, and **exceeding it
scores above 1.0**. `combined_score` is the mean over dimensions. An invalid set (any
collinear triple) scores 0 for that dimension.

## Rules

- Only edit `solution.py`; keep the `build_capset(n)` signature and list-of-vectors output.
- Vectors must have entries in `{0,1,2}` and length `n`; duplicates are de-duplicated.
- At most 2500 vectors after de-duplication. `numpy`/stdlib only, CPU.
- Do not read anything under `verification/` or `frontier_eval/`.
