# CoveringDesignBlocks — reference results and anchor confidence

Every score below is produced by running code in this directory.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate solution.py --metrics-out /tmp/baseline.json
python3 frontier_eval/run_eval.py --candidate verification/reference_construction.py --metrics-out /tmp/reference.json
```

## The anchor (best-known, genuinely open, disclosed sourcing gap)

`C(13,7,4)`: La Jolla Covering Repository's explicit best-known cover uses 30 blocks,
known bounds `28 <= C(13,7,4) <= 30`. **Disclosed rather than hidden**: this task's
construction attempted to re-fetch the specific LJCR page directly and the DNS lookup for
`ljcr.dmgordon.org` failed from this environment on 2026-09-06. The value 30 is taken from
a cross-referencing secondary source (HorizonMath's own baselines.json, which cites LJCR
directly and marks it "verified") rather than independently re-confirmed against the live
page. If this number is wrong, whoever next has working access to LJCR should re-verify it
directly. Not proven optimal: a candidate that finds a valid cover with 29 or fewer blocks
would be a genuine, new, checkable record (and one with 28 would settle the open gap).

## Baseline — `solution.py`

A weak randomized greedy: visits candidate 7-subsets in a random order and keeps the first
one that covers at least one currently-uncovered 4-subset (rather than the one covering the
*most*), until every 4-subset is covered.

| num_blocks | score |
|---|---|
| 73 | 0.0000 |

## Reference — `verification/reference_construction.py`

The standard max-gain greedy set-cover algorithm: at each step, picks the 7-subset covering
the most currently-uncovered 4-subsets.

| num_blocks | score |
|---|---|
| 37 | 0.8372 |

Measured directly by running `verification/reference_construction.py` through the oracle
above (runtime under 0.1s). A real, well-known algorithm for set cover, not the
exhaustive/algebraic search behind the published record, and it does not reach that record,
leaving real headroom.

## What this task is not

This task scores the exact, finite, self-contained combinatorial object (a set of 7-blocks
and whether they jointly cover every 4-subset of `{0,...,12}`, checked directly). It does
not ask for, and does not check, the construction or search technique behind the published
record, nor whatever argument establishes the lower bound of 28 -- those are separate,
already-published results this task does not re-derive or re-check.
