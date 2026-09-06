# HeavyTailEvidence — reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_tail.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_tail.py`

Truth-blind: it reads only the public sample, xmin, and the budgeted `extra_draw` callback.

| metric | development | held out |
|---|---|---|
| combined / mechanism score (normalized) | **~0.75** | **~0.86** |
| signal recovery rate | ~0.75 | similar |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |

It refuses when the public sample has fewer than 25 points, or when the log-moment ratio is neither a power law nor a lognormal (exponential cutoff). A full Clauset xmin search is not in the score because xmin is public. No frontier draw has been run yet.

## Baseline - `solution.py`

Ignores the sample. Always publishes a power law with alpha=2. Cutoff and small-n worlds are therefore power-law papers.

| metric | value |
|---|---|
| combined score | **0.0000** |
| signal recovery rate | ~0.21 |
| false discovery rate | 1.00 |
| correct refusal rate | 0.00 |
