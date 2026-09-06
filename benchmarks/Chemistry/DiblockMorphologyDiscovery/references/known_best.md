# DiblockMorphologyDiscovery — reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_morphology.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_morphology.py`

Truth-blind: it reads only the public q bounds and the budgeted `measure` callback.

| metric | development | held out |
|---|---|---|
| combined / mechanism score (normalized) | **1.00** | **1.00** |
| signal recovery rate | 1.00 | 1.00 |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |

It locates the first Bragg peak, probes the distinctive harmonics of lamella / hex / bcc / gyroid, and refuses when a second q* is incommensurate with those ratios. Disorder is the single bright RPA peak. No frontier draw has been run yet.

## Baseline - `solution.py`

Buys one mid-q assay it ignores. Always publishes lamellae. Mixture and ABC traces are therefore lamellar papers.

| metric | value |
|---|---|
| combined score | **0.0000** |
| signal recovery rate | 0.20 |
| false discovery rate | 1.00 |
| correct refusal rate | 0.00 |
