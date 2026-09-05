# DegreeDiameterGraph — build a bigger bounded-degree, bounded-diameter graph than the published record

## Scientific setting

The degree/diameter problem asks: given a maximum degree `d` and a diameter `k`, what is the
largest graph with max degree `<= d` and diameter `<= k`? The Moore bound
`M(d,k) = 1 + d + d(d-1) + d(d-1)^2 + ... + d(d-1)^(k-1)` upper-bounds it, but the true largest
known graph at almost every `(d,k)` falls well short of that bound and is **not** proven optimal --
a maintained public table (the "Table of the largest known graphs of a given diameter and maximal
degree") just records the largest graph found so far, and most entries have real open headroom.

This is a real, actively worked construction problem. arXiv:2606.15860 ("New lower bounds for the
degree/diameter problem via interaction with a browser-accessible LLM") reports genuinely new
record graphs found this way in 2026 (at larger `(d,k)` pairs than used here: `N(12,5) >= 34992`,
`N(16,5) >= 147456`, both improving prior records). The three sizes in this task use `k=3` and the
current best-known vertex counts from the maintained record table as the score = 1.0 witness;
none of these is proven optimal, so a valid submitted graph with more vertices is a real, new,
checkable improvement on a problem still open today.

## Your task

Implement:

```python
def construct_graph(d: int, k: int) -> list[tuple[int, int]]:
    """Return an edge list [(u, v), ...] with max degree <= d and diameter <= k."""
```

You will be called at `(d,k) = (4,3)`, `(5,3)`, `(6,3)`. Vertex labels must be exactly `0..N-1`
for however many vertices `N` your graph uses (no gaps, no isolated stray labels), no self-loops,
no duplicate edges. Every vertex's degree must be `<= d`, the graph must be connected, and every
pair of vertices must be within `k` hops of each other. Anything else -- a degree violation, a
disconnected graph, or a diameter exceeding `k` -- scores that size zero. Never an infrastructure
failure.

## Evaluation

For each `(d,k)`, `score = (your_N - baseline_N) / (sota_ref_N - baseline_N)`, clipped below at 0
and **unbounded above**:

| (d,k) | baseline vertices (naive, always valid) | current best-known vertices |
|---|---|---|
| (4,3) | 8 | 41 |
| (5,3) | 10 | 72 |
| (6,3) | 12 | 111 |

`combined_score` is the mean over all three sizes. Matching the current record scores 1.0; more
vertices scores above 1.0 -- a real result, since the oracle checks your literal submitted graph
directly (every vertex's degree, and every pairwise distance via breadth-first search), not a
recalled number.

## Available tools and resources

NumPy and the standard library are available. A standard, effective technique: circulant graphs
(vertices `0..n-1`, each connected to `i +/- s (mod n)` for a chosen set of "step" sizes `s`) are
vertex-transitive, so a single breadth-first search from one vertex tells you the whole graph's
diameter -- this lets you search many candidate `n` and step-set combinations quickly. Growing `n`
while randomly trying step sets, keeping the largest `n` that stays within diameter `k`, already
beats the naive baseline by a wide margin but does not reach the published record -- the record
constructions use structured algebraic designs (voltage graphs, specific group-theoretic
constructions) or dedicated computer search, which is real headroom for a stronger policy to close.
Candidate execution is networkless and cannot look anything up.

## Rules and scope

- Only edit `solution.py`; keep `construct_graph(d, k)`.
- Return an edge list using vertex labels `0..N-1` with no gaps.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

References: R. Mizuno, "New lower bounds for the degree/diameter problem via interaction with a
browser-accessible LLM," arXiv:2606.15860; "Table of the largest known graphs of a given diameter
and maximal degree" (maintained community record table, citing J. G. Allwright (1992) for `(4,3)`
and G. Exoo (1998-2010) for `(5,3)` and `(6,3)`); M. Miller, J. Širáň, "Moore graphs and beyond: A
survey of the degree/diameter problem," *Electron. J. Combin.*, Dynamic Survey DS14.
