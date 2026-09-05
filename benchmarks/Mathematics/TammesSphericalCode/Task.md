# TammesSphericalCode — spread 15 points on a sphere better than the published record

## Scientific setting

The Tammes problem: place `n` points on the unit sphere `S^2` to maximize the minimum
angular separation between any two of them -- equivalently, minimize the maximum pairwise
dot product (cosine of angle) among the `n` unit vectors. `n=14` was proven optimal by Musin
and Tarasov (2015); `n=15` remains open, and Cohn et al.'s Spherical Codes database lists
the best-known configuration, not proven optimal -- real headroom exists above it.

## Your task

Implement:

```python
def construct_points(n: int) -> list[list[float]]:
    """Return a list of n [x, y, z] points on (or near) the unit sphere."""
```

You will be called at `n = 15`. Points need not already be unit length -- the oracle
normalizes each one -- but must be finite and not (near) the origin. Anything else scores
zero. Never an infrastructure failure.

## Evaluation

`score = (baseline_max_dot - your_max_dot) / (baseline_max_dot - sota_ref)`, clipped below
at 0 and **unbounded above**:

| n | baseline max dot product (naive, always valid) | published best-known max dot product |
|---|---|---|
| 15 | 0.857143 (Fibonacci-sphere spiral) | 0.592606 (Cohn et al., not proven optimal) |

Matching the published record scores 1.0; a smaller maximum dot product (larger minimum
angle) scores above 1.0 -- a real, checkable new record, since the oracle checks every
pairwise dot product in your literal submitted point set directly, not a recalled angle.

## Available tools and resources

NumPy and the standard library are available. A standard, effective technique: start from
several random point sets on the sphere, then repeatedly perturb one randomly-chosen point
by a shrinking random offset (re-normalizing back onto the sphere), keeping the move only
if it strictly lowers the maximum pairwise dot product; repeat with many random restarts.
This gets close to the published record but does not reach it -- a smarter search
(simulated annealing, or a proper global-optimization approach) can do better. Candidate
execution is networkless and cannot look anything up.

## Rules and scope

- Only edit `solution.py`; keep `construct_points(n)`.
- Return exactly `n` `[x, y, z]` triples, finite, not (near) the origin.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

References: H. Cohn et al., "Spherical Codes" (maintained record database,
`https://cohn.mit.edu/spherical-codes/`); O. R. Musin, A. S. Tarasov, "The Tammes problem
for N=14," *Exp. Math.* 24 (2015), 460-468 (proves `n=14` optimal, establishing `n=15` as
the first open case).
