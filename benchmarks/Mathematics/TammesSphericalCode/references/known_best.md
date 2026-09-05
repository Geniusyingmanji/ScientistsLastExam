# TammesSphericalCode — reference results and anchor confidence

Every score below is produced by running code in this directory.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate solution.py --metrics-out /tmp/baseline.json
python3 frontier_eval/run_eval.py --candidate verification/reference_construction.py --metrics-out /tmp/reference.json
```

## The anchor (best-known, genuinely open)

`n=15` on `S^2`: best-known minimum angular separation has cosine
`0.59260590292507377809642492233276` (Cohn et al.'s Spherical Codes database,
`https://cohn.mit.edu/spherical-codes/`, re-fetched 2026-09-06). Not proven optimal --
`n=14` was the last case proven optimal (Musin & Tarasov, 2015), making `n=15` the first
open case. A candidate that finds a valid point set with a smaller maximum pairwise dot
product would be a genuine, new, checkable record.

## Baseline — `solution.py`

Fibonacci-sphere spiral (golden-angle construction): a simple, standard way to spread
points roughly evenly, not tailored to any specific `n`.

| n | max dot product | score |
|---|---|---|
| 15 | 0.8571428571428572 | 0.0000 |

## Reference — `verification/reference_construction.py`

Randomized hill-climbing on the sphere: 25 restarts, each perturbing one point at a time
(re-normalized back onto the sphere) with an annealed step size, keeping only moves that
strictly lower the maximum pairwise dot product.

| n | max dot product | score |
|---|---|---|
| 15 | 0.6099012982236485 | 0.9346 |

Measured directly by running `verification/reference_construction.py` through the oracle
above (runtime approx 4s). Gets close to the published record but does not reach it --
real headroom remains for a smarter search.

## What this task is not

This task scores the exact, finite, self-contained geometric object (a finite point set on
the sphere and its maximum pairwise dot product, computed directly). It does not ask for,
and does not check, the enumeration-of-irreducible-contact-graphs proof technique used to
settle `n=14` -- that is separate, already-published mathematics this task does not
re-derive or re-check.
