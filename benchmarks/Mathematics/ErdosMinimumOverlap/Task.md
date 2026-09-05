# ErdosMinimumOverlap — match the exactly-known minimum overlap at three sizes

## Scientific setting

Erdős' minimum overlap problem: partition `{1, ..., 2n}` into two sets `A, B` of size `n`
each. For every integer shift `k`, let `M_k` be the number of pairs `(a, b)` with `a in A`,
`b in B`, and `a - b = k`. Define `M(n) = min` over all such partitions of `max_k M_k` — the
best a partition can do at keeping every difference from being hit too often.

The asymptotic constant `c = lim_{n->inf} M(n)/n` is a live research target: its published
upper bound has been nudged downward repeatedly in 2025-2026 (0.380927 -> 0.380924 by
AlphaEvolve, then further to 0.380876 and 0.380868 by two more search-based methods), each
the first progress on this exact constant since Haugland's 2016 bound. Those results
optimize a continuous density function via Fourier analysis, not a finite partition for
one specific `n` — a genuinely different kind of object from what this task asks for.

What this task asks for instead is the object those bound-improvements are ultimately
about: for `n` small enough that `M(n)` has been determined **exactly** by exhaustive
computer search (known for every `n` up to 15), submit a literal partition and match it.

## Your task

Implement:

```python
def construct_partition(n: int) -> list[int]:
    """Return a list of 2n labels (0 = in A, 1 = in B), n of each."""
```

You will be called at `n = 8`, `11`, `15`. Your list must have length `2n`, contain only
`0`/`1`, and split into exactly `n` zeros and `n` ones. Anything else scores that size
zero. Never an infrastructure failure.

## Evaluation

For each `n`, `score = (baseline_overlap - your_overlap) / (baseline_overlap - sota_ref)`,
clipped below at 0 and **formally unbounded above** (see the caveat below):

| n | baseline max-overlap (naive, always valid) | proven-exact M(n) |
|---|---|---|
| 8 | 8 | 4 |
| 11 | 11 | 5 |
| 15 | 15 | 6 |

`combined_score` is the mean over all three sizes. Matching the exact value scores 1.0.
**Caveat, disclosed rather than hidden**: `M(n)` for these three sizes is a *proven* exact
value (settled by exhaustive search), so no valid partition can score above 1.0 at any of
them — unlike this task's siblings (`ZarankiewiczMatrix`, `DegreeDiameterGraph`), whose
anchors are best-known lower bounds with genuine headroom above 1.0.

## Available tools and resources

NumPy and the standard library are available. A standard, effective technique: start from
a random balanced partition and repeatedly swap one element between `A` and `B` whenever
that strictly lowers `max_k M_k` (hill climbing), with several random restarts, keeping the
best partition found. `max_k M_k` for a whole partition can be computed in one shot via the
cross-correlation of the two sets' indicator vectors (`numpy.correlate`), rather than
looping over every `k` and every pair by hand. This already reaches the exact optimum for
`n=8` and `n=11`, but not for `n=15` — real headroom is left there for a smarter search
(simulated annealing, or exact search exploiting the problem's symmetry). Candidate
execution is networkless and cannot look anything up.

## Rules and scope

- Only edit `solution.py`; keep `construct_partition(n)`.
- Return a list of length `2n` with exactly `n` zeros and `n` ones.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

References: P. Erdős, *Some remarks on number theory* (1955) (original problem); J. K.
Haugland, "The minimum overlap problem revisited," arXiv:1609.08000 (2016 upper bound);
E. P. White, "Erdős' minimum overlap problem," arXiv:2201.05704 (2022 lower bound);
"AlphaEvolve: A coding agent for scientific and algorithmic discovery," arXiv:2506.13131
(2025, first upper-bound progress since 2016); Wikipedia, "Minimum overlap problem" (exact
`M(n)` table for `n<=15` and the current best upper/lower bounds on `c`).
