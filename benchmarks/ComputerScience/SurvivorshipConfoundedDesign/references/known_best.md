# SurvivorshipConfoundedDesign — reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_design.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_design.py`

Truth-blind: two interventions at the public probe values. OLS on returned survivors is unused.

| metric | development | held out |
|---|---|---|
| combined / mechanism score (normalized) | **1.0000** | 1.0000 |
| signal recovery rate | 1.00 | 1.00 |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |

The reference sits at the scoring ceiling this contract admits. A first searcher proposal
that reaches it means the task needs hardening before it is frontier evidence. No frontier
draw has been run yet.

## Baseline - `solution.py`

Never intervenes. Never declines. OLS among observational survivors is published as a
causal effect. Collider and blank worlds are therefore papers.

| metric | value |
|---|---|
| combined score | **0.0000** |
| signal recovery rate | 1.00 |
| false discovery rate | 1.00 |
| correct refusal rate | 0.00 |
