# ComplexBoseLaw — reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_fit.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_fit.py`

Truth-blind: it reads only the public bounds and the budgeted `measure` callback.

| metric | development | held out |
|---|---|---|
| combined / mechanism score (normalized) | **~0.94** | similar |
| signal recovery rate | ~0.94 | similar |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |

It refuses when occupancy does not move with T (blank) or saturates below 1 (Fermi). On Bose
worlds it inverts the mixed occupancy with the exact map x = log(1 + 1/n) ≈ C ω^α / T^β.
Mixing mostly renormalizes C; the exponents remain recoverable. A joint fit of the three
mixing weights is leftover headroom, not an exploit. No frontier draw has been run yet.

NewtonBench (arXiv:2510.07172) motivates the shifted exponents and complex-apparatus stress,
but its printed hard distribution-law cell uses the opposite denominator sign. This task
restores the physical Bose minus sign and varies (α, β) by world, so it should be treated as
a related counterfactual task rather than a benchmark reproduction.

## Baseline - `solution.py`

Buys one measurement it ignores. Always publishes textbook Bose occupation (C, α, β) = (1, 1, 1).
Fermi and blank worlds are therefore Bose papers.

| metric | value |
|---|---|
| combined score | **0.0000** |
| signal recovery rate | ~0.23 |
| false discovery rate | 1.00 |
| correct refusal rate | 0.00 |
