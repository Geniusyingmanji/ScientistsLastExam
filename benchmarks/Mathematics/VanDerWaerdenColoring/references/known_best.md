# VanDerWaerdenColoring — reference results and anchor confidence

Every score below is produced by running code in this directory.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate solution.py --metrics-out /tmp/baseline.json
python3 frontier_eval/run_eval.py --candidate verification/reference_construction.py --metrics-out /tmp/reference.json
```

## A convention note (disclosed because sources disagree on letter order)

Wikipedia and MathWorld both write the van der Waerden number as `W(r, k)` with `r` = number of
colors **first**, `k` = AP length **second** -- this task's own function signature
`construct_coloring(r, k)` matches that order, but is spelled out explicitly here (and in
`Task.md`) rather than relied on from the letters alone.

## The k=4, k=5 anchors (proven exact, primary-attributed, independently re-fetched)

| k (AP length) | r (colors) | W(r,k) | witness length used here (W-1) | attribution |
|---|---|---|---|---|
| 4 | 2 | 35 | 34 | Chvátal (1970) |
| 5 | 2 | 178 | 177 | Stevens & Shantaram (1978) |

Both are **exact, proven** van der Waerden numbers -- 2 of only 9 exact values ever determined.
Independently re-confirmed by direct fetch of `https://en.wikipedia.org/wiki/Van_der_Waerden_number`
on 2026-09-05. **Because these are exact values, a valid coloring cannot exceed the listed length
without contradicting a proven theorem** -- disclosed here rather than hidden: `combined_score`
has a hard ceiling of 1.0 in practice for these two sizes specifically, even though the
normalization formula itself is the same uncapped form used throughout this task family.

## The k=7 anchor (best-known lower bound, real headroom, secondary-sourced attribution)

`W(2,7) > 3703` (not yet proven exact). This is a real, currently-open lower bound: a candidate
that submits a longer valid 2-coloring avoiding every monochromatic 7-term AP would be a genuine,
new, checkable improvement. Attributed to J. Rabung and M. Lotts via the "zipper" construction
method, and confirmed consistently across three independent lookups during this task's
construction (a broader research pass, a direct raw-table transcription of Wikipedia's own
lower-bounds table, and a separate web search) -- but this task could not locate a stable
primary-source URL for the original Rabung-Lotts paper itself. This is disclosed rather than
asserted with unearned confidence, the same disclosure pattern used for the k=54 anchor in
`Mathematics/NarrowAdmissibleTuple`.

## Baseline — `solution.py`

Splits `{0,...,r*(k-1)-1}` into `r` consecutive blocks of `(k-1)` elements each, one color per
block. Every color is used exactly `k-1` times total, so no color can ever contain `k` elements at
all, let alone `k` in arithmetic progression -- valid by construction, zero search.

| (r,k) | length | score |
|---|---|---|
| (2,4) | 6 | 0.0000 |
| (2,5) | 8 | 0.0000 |
| (2,7) | 12 | 0.0000 |

## Reference — `verification/reference_construction.py`

Randomized greedy: extends the coloring position by position, at each step trying colors in a
random order and keeping the first one that does not complete a monochromatic `k`-term AP ending
there (checked incrementally); 30 randomized restarts, keeping the longest coloring found.

| (r,k) | length | score |
|---|---|---|
| (2,4) | 27 | 0.7500 |
| (2,5) | 55 | 0.2781 |
| (2,7) | 185 | 0.0469 |

`combined_score = 0.3583`. Measured directly by running `verification/reference_construction.py`
through the oracle above. The greedy does comparatively well for the smallest AP length (`k=4`)
but falls sharply behind for `k=7`, where the true witness (3703) is a dedicated
construction-method result far beyond what plain greedy extension reaches -- exactly the gap a
stronger search (backtracking, or an actual zipper/SAT-based construction) would need to close.

## What this task is not

This task scores the exact, finite, self-contained combinatorial object (a coloring and the
absence of a monochromatic `k`-term AP within it, checked directly). It does not ask for, and does
not check, the general theory behind van der Waerden's theorem itself (the compactness/
combinatorial-line argument that guarantees some finite `W(r,k)` exists for every `r,k`) -- that
is a fixed, already-published mathematical fact this task assumes, not something a candidate
re-derives or that this oracle re-checks.
