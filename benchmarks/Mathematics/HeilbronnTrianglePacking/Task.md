# HeilbronnTrianglePacking — beat the published record for well-spread points in a square

## Scientific setting

The Heilbronn triangle problem: place `n` points in the closed unit square `[0,1]^2` to
maximize the minimum area of any triangle formed by 3 of them. This is a classic problem
(posed in the 1950s) that is still actively worked today: Erich's Packing Center maintains
a record table for every `n` up to 16, but only `n=5` through `n=9` have ever been *proven*
optimal by computer-assisted proof -- most recently `n=9`, settled by Sudermann-Merx in
March 2026. Everything from `n=10` up is best-known-only, with real headroom above it.
AlphaEvolve (arXiv:2506.13131) found new records on several *variants* of this problem in
2026 (different regions: an equilateral triangle, general convex regions) but did not beat
the classic unit-square records used here -- a sign of just how hard even a few extra
points still are on this specific, most-studied version.

## Your task

Implement:

```python
def construct_points(n: int) -> list[list[float]]:
    """Return a list of n [x, y] points, each with x, y in [0, 1]."""
```

You will be called at `n = 8`, `10`, `11`. Every coordinate must lie in `[0, 1]`. Anything
else (wrong count, out-of-range or non-finite coordinates) scores that size zero. Never an
infrastructure failure.

## Evaluation

For each `n`, `score = (your_min_area - baseline) / (sota_ref - baseline)`, clipped below
at 0 and **unbounded above**:

| n | baseline min-area (naive, always valid) | published record min-area |
|---|---|---|
| 8 | 0.05178 | 0.07238 (= (sqrt(13)-1)/36, proven optimal, Dehbi & Zeng 2022) |
| 10 | 0.02806 | 0.04654 (best-known only) |
| 11 | 0.02146 | 0.03704 (= 1/27, best-known only) |

`combined_score` is the mean over all three sizes. Matching the published record scores
1.0. At `n=10` and `n=11` (best-known only, not proven optimal), a configuration with a
larger minimum triangle area scores above 1.0 -- a real, checkable new record, since the
oracle checks every one of the `C(n,3)` triangles in your literal submitted point set
directly, not a recalled number. At `n=8` (proven optimal), exceeding 1.0 is mathematically
impossible -- disclosed rather than hidden; see `references/known_best.md`.

## Available tools and resources

NumPy and the standard library are available. A standard, effective technique: start from
several random point sets, then repeatedly perturb one randomly-chosen point by a shrinking
random offset, keeping the move only when it strictly increases the minimum triangle area
(hill climbing with an annealed step size); repeat with many random restarts, keeping the
best result. This clears the naive baseline by a wide margin but falls well short of the
published records, especially at `n=11` -- a smarter search (simulated annealing that
occasionally accepts a worse move, or a proper global-optimization / mixed-integer approach
of the kind the cited certified-optimal papers use) can do meaningfully better. Candidate
execution is networkless and cannot look anything up.

## Rules and scope

- Only edit `solution.py`; keep `construct_points(n)`.
- Return exactly `n` `[x, y]` pairs with coordinates in `[0, 1]`.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

References: L. Dehbi, Z. Zeng, certified-optimal `n=8` configuration (2022, cited via
Erich's Packing Center); N. Sudermann-Merx, certified-optimal `n=9` configuration (March
2026, cited via Erich's Packing Center); Erich Friedman, "Heilbronn's Triangle Problem"
(Erich's Packing Center, the maintained record table for `n<=16`, `https://erich-friedman.github.io/packing/heilbronn/`);
"AlphaEvolve: A coding agent for scientific and algorithmic discovery," arXiv:2506.13131
(2026 new records on Heilbronn variants, motivating context for this task, not a task
anchor since those variants use different regions).
