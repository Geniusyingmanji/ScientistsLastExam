# SchurPartition — reference results and anchor confidence

Every score below is produced by running code in this directory.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate solution.py --metrics-out /tmp/baseline.json
python3 frontier_eval/run_eval.py --candidate verification/reference_construction.py --metrics-out /tmp/reference.json
```

## Sum-free definition (confirmed, since sources vary on whether a=b counts)

A set is sum-free here if no `a, b, c` in the set (not necessarily distinct -- `a=b` is allowed,
so `2a=c` is forbidden too) satisfy `a + b = c`. This is the standard convention for Schur numbers
(as opposed to *weak* Schur numbers, a separate, larger sequence that only forbids `a != b`).

## The k=4 anchor (proven exact, primary-attributed)

`S(4) = 44` -- S. W. Golomb, L. D. Baumert, "Backtrack Programming," *J. ACM* 12(4) (1965),
516-524, DOI `10.1145/321296.321300`, confirmed directly during this task's construction. A
proven exact value (an explicit sum-free 4-partition of `{1,...,44}`, plus an exhaustive backtrack
search proving no partition of `{1,...,45}` exists): **no valid 4-partition can exceed length 44**
-- disclosed here rather than hidden. `combined_score` has a hard ceiling of 1.0 in practice for
this size specifically, even though the normalization formula itself is the same uncapped form
used throughout this task family.

## The k=6, k=7 anchors (best-known lower bounds, real headroom)

| k | value | status | source |
|---|---|---|---|
| 6 | 536 | best-known lower bound, not proven exact | H. Fredricksen, M. Sweet, *Electron. J. Combin.* 7 (2000), #R32, DOI `10.37236/1510` |
| 7 | 1696 | best-known lower bound, not proven exact | F. Rowley, arXiv:2107.03560 (2021), superseding the older 1680 bound |

Both confirmed unchanged as of a July 2026 paper (arXiv:2607.15034, "Shifted S-templates and
improved lower bounds for Schur numbers"), which explicitly cites 536 and 1696 as the current,
unimproved bounds while improving `S(8)` and `S(13)` instead. Because `S(6)` and `S(7)` are not
proven exact, a candidate that finds a longer valid partition at either size would be a genuine,
new, checkable improvement -- real, uncapped headroom above 1.0.

## Baseline — `solution.py`

A single greedy pass: extends the partition one integer at a time, placing each new integer `x`
into the first part (fixed order `0..k-1`) that does not already contain `a, b` with `a + b = x`;
stops the first time no part works. No backtracking, no restarts.

| k | length | score |
|---|---|---|
| 4 | 15 | 0.0000 |
| 6 | 63 | 0.0000 |
| 7 | 127 | 0.0000 |

## Reference — `verification/reference_construction.py`

Schur's classical doubling construction, applied recursively from the trivial `k=1` partition
`{1}`: each step turns a sum-free `k`-partition of `{1,...,n}` into a sum-free `(k+1)`-partition of
`{1,...,3n+1}` by adding a new part `{n+1,...,2n+1}` and doubling each old part via
`A_i -> A_i union {2n+1+x : x in A_i}`.

| k | length | score |
|---|---|---|
| 4 | 40 | 0.8621 |
| 6 | 364 | 0.6364 |
| 7 | 1093 | 0.6157 |

`combined_score = 0.7047`. Measured directly by running `verification/reference_construction.py`
through the oracle above. This construction matches the true Schur numbers exactly for `k <= 3`
(1, 4, 13) but falls further behind the real records as `k` grows: real headroom is left for a
smarter search (extending an existing good partition element by element with backtracking, or an
actual SAT-based construction of the kind the cited `S(5)`, `S(6)`, `S(7)` papers use).

## What this task is not

This task scores the exact, finite, self-contained combinatorial object (a partition and the
absence of a sum-free violation within each part, checked directly). It does not ask for, and does
not check, the SAT-solver machinery or exhaustive-search proof technique behind how `S(4)` and
`S(5)` were actually established to be exact -- that proof is a fixed, already-published fact this
task assumes, not something a candidate re-derives or that this oracle re-checks.
