# VanDerWaerdenColoring — build a longer AP-free coloring than the published witness

## Scientific setting

Van der Waerden's theorem says: for any number of colors `r` and progression length `k`, there is
a smallest `n` -- the van der Waerden number `W(r,k)` -- such that *every* `r`-coloring of
`{1,...,n}` contains a monochromatic `k`-term arithmetic progression. Equivalently: a valid
`r`-coloring avoiding every monochromatic `k`-term AP can exist only for `n < W(r,k)`, and
`W(r,k) - 1` is the length of the longest such coloring. This is a real, actively worked problem --
only 9 exact van der Waerden numbers have ever been determined (the rest are known only as
best-known lower bounds, found and improved by dedicated SAT-solver search).

## Your task

Implement:

```python
def construct_coloring(r: int, k: int) -> list[int]:
    """Return a list of colors in {0,...,r-1}, of a length you choose, with no monochromatic
    k-term arithmetic progression."""
```

You will be called at `(r,k) = (2,4)`, `(2,5)`, `(2,7)` (2 colors; progression lengths 4, 5, 7).
You choose the length of your coloring -- longer is better, as long as it stays valid. Every entry
must be an integer in `{0,...,r-1}`, and no `k` positions in arithmetic progression (any starting
point, any common difference) may all share the same color. Anything else -- an out-of-range
color, or a monochromatic `k`-term AP anywhere in your coloring -- scores that size zero. Never an
infrastructure failure.

## Evaluation

For each `(r,k)`, `score = (your_n - baseline_n) / (sota_ref_n - baseline_n)`, clipped below at 0
and **unbounded above**:

| (r,k) | baseline length (naive, always valid) | published witness length |
|---|---|---|
| (2,4) | 6 | 34 (= W(2,4) - 1, a proven exact ceiling) |
| (2,5) | 8 | 177 (= W(2,5) - 1, a proven exact ceiling) |
| (2,7) | 12 | 3703 (best-known lower-bound witness; W(2,7) is not yet known exactly) |

`combined_score` is the mean over all three sizes. Matching the published witness length scores
1.0. For `(2,7)`, a longer valid coloring scores above 1.0 -- and would be a genuine, new,
checkable improvement on a still-open lower bound, since the oracle checks your literal submitted
coloring for every arithmetic progression of the given length directly, not a recalled number. For
`(2,4)` and `(2,5)`, `W(r,k)` is a *proven* exact value, so no valid coloring can exceed the listed
length -- this is disclosed rather than hidden; see `references/known_best.md`.

## Available tools and resources

NumPy and the standard library are available. A standard, effective technique: extend the
coloring position by position, and at each new position try colors in some order, keeping the
first one that does not complete a monochromatic `k`-term AP ending there (checked against only
the earlier positions, not the whole array); stop when no color works. Randomized restarts over
the per-position color order typically extend further than a single greedy pass. Backtracking
(undoing recent choices instead of stopping outright) or a real SAT-based search can do
meaningfully better -- the reference construction shipped with this task is a plain randomized
greedy, not that, and it falls well short of the published witness lengths, especially for larger
`k`. Candidate execution is networkless and cannot look anything up.

## Rules and scope

- Only edit `solution.py`; keep `construct_coloring(r, k)`.
- Return a list of ints in `{0,...,r-1}` of whatever length you construct.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

References: V. Chvátal, "Some unknown van der Waerden numbers," *Combinatorial Structures and
Their Applications* (1970), 31-33; R. Stevens, R. Shantaram, "Computer-generated van der Waerden
partitions," *Math. Comp.* 32 (1978), 635-636; J. Rabung, M. Lotts, lower bound `W(2,7) > 3703` via
the "zipper" construction method (see `references/known_best.md` for this task's disclosure of
what could and could not be independently confirmed about this specific attribution).
