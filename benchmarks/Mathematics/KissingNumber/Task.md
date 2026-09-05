# KissingNumber — pack more unit spheres around one sphere

## Scientific background

The kissing number in dimension `d` is how many non-overlapping unit spheres can touch a central
unit sphere. Equivalently: the maximum number of points on the unit sphere with pairwise angular
separation at least 60° (inner product at most `1/2`). Exact values are known only in dimensions
1, 2, 3, 4, 8 and 24. In dimensions 9, 10 and 12 the gap between the best construction and the
best upper bound is still large. Dimension 11 is omitted: recent AI-search claims there are still
contested, and this task is not a venue for re-litigating them.

There is **no required configuration**. Adding one more exactly certified contact in these
dimensions is a record; the score is built to keep climbing.

## Your task

Edit **`solution.py`** so it defines:

```python
def build_kissing(d: int) -> list:
    """Return a list of nonzero length-d vectors. After normalising to the unit sphere,
    every pair of distinct vectors must have inner product at most 1/2."""
```

The evaluator calls it for dimensions 5, 6, 9, 10 and 12, **verifies the 60° condition**, and reads off
the number of distinct directions. Integer vectors are reduced by their positive gcd (`x` and
`2x` count once) and checked exactly (`4⟨x,y⟩² ≤ ||x||²||y||²` whenever `⟨x,y⟩ > 0`). Antipodes
remain distinct kissing points. Exact duplicate vectors are dropped. Zero vectors are rejected.
Non-integral floating witnesses use a `1e-9` angular tolerance, so their acceptance is a
fixed-tolerance numerical benchmark result rather than an exact geometric certificate.

## Scoring

For each dimension, with `baseline = 2d` (the coordinate axes `±e_i`) and `sota` the Cohn-table
lower bound:

```
score(d) = max(0, (|C| − 2d) / (sota − 2d))      # UNCAPPED above
```

So the axis baseline scores 0, matching the published lower bound scores 1.0, and **exceeding it
scores above 1.0**. `combined_score` is the mean over dimensions. Anchors: d=5 (40), d=6 (72),
d=9 (306), d=10 (510), d=12 (841). An invalid set scores 0 for that dimension.

For primitive integer witnesses, a score above 1.0 is backed by exact integer inequalities. For
non-integral floating witnesses, it is a benchmark candidate only: an exact or interval
certificate is required before claiming a scientific kissing-number record.

## Rules

- Only edit `solution.py`; keep the `build_kissing(d)` signature.
- At most 2500 vectors; all finite; no zero vector. `numpy`/stdlib only, CPU.
- Do not describe a floating-witness result as a record without an exact or interval certificate.
- Do not read anything under `verification/` or `frontier_eval/`.
