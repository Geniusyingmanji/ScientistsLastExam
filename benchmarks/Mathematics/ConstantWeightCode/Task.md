# ConstantWeightCode — pack more 5-blocks of {0,...,28} than the published record

## Scientific setting

`A(29,8,5)`: the maximum number of 5-element subsets ("blocks") of `{0,...,28}` such that no
two blocks share more than one point -- equivalently, no unordered pair `{i,j}` appears in
more than one block. This is exactly the binary constant-weight code of length 29, weight
5, minimum Hamming distance `>= 8`. Best-known published lower bound 36 (Bluskov, 2018),
upper bound 39 -- a real, not-yet-closed gap.

## Your task

Implement:

```python
def construct_blocks() -> list[list[int]]:
    """Return a list of 5-element subsets of {0,...,28}. No pair of points may be
    shared by more than one block."""
```

Each block must have exactly 5 distinct entries in `0..28`. No unordered pair of points may
appear together in more than one block. Anything else -- wrong block size, an entry out of
range, a repeated pair -- scores zero. Never an infrastructure failure.

## Evaluation

`score = (your_num_blocks - 5) / (36 - 5)`, clipped below at 0 and **unbounded above**:

| metric | baseline (naive, always valid) | published record |
|---|---|---|
| number of blocks | 5 (disjoint partition) | 36 (Bluskov, 2018) |

Matching the published record scores 1.0; more blocks scores above 1.0 -- a real, checkable
new record, since the oracle checks every pair of points across your literal submitted
blocks directly, not a recalled count.

## Available tools and resources

NumPy and the standard library are available. A standard, effective technique: a
randomized greedy construction -- visit candidate 5-subsets of `{0,...,28}` in a random
order, keeping each one whose pairs are all still unused so far; repeat with several random
orders, keeping the largest code found. This clears the naive disjoint-partition baseline
by a wide margin but does not reach the published record -- a smarter search (or the
algebraic/computer-search construction behind the record) can do better. Candidate
execution is networkless and cannot look anything up.

## Rules and scope

- Only edit `solution.py`; keep `construct_blocks()`.
- Return any number of 5-element subsets of `{0,...,28}` (at most 200), no pair shared by
  more than one block.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

References: I. Bluskov, "New Constant Weight Codes and Packing Numbers," *Electron. Notes
Discrete Math.* 65 (2018), 31-36 (`A(29,8,5) >= 36`); A. Brouwer, "Bounds for binary
constant-weight codes" (maintained table, `https://aeb.win.tue.nl/codes/Andw.html`, upper
bound 39).
