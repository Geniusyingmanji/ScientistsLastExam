# ZarankiewiczMatrix — build a denser K3,3-free 0/1 matrix than the published record

## Scientific setting

The Zarankiewicz number `z(m,n;s,t)` is the maximum number of 1-entries a 0/1 matrix with `m`
rows and `n` columns can have while containing no `s x t` all-ones submatrix -- no choice of `s`
rows and `t` columns (not necessarily contiguous) that are all 1 simultaneously. Equivalently: the
maximum number of edges a bipartite graph with parts of size `m, n` can have with no complete
bipartite subgraph `K_{s,t}`.

This is a real, actively worked extremal graph theory problem. arXiv:2605.01120 ("New Bounds for
Zarankiewicz Numbers via Reinforced LLM Evolutionary Search") used **OpenEvolve** -- an LLM-guided
evolutionary search backend this repository natively supports (`--algorithm openevolve`) -- to
find the first exact values of `z(11,21;3,3)=116`, `z(11,22;3,3)=121`, `z(12,22;3,3)=132`, and new
lower bounds for 41 more cases. A follow-up, arXiv:2608.26603 ("Five improved lower bounds for
Zarankiewicz numbers z(m,n;3,3)"), pushed several of those lower bounds further. The three sizes
in this task use the most recent published lower bound as the score = 1.0 witness; none of them
has a matching upper-bound proof, so a valid submitted matrix with more 1-entries is a real, new,
checkable improvement on a problem still open today.

## Your task

Implement:

```python
def construct_matrix(m: int, n: int, s: int, t: int) -> list[list[int]]:
    """Return an m x n 0/1 matrix (list of lists) with no s x t all-ones submatrix."""
```

You will be called at `(m,n,s,t) = (13,19,3,3)`, `(14,19,3,3)`, `(16,18,3,3)`. Your matrix must
have exactly `m` rows and `n` columns of `0`/`1` entries, and no 3 rows and 3 columns may all be 1
simultaneously. Anything else -- wrong shape, non-binary entries, or a `3x3` all-ones submatrix --
scores that size zero. Never an infrastructure failure.

## Evaluation

For each size, `score = (your_ones - baseline_ones) / (sota_ref_ones - baseline_ones)`, clipped
below at 0 and **unbounded above**:

| (m,n,s,t) | baseline ones (naive, always valid) | published record ones (lower bound) |
|---|---|---|
| (13,19,3,3) | 26 | 118 |
| (14,19,3,3) | 28 | 126 |
| (16,18,3,3) | 32 | 136 |

`combined_score` is the mean over all three sizes. Matching the published record scores 1.0; a
matrix with strictly more 1-entries scores above 1.0 -- a real result, since the oracle checks
your literal submitted matrix directly (every 3-row-by-3-column combination), not a recalled
number.

## Available tools and resources

NumPy and the standard library are available. A standard, effective technique: greedily fill
cells in some order, checking after each tentative 1 whether it creates a `3x3` all-ones block
with any two other rows (an incremental check, far cheaper than rechecking the whole matrix); keep
the densest valid matrix across several randomized cell orders. Local search after a greedy pass
(swap or add/remove a handful of cells to escape a locally-stuck configuration) or an actual
evolutionary/SAT-based search can do meaningfully better -- the reference construction shipped
with this task is a plain randomized greedy, not that. Candidate execution is networkless and
cannot look anything up.

## Rules and scope

- Only edit `solution.py`; keep `construct_matrix(m, n, s, t)`.
- Return exactly an `m x n` list of lists of `0`/`1` integers.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

References: J. Bhan, N. Nobili, P. Langer, "New Bounds for Zarankiewicz Numbers via Reinforced LLM
Evolutionary Search," arXiv:2605.01120; A. Saurabh, "Five improved lower bounds for Zarankiewicz
numbers z(m,n;3,3)," arXiv:2608.26603; T. Kővári, V. T. Sós, P. Turán, "On a problem of K.
Zarankiewicz," *Colloq. Math.* 3 (1954), 50-57.
