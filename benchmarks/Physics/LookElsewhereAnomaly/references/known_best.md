# LookElsewhereAnomaly — reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_scan.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_scan.py`

Truth-blind: it reads only the public flat prior and the histogram.

| metric | development | held out |
|---|---|---|
| combined / mechanism score (normalized) | **1.0000** | 1.0000 |
| signal recovery rate | 1.00 | 1.00 |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |
| mean toy units | 0.00 of 8 | - |

It refuses when the sideband reduced chi-square against the public prior exceeds 2.5, and
otherwise applies a Bonferroni factor over `n_mass_windows`. A local 5σ that is not
global-5σ is declined; a genuine resonance in these worlds remains above the threshold.

Empirical toys can replace Bonferroni and are leftover headroom, not an exploit. The
reference sits at the scoring ceiling this contract admits: a first searcher proposal that
reaches it means the task needs hardening before it is anything more than an evidence-cell
on-ramp. No frontier draw has been run yet.

## Baseline - `solution.py`

Never buys toys. Never declines. The highest local z against the public prior is published
as a discovery. Fluke, sculpted and blank worlds are therefore papers.

| metric | value |
|---|---|
| combined score | **0.0000** |
| signal recovery rate | 1.00 |
| false discovery rate | 1.00 |
| correct refusal rate | 0.00 |
| mean toy units | 0.00 |
