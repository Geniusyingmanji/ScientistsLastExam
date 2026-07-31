# CirclePacking — pack unit circles into the smallest square

## Scientific background

**Circle packing** in a square is a classic problem in discrete and computational geometry:
given N unit circles (radius 1), find the arrangement inside a square that minimizes the
square's side length. Optimal configurations are known only for a few small N; for most N
the best-known packings come from computational search (Packomania, E. Specht). The problem
has applications in logistics, materials science, sensor placement, and facility layout.

## Your task

Edit **`solution.py`** so it defines:

```python
def pack_circles(n: int):
    """Return (centers, side) where centers is a list of n (x, y) pairs and side is the
    square side length. Every circle (center (x,y), radius 1) must fit inside [0, side]^2
    and no two circles may overlap (center-to-center distance ≥ 2)."""
```

The evaluator checks validity (no overlap, all inside the box) and measures the side length
against the best-known packing from the Packomania database.

## Scoring

```
score = clip( (side_baseline − side_found) / (side_baseline − side_best_known), 0, 1 )
```

where `side_baseline` is the regular-grid baseline. `combined_score` is the mean over sizes.
Test sizes: N ∈ {7, 10, 13}. Smaller side = better.

## Rules

- Only edit `solution.py`. Keep `pack_circles(n) -> (centers, side)`.
- numpy/stdlib only. CPU, seconds per N. No network.
- Do not read `verification/` or `frontier_eval/`.
