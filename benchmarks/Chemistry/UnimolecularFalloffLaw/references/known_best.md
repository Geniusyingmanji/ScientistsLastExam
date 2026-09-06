# UnimolecularFalloffLaw — reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_falloff.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_falloff.py`

Truth-blind: it reads only the public bounds and the budgeted `measure` callback.

| metric | development | held out |
|---|---|---|
| combined / mechanism score (normalized) | **~0.73** | **~0.78** |
| signal recovery rate | ~0.73 | similar |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |

It refuses when the low-pressure reaction order is not 1 (second channel) or when k falls as P rises. On in-family worlds it estimates k_inf from the high-P end and Fcent from the mid-falloff point. Publishing a typical Troe Fcent of 0.40 rather than a full master-equation fit is leftover headroom, not an exploit. No frontier draw has been run yet.

## Baseline - `solution.py`

Buys one mid-range assay it treats as pressure-independent Arrhenius. Always publishes Lindemann. Two-channel and negative-order worlds are therefore Lindemann papers.

| metric | value |
|---|---|
| combined score | **0.0000** |
| signal recovery rate | 0.00 |
| false discovery rate | 1.00 |
| correct refusal rate | 0.00 |
