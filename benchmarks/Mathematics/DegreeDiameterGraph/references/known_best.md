# DegreeDiameterGraph — reference results and anchor confidence

Every score below is produced by running code in this directory.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate solution.py --metrics-out /tmp/baseline.json
python3 frontier_eval/run_eval.py --candidate verification/reference_construction.py --metrics-out /tmp/reference.json
```

## The anchors (aggregator table, sourced to primary literature, independently re-fetched)

The "Table of the largest known graphs of a given diameter and maximal degree" is a maintained
community record table for the degree/diameter problem. Its `combinatoricswiki.org` original
returned a TLS certificate error during this task's construction; its actively-maintained Wikipedia
mirror (same underlying data lineage, citing the same primary sources) was fetched directly and
independently re-confirmed on 2026-09-05:

| d | k | best-known vertices | cited construction | proven optimal? |
|---|---|---|---|---|
| 4 | 3 | 41 | J. G. Allwright (1992) | no -- largest found so far |
| 5 | 3 | 72 | Geoffrey Exoo (1998-2010) | no -- largest found so far |
| 6 | 3 | 111 | Geoffrey Exoo (1998-2010) | no -- largest found so far |

None of these three is proven optimal (the Moore bound is 53, 106, 187 respectively -- see below),
so real headroom exists: a candidate that finds a valid graph with even one more vertex at these
exact `(d,k)` would be a genuine, new, checkable record.

For scientific motivation (not used as a task anchor, since the sizes are much larger and too
expensive to verify per-call): R. Mizuno, "New lower bounds for the degree/diameter problem via
interaction with a browser-accessible LLM," arXiv:2606.15860, reports `N(12,5) >= 34992` and
`N(16,5) >= 147456`, both improving prior records -- direct 2026 precedent that LLM-guided search
makes genuine new progress on exactly this construction problem.

## Moore bound (context, not a task anchor)

`M(d,k) = 1 + d + d(d-1) + ... + d(d-1)^(k-1)`. For `k=3`: `M(4,3)=53`, `M(5,3)=106`, `M(6,3)=187`
-- the best-known graphs above sit at 77%, 68%, and 59% of the Moore bound respectively, leaving
substantial theoretical headroom even beyond the current record.

## Baseline — `solution.py`

The "central-edge double tree": two roots joined by one edge, each growing a `(d-1)`-ary tree of
depth 1. Diameter is exactly 3 by construction (leaf -> root -> root -> leaf), valid with zero
search.

| (d,k) | vertices | score |
|---|---|---|
| (4,3) | 8 | 0.0000 |
| (5,3) | 10 | 0.0000 |
| (6,3) | 12 | 0.0000 |

## Reference — `verification/reference_construction.py`

Searches circulant graphs (vertices `0..n-1` connected by a chosen set of step sizes `s`, each
vertex linked to `i +/- s mod n`): scans `n` upward from just past the baseline, trying up to 60
random step sets per `n` (using the vertex-transitivity of circulant graphs to check diameter with
a single BFS instead of one per vertex), and keeps the largest `n` for which some trial stays
within diameter `k`.

| (d,k) | vertices | score |
|---|---|---|
| (4,3) | 25 | 0.5152 |
| (5,3) | 36 | 0.4194 |
| (6,3) | 49 | 0.3737 |

`combined_score = 0.4361`. Measured directly by running `verification/reference_construction.py`
through the oracle above. Circulant graphs are a real, standard technique in degree/diameter
research, not the literal algebraic or computer-search construction behind the published records
(which use structured designs such as voltage graphs) -- real headroom is left for a stronger,
more targeted construction or search.

## What this task is not

This task scores the exact, finite, self-contained combinatorial object (a graph's degree
sequence and its diameter, computed by breadth-first search). It does not ask for, and does not
check, the general theory of the degree/diameter problem (the Moore bound derivation, or the
voltage-graph/lifting machinery behind the strongest known constructions) -- that body of theory
is a fixed, already-published mathematical context this task assumes, not something a candidate
re-derives or that this oracle re-checks.
