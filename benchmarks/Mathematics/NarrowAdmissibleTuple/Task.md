# NarrowAdmissibleTuple — find a narrower admissible k-tuple than Polymath8b's

## Scientific setting

The Zhang / Maynard-Tao / Polymath8 program on bounded gaps between primes reduces to a
combinatorial construction problem: find a set of `k` distinct integers — an **admissible
k-tuple** — that is as tightly packed as possible.

A set `H = {h_1, ..., h_k}` is **admissible** if, for every prime `p`, the residues
`{h_i mod p}` do not cover all `p` residue classes. (This is only a real constraint for primes
`p <= k`: with only `k` values you cannot possibly cover `p > k` classes, so admissibility is an
exact, finite, checkable computation over the primes up to `k`.) The Maynard-Tao theorem says
that for `k` large enough, *any* admissible k-tuple is guaranteed to contain at least two primes
infinitely often — and the **diameter** (`max(H) - min(H)`) of the tuple you use directly bounds
a prime gap that recurs infinitely often. This is exactly the object Polymath8b computed: an
admissible 50-tuple of diameter **246** is what gives "there are infinitely many primes `p > q`
with `p - q <= 246`" (arXiv:1409.8361). Finding a *narrower* admissible 50-tuple would be a real,
exactly-checkable improvement on a problem that is still open today.

## Your task

Implement:

```python
def construct_tuple(k: int) -> list[int]:
    """Return a list of k distinct integers forming an admissible k-tuple."""
```

You will be called at `k = 50` and `k = 54`. Your tuple must contain exactly `k` distinct
integers, and for every prime `p <= k` the residues of your tuple mod `p` must not cover all `p`
classes. Anything else — wrong count, duplicates, a diameter outside `(0, 200000]`, or a prime
whose residues you cover completely — scores that size zero. Never an infrastructure failure.

## Evaluation

For each `k`, `score = (baseline_diameter - your_diameter) / (baseline_diameter - sota_diameter)`,
clipped below at 0 and **unbounded above**:

| k | baseline diameter (naive, always valid) | published record diameter |
|---|---|---|
| 50 | 310 | 246 |
| 54 | 346 | 270 |

`combined_score` is the mean over both sizes. Matching the published record scores 1.0 on that
size; a smaller, verified diameter scores above 1.0 — a real result, not a benchmark artifact,
since the oracle checks your literal submitted tuple's admissibility and diameter directly. Simply
naming a number you recall is worth nothing: you must produce integers that pass the same
admissibility check anyone else would run.

## Available tools and resources

NumPy and the standard library are available. A standard, effective technique: sieve a symmetric
window of candidate integers, and for each prime `p <= k` remove whichever residue class currently
costs the least surviving density (a greedy min-impact rule), then slide a window of size `k`
across the survivors to find the smallest diameter. Randomized tie-breaking and prime-order
restarts, followed by local swaps to further shrink the diameter, can do better than a single
greedy pass. Candidate execution is networkless and cannot look anything up.

## Rules and scope

- Only edit `solution.py`; keep `construct_tuple(k)`.
- Return exactly `k` distinct integers per call.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

This task scores an exact, self-contained combinatorial check (admissibility and diameter of your
submitted integers); it says nothing about the analytic level-of-distribution machinery
(Bombieri-Vinogradov / Zhang / Maynard-Tao sieve weights) that turns a narrow admissible tuple into
a proved bound on prime gaps — that machinery is a fixed, already-published fact this task assumes,
not something you re-derive. `sle.contract_lint` is importable inside the sandbox and costs no
oracle call.

References: Zhang, *Ann. of Math.* 179 (2014), 1121-1174, DOI `10.4007/annals.2014.179.3.7`;
Maynard, *Ann. of Math.* 181 (2015), 383-413, DOI `10.4007/annals.2015.181.1.7`; D.H.J. Polymath,
"The 'bounded gaps between primes' Polymath project — a retrospective," arXiv:1409.8361; D.H.J.
Polymath, "Variants of the Selberg sieve, and bounded intervals containing many primes,"
*Research in the Mathematical Sciences* 1:12 (2014), DOI `10.1186/s40687-014-0012-7`.
