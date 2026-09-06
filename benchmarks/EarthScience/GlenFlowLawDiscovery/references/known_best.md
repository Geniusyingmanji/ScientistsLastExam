# GlenFlowLawDiscovery — reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_flow.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_flow.py`

Truth-blind: it reads only the public bounds and the budgeted `measure` callback.

| metric | development | held out |
|---|---|---|
| combined / mechanism score (normalized) | **~0.98** | **~0.97** |
| signal recovery rate | ~0.98 | ~0.97 |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |

It refuses when the log-log curvature exceeds 0.40 or when the apparent exponent is outside both families (plugs, sliding mixes). On in-family worlds it publishes the four-point slope as `n`. Fitting `A` jointly with `n` is leftover headroom, not an exploit. No frontier draw has been run yet.

## Baseline - `solution.py`

Buys one mid-range assay and always publishes Newtonian `n = 1`. Sliding and plug worlds are therefore Newtonian papers.

| metric | value |
|---|---|
| combined score | **0.0000** |
| signal recovery rate | ~0.33 |
| false discovery rate | 1.00 |
| correct refusal rate | 0.00 |
