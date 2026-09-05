# ErdosMinimumOverlap — reference results and anchor confidence

Every score below is produced by running code in this directory.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate solution.py --metrics-out /tmp/baseline.json
python3 frontier_eval/run_eval.py --candidate verification/reference_construction.py --metrics-out /tmp/reference.json
```

## The anchors (proven exact, independently re-confirmed)

| n | M(n) | status |
|---|---|---|
| 8 | 4 | proven exact (exhaustive computer search) |
| 11 | 5 | proven exact |
| 15 | 6 | proven exact -- the largest n currently known exactly |

Source: the "Minimum overlap problem" record table on Wikipedia
(`https://en.wikipedia.org/wiki/Minimum_overlap_problem`), independently re-fetched and
confirmed on 2026-09-06, and cross-checked against a from-scratch brute-force search over
all partitions for n=1..6 during this task's construction (matches the table's M(1..6) =
1,1,2,2,3,3 exactly).

**Because these are proven exact values, no valid partition can score above 1.0 at any of
the three sizes** -- disclosed here rather than hidden. `combined_score` has a hard ceiling
of 1.0 in practice for this task, even though the normalization formula itself is the same
uncapped form used throughout this task family. This mirrors the disclosed situation in
`Mathematics/VanDerWaerdenColoring` (2 of 3 sizes) and `Mathematics/SchurPartition` (1 of 3
sizes), except here all three sizes are proven exact -- because M(n) has only ever been
determined exactly for n <= 15, and this task's other two candidate sizes for genuine open
headroom (the asymptotic constant `c`) turn out not to reduce to a finite-`n` partition:
modern improvements to `c`'s upper bound (AlphaEvolve, arXiv:2506.13131; and two 2026
follow-ups) optimize a continuous density function via Fourier analysis and a theorem of
Swinnerton-Dyer, not an explicit partition for one concrete large `n` -- so there is no
real, citable "best-known M(n) for some specific n > 15" to anchor against. This is
disclosed rather than papered over with an invented number.

## Baseline — `solution.py`

Splits `{1,...,2n}` into the first half `A = {1,...,n}` and second half `B = {n+1,...,2n}`.
Always exactly balanced, but the differences concentrate badly.

| n | max-overlap | score |
|---|---|---|
| 8 | 8 | 0.0000 |
| 11 | 11 | 0.0000 |
| 15 | 15 | 0.0000 |

## Reference — `verification/reference_construction.py`

Randomized hill-climbing: 200 restarts from a random balanced partition, each repeatedly
swapping one element between `A` and `B` whenever that strictly lowers `max_k M_k`, until
no single swap helps.

| n | max-overlap | score |
|---|---|---|
| 8 | 4 | 1.0000 |
| 11 | 5 | 1.0000 |
| 15 | 7 | 0.8889 |

`combined_score = 0.9630`. Measured directly by running
`verification/reference_construction.py` through the oracle above. Plain hill-climbing
reaches the true optimum for `n=8` and `n=11` (small enough that the search landscape is
forgiving) but gets stuck at 7 for `n=15` even across 3000 restarts tested during
construction -- the true optimum of 6 requires escaping a local optimum that first-
improvement swaps alone do not find, leaving real (if numerically modest) headroom for a
smarter search (simulated annealing, tabu search, or an exact search exploiting the
problem's structure).

## What this task is not

This task scores the exact, finite, self-contained combinatorial object (a balanced
partition and its maximum difference-overlap, computed by exact cross-correlation). It
does not ask for, and does not check, the Fourier-analytic / convex-optimization machinery
behind the modern improvements to the asymptotic constant `c`'s bounds -- that is separate,
already-published mathematics this task does not re-derive or re-check.
