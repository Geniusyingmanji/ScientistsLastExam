# DifferenceBasisRatio — reference results and anchor confidence

Every score below is produced by running code in this directory.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate solution.py --metrics-out /tmp/baseline.json
python3 frontier_eval/run_eval.py --candidate verification/reference_construction.py --metrics-out /tmp/reference.json
```

## The anchor (genuinely open, actively improving)

`C = inf_n Delta(n)^2/n <= 2.6390` -- B. Georgiev, J. Gómez-Serrano, T. Tao, A. Z. Wagner,
"Mathematical exploration and discovery at scale," arXiv:2511.02864, Section 3 ("Difference
bases"): AlphaEvolve improved the published upper bound from 2.6571 to 2.6390, the first
improvement in years. This is used as the single `score = 1.0` target for every call,
since the constant is defined as an infimum over *every* n -- a good basis at any scale is
a genuine data point toward it. A candidate that finds a basis with ratio below 2.6390 at
any n would be a real, new, checkable improvement.

## Baseline — `solution.py`

A "two-level" basis with `k = round(sqrt(2n))` (no search over k, no pruning): `{0,...,k-1}`,
its negatives, and multiples of `k` up to `n`.

| hint_n | n used | basis size | ratio | score |
|---|---|---|---|---|
| 500 | 500 | 78 | 12.168 | 0.0000 |
| 2000 | 2000 | 156 | 12.168 | 0.0000 |
| 10000 | 10000 | 351 | 12.3201 | 0.0000 |

## Reference — `verification/reference_construction.py`

Searches over a range of `k` around `sqrt(2n)` for the smallest valid two-level basis, then
prunes any element whose removal still leaves every difference covered (up to 3 rounds).

| hint_n | n used | basis size | ratio | score |
|---|---|---|---|---|
| 500 | 500 | 47 | 4.4180 | 0.8133 |
| 2000 | 2000 | 93 | 4.3245 | 0.8231 |
| 10000 | 10000 | 203 | 4.1209 | 0.8469 |

`combined_score = 0.8278`. Measured directly by running
`verification/reference_construction.py` through the oracle above (runtime approx 33s for
all three calls together). A real, standard two-stage technique -- not the Fourier-analytic
optimization behind the published 2.6390 bound -- and it does not reach that bound, leaving
real headroom for a smarter search.

## What this task is not

This task scores the exact, finite, self-contained combinatorial object (a difference
basis and its coverage of every difference `1..n`, checked by exact convolution). It does
not ask for, and does not check, the Fourier-analytic / convex-optimization machinery
behind the published improvements to the constant's bound -- that is separate,
already-published mathematics this task does not re-derive or re-check.
