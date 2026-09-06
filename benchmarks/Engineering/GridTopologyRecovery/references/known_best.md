# GridTopologyRecovery — reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_topology.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_topology.py`

Truth-blind: it reads only the public catalog, the frozen injections, and the budgeted `measure` callback.

| metric | development | held out |
|---|---|---|
| combined / mechanism score (normalized) | **1.00** | **1.00** |
| signal recovery rate | 1.00 | 1.00 |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |

It ranks catalog residuals on both injection patterns and refuses when the top two graphs tie. The twin is graph_3 plus an invisible chord between already-equipotential buses. No frontier draw has been run yet.

## Baseline - `solution.py`

Buys one angle it ignores. Always publishes the star (`graph_1`). Twin worlds are therefore star papers.

| metric | value |
|---|---|
| combined score | **0.0000** |
| signal recovery rate | 0.25 |
| false discovery rate | 1.00 |
| correct refusal rate | 0.00 |
