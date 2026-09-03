# RamseyLowerBound — construct larger (s,t)-Ramsey colorings

## Scientific background

The Ramsey number `R(s, t)` is the smallest `n` such that every 2-coloring of the edges of `K_n`
contains a red `K_s` or a blue `K_t`. Lower bounds come from **explicit colorings**: a coloring
of `K_n` with no red `K_s` and no blue `K_t` proves `R(s, t) ≥ n + 1`.

`R(5, 5)` is the emblematic open case. Since Exoo (1989) there has been a coloring of 42 vertices
with no monochromatic `K_5`, so `R(5, 5) ≥ 43`; the upper bound is now 46 (Angeltveit–McKay).
Nobody has published a 43-vertex coloring in the decades since. `R(4, 6) ≥ 36` is the same kind
of construction problem on a different pair. There is **no required solution**. A coloring larger
than the published witness is a paper; the score is built to keep climbing.

## Your task

Edit **`solution.py`** so it defines:

```python
def build_coloring(s: int, t: int):
    """Return an n x n array. 0 = red, 1 = blue, diagonal 0, symmetric."""
```

The evaluator calls it for the pairs `(s, t)` below, **checks there is no red `K_s` and no blue
`K_t`**, and reads off `n`. Bigger valid colorings score higher.

## Scoring

For each pair, with `baseline` the complete-bipartite coloring of order `2(t − 1)` (red between
the parts, blue inside them) and `sota` the published construction order:

```
score(s, t) = max(0, (n − baseline) / (sota − baseline))      # UNCAPPED above
```

So the bipartite baseline scores 0, matching the published witness scores 1.0, and **exceeding it
scores above 1.0**. `combined_score` is the mean over pairs. Pairs evaluated: `(5, 5)` (witness
n=42, Exoo) and `(4, 6)` (witness n=35, Exoo). An invalid coloring (asymmetric, values outside
`{0, 1}`, `n` above the checker cap, or a monochromatic clique) scores 0 for that pair.

## Rules

- Only edit `solution.py`; keep the `build_coloring(s, t)` signature.
- Colorings must be square, symmetric, zero-diagonal, entries in `{0, 1}`.
  `n` at most 50 for `(5, 5)` and 42 for `(4, 6)` (checker budget; the published upper bounds
  are 46 and 41).
- `numpy`/stdlib only, CPU. Do not read anything under `verification/` or `frontier_eval/`.
