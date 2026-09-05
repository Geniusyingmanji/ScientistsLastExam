# SchurPartition — build a longer sum-free k-partition than the published record

## Scientific setting

The Schur number `S(k)` is the largest `n` such that `{1,...,n}` can be partitioned into `k`
sum-free sets -- sets containing no `a, b, c` (`a, b, c` need not be distinct, so `a=b` is allowed)
with `a + b = c`. This is a real, actively worked problem: only `S(1)` through `S(5)` have ever
been determined exactly, the most recent by a 200-terabyte SAT-solver proof in 2017 ("Schur
Number Five"); `S(6)` and `S(7)` are known only as best-known lower bounds, kept current by
dedicated search.

## Your task

Implement:

```python
def construct_partition(k: int) -> list[int]:
    """Return a list of part indices in {0,...,k-1}, one per element 1..n (for an n you choose),
    such that every part is sum-free."""
```

You will be called at `k = 4`, `6`, `7`. You choose the length `n` of your partition -- longer is
better, as long as it stays valid: every part index must be in `{0,...,k-1}`, and no part may
contain `a, b, c` (with `a=b` allowed) satisfying `a + b = c`. Anything else -- an out-of-range
part index, or a sum-free violation in any part -- scores that size zero. Never an infrastructure
failure.

## Evaluation

For each `k`, `score = (your_n - baseline_n) / (sota_ref_n - baseline_n)`, clipped below at 0 and
**unbounded above**:

| k | baseline length (naive, always valid) | published witness length |
|---|---|---|
| 4 | 15 | 44 (= S(4), a proven exact ceiling) |
| 6 | 63 | 536 (best-known lower bound; S(6) is not yet known exactly) |
| 7 | 127 | 1696 (best-known lower bound; S(7) is not yet known exactly) |

`combined_score` is the mean over all three sizes. Matching the published witness length scores
1.0. For `k=6` and `k=7`, a longer valid partition scores above 1.0 -- a genuine, new, checkable
improvement on a still-open lower bound, since the oracle checks your literal submitted partition
directly, not a recalled number. For `k=4`, `S(4)=44` is a *proven* exact value, so no valid
partition can exceed it -- disclosed rather than hidden; see `references/known_best.md`.

## Available tools and resources

NumPy and the standard library are available. A standard, effective technique: Schur's own
doubling construction -- given a sum-free partition of `{1,...,n}` into `k` parts, add a new part
`{n+1,...,2n+1}` and replace each old part `A_i` with `A_i` union `{2n+1+x : x in A_i}`, giving a
sum-free `(k+1)`-partition of `{1,...,3n+1}` -- applied recursively from `k=1` already beats a
naive greedy by a wide margin (the reference construction shipped with this task uses exactly
this, and still falls short of the published records at `k=6` and `k=7`). Extending an existing
good partition element by element (checking, for each new integer and each part, whether adding it
completes `a + b = x` with `a, b` already in that part) with backtracking, or an actual SAT-based
search, can do meaningfully better. Candidate execution is networkless and cannot look anything up.

## Rules and scope

- Only edit `solution.py`; keep `construct_partition(k)`.
- Return a list of ints in `{0,...,k-1}` of whatever length you construct.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

References: L. D. Baumert, S. W. Golomb, "Backtrack Programming," *J. ACM* 12(4) (1965), 516-524
(`S(4)=44`); M. J. H. Heule, "Schur Number Five," arXiv:1711.08076, AAAI 2018 (`S(5)=160`,
confirming no partition of 161 exists); H. Fredricksen, M. Sweet, "Symmetric sum-free partitions
and lower bounds for Schur numbers," *Electron. J. Combin.* 7 (2000), #R32 (`S(6) >= 536`); F.
Rowley, "An Improved Lower Bound for S(7) and Some Interesting Templates," arXiv:2107.03560
(2021) (`S(7) >= 1696`).
