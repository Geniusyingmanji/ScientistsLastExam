# MeritFactorSequence — build a binary sequence with a higher merit factor than the record

## Scientific setting

The merit factor of a binary polynomial `p(z) = sum_{i=0}^{n-1} a_i z^i` with coefficients
`a_i` in `{-1, 1}` is `F(p) = n^2 / (2 * sum_{k=1}^{n-1} C_k^2)`, where
`C_k = sum_i a_i * a_{i+k}` is the aperiodic autocorrelation at lag `k` -- a measure of how
flat the sequence's spectrum is. The best-known construction (Borwein, Choi, Jedwab, 2004)
achieves `F = 9.5851` at length 191; this is the documented record used here (see
`references/known_best.md` for a disclosure of what could and could not be independently
confirmed about it).

## Your task

Implement:

```python
def construct_sequence() -> list[float]:
    """Return a list of +/-1 coefficients, length >= 100."""
```

Every entry must be exactly `1` or `-1`, and the sequence must have length at least 100.
Anything else scores zero. Never an infrastructure failure.

## Evaluation

`score = (your_merit_factor - baseline) / (9.5851 - baseline)`, clipped below at 0 and
**unbounded above**:

| baseline merit factor (naive, always valid) | published record |
|---|---|
| 0.015227653418608192 (all-ones, length 100) | 9.5851 (Borwein, Choi, Jedwab, 2004, L=191) |

Matching the published record scores 1.0; a higher merit factor scores above 1.0 -- a real,
checkable new result, since the oracle computes the merit factor directly from your
literal submitted coefficients, not a recalled number.

## Available tools and resources

NumPy and the standard library are available. A standard, effective technique: start from
several random +/-1 sequences, then repeatedly flip one randomly-chosen sign, keeping the
flip only if it strictly raises the merit factor; repeat with many random restarts. This
clears the naive all-ones baseline by more than two orders of magnitude but does not reach
the published record -- the record uses an algebraic construction related to Barker-like
arrays, which is real headroom for a smarter search. Candidate execution is networkless and
cannot look anything up.

## Rules and scope

- Only edit `solution.py`; keep `construct_sequence()`.
- Return a list of `+1`/`-1` values, length at least 100.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

References: P. Borwein, K.-K. S. Choi, J. Jedwab, "Binary sequences with merit factor
greater than 6.34," *IEEE Trans. Inform. Theory* 50 (2004), DOI `10.1109/TIT.2004.838341`
(the current published record for `n >= 100`, `F = 9.5851` at `L=191, E=1903`).
