# PTAHellingsDowns — reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_kernel.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_kernel.py`

Truth-blind: it reads only the public pair angles and correlations.

| metric | development | held out |
|---|---|---|
| combined / mechanism score (normalized) | **1.0000** | 1.0000 |
| signal recovery rate | 1.00 | 1.00 |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |
| mean boot units | 0.00 of 6 | - |

It fits four public spatial kernels by least squares and publishes Hellings–Downs only when
that kernel is uniquely best. A clock monopole, an ephemeris dipole, and an uncorrelated
process are declined. Empirical bootstraps can replace the public-table fit and are leftover
headroom, not an exploit. The reference sits at the scoring ceiling this contract admits: a
first searcher proposal that reaches it means the task needs hardening before it is anything
more than an evidence-cell on-ramp. No frontier draw has been run yet.

Hellings–Downs overlap reduction is pinned to Hellings & Downs 1983: Γ = 1/2 − x/4 + (3/2) x ln x
with x = (1−cos θ)/2, so Γ(π) = 1/4 and Γ(π/2) ≈ −0.145.

## Baseline - `solution.py`

Never buys bootstraps. Never declines. A positive mean pair correlation is published as
Hellings–Downs. Monopole, dipole and uncorrelated worlds are therefore gravitational-wave papers.

| metric | value |
|---|---|
| combined score | **0.0000** |
| signal recovery rate | 1.00 |
| false discovery rate | 1.00 |
| correct refusal rate | 0.00 |
| mean boot units | 0.00 |
