# AMOCTippingRefusal — reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_probe.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_probe.py`

Truth-blind: plus/minus probes at offset 0 must end at least 0.9 apart and on opposite
sides of zero; only then is a continued run used to read a crossing year.

| metric | development | held out |
|---|---|---|
| combined / mechanism score (normalized) | **1.0000** | 1.0000 |
| signal recovery rate | 1.00 | 1.00 |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |

The reference sits at the scoring ceiling this contract admits. A first searcher that
reaches it is an on-ramp warning, not a CMIP AMOC. No frontier draw has been run yet.

## Baseline - `solution.py`

Never probes. Never declines. The first historical year with a negative fingerprint is
published as a collapse (or `year_now` if the series stays positive).

| metric | value |
|---|---|
| combined score | **0.0000** |
| signal recovery rate | 0.00 |
| false discovery rate | 1.00 |
| correct refusal rate | 0.00 |
