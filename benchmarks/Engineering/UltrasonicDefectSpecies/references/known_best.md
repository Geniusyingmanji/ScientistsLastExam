# UltrasonicDefectSpecies — reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_species.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_species.py`

Truth-blind: it reads only the public bounds and the budgeted `measure` callback.

| metric | development | held out |
|---|---|---|
| combined / mechanism score (normalized) | **1.00** | **~0.75** |
| signal recovery rate | 1.00 | 0.75 |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |

It refuses when both polarities are strong (mixture or mode conversion). On in-family worlds it uses polarity and a same-sign doublet test. Recovering depth as well as species, and the held-out lack-of-fusion arrival that sits between coarse samples, is leftover headroom, not an exploit. No frontier draw has been run yet.

## Baseline - `solution.py`

Buys one mid-range sample and always publishes a clean scan. Mixture and mode-converted worlds are therefore "none" papers.

| metric | value |
|---|---|
| combined score | **0.0000** |
| signal recovery rate | 0.25 |
| false discovery rate | 1.00 |
| correct refusal rate | 0.00 |
