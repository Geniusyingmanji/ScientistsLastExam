# MeritFactorSequence — reference results and anchor confidence

Every score below is produced by running code in this directory.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate solution.py --metrics-out /tmp/baseline.json
python3 frontier_eval/run_eval.py --candidate verification/reference_construction.py --metrics-out /tmp/reference.json
```

## The anchor (documented, disclosed confidence level)

`F = 9.5851` at length `L=191` -- P. Borwein, K.-K. S. Choi, J. Jedwab, "Binary sequences
with merit factor greater than 6.34," *IEEE Trans. Inform. Theory* 50 (2004), 3234-3249,
DOI `10.1109/TIT.2004.838341`. The paper's headline result is asymptotic (merit factor
`> 6.34` as `n -> infinity`, the first improvement on the asymptotic record since 1988);
`9.5851` is a documented specific finite-length instance of the same construction family,
corroborated during this task's construction against low-autocorrelation-binary-sequence
survey literature covering lengths in the 191-225 range. **Disclosed rather than asserted
with unearned confidence**: this task could not independently confirm that no other
published sequence at some other `n >= 100` exceeds 9.5851 -- only that no search result
found one. If a stronger documented record exists, this anchor should be updated.

## Baseline — `solution.py`

An all-ones sequence of length 100: every autocorrelation lag `C_k = 100 - k` is large,
giving a very poor merit factor.

| length | merit factor | score |
|---|---|---|
| 100 | 0.015227653418608192 | 0.0000 |

## Reference — `verification/reference_construction.py`

Randomized bit-flip hill-climbing: 8 restarts from random +/-1 sequences of length 100,
each running 20,000 single-sign-flip steps, keeping only flips that strictly raise the
merit factor.

| length | merit factor | score |
|---|---|---|
| 100 | 4.078303425774878 | 0.4246 |

`combined_score = 0.4246`. Measured directly by running
`verification/reference_construction.py` through the oracle above (runtime under 1s). Plain
bit-flip local search clears the naive baseline by more than two orders of magnitude but
falls well short of the published record -- the record uses an algebraic construction, not
a local search, leaving real headroom.

## What this task is not

This task scores the exact, finite, self-contained combinatorial object (a +/-1 sequence
and its exact aperiodic autocorrelation, computed directly). It does not ask for, and does
not check, the algebraic (Barker-array-related) construction technique behind the cited
record, nor the asymptotic analysis proving the construction family's limiting behavior --
those are separate, already-published results this task does not re-derive or re-check.
