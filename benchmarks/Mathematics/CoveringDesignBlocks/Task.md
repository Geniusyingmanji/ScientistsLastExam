# CoveringDesignBlocks — cover C(13,7,4) with fewer blocks than the published record

## Scientific setting

The covering design `C(13,7,4)`: a collection of 7-element blocks of `{0,...,12}` such that
every 4-element subset is contained in at least one block. The objective is to use as few
blocks as possible. The La Jolla Covering Repository's explicit best-known cover uses 30
blocks (`28 <= C(13,7,4) <= 30`) -- a lower-bound-style record without a matching
achievability proof at 28, so real headroom exists.

## Your task

Implement:

```python
def construct_blocks() -> list[list[int]]:
    """Return a list of 7-element subsets of {0,...,12} covering every 4-element
    subset of {0,...,12}."""
```

Each block must have exactly 7 distinct entries in `0..12`, and every one of the `C(13,4)`
4-element subsets of `{0,...,12}` must be contained in at least one block. Anything else --
wrong block size, an entry out of range, a subset left uncovered -- scores zero. Never an
infrastructure failure.

## Evaluation

`score = (73 - your_num_blocks) / (73 - 30)`, clipped below at 0 and **unbounded above**:

| metric | baseline (naive, always valid) | published record |
|---|---|---|
| number of blocks | 73 (weak randomized greedy) | 30 (La Jolla Covering Repository) |

Matching the published record scores 1.0; fewer blocks scores above 1.0 -- a real,
checkable new record, since the oracle checks coverage of every one of the `C(13,4)`
4-subsets against your literal submitted blocks directly, not a recalled count.

## Available tools and resources

NumPy and the standard library are available. A standard, effective technique: the
max-gain greedy set-cover algorithm -- at each step, pick the 7-subset covering the most
currently-uncovered 4-subsets (not just the first one that helps, unlike the naive
baseline), until every 4-subset is covered. This is the standard, well-known greedy
algorithm for set cover and does substantially better than picking blocks in a fixed or
random "first improvement" order, but it does not reach the published record -- a smarter
search (or the exhaustive/algebraic construction behind the record) can do better. Candidate
execution is networkless and cannot look anything up.

## Rules and scope

- Only edit `solution.py`; keep `construct_blocks()`.
- Return any number of 7-element subsets of `{0,...,12}` (at most 500) covering every
  4-subset.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

References: La Jolla Covering Repository (maintained record database,
`https://ljcr.dmgordon.org/`), entry `C(13,7,4)`.
