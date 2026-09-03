# CrowdedSpectrumAssignment - reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_assignment.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_assignment.py`

Truth-blind: it reads only the public library and the budgeted zoom.

| metric | development | held out |
|---|---|---|
| combined / mechanism score (normalized) | **0.7172** | 0.8152 |
| species-set rate | 1.0000 | 1.0000 |
| fraction score | 0.7172 | 0.8152 |
| false-species rate | 0.0000 | 0.0000 |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |
| mean zoom calls | 1.56 of 8 | not reported by the held-out summary |

It matches unique default-scan peaks to the library immediately, and buys a zoom only when a
peak sits within two default widths of more than one species. After zooms it requires two hits
to name a species, and declines on unexplained peaks or a blank scan.

The paired alias worlds have exactly the same default scan but different hidden species sets;
their zooms contain the information needed to distinguish a true epsilon line from a
gamma-plus-delta blend. The reference votes once per zoomed line using its strongest resolved
peak, rather than treating every noise-induced local maximum as a separate line, and recovers
all four alias species sets. Weighted fraction fitting remains deliberate headroom; the
reference still assigns equal fractions within each claimed set.

A first searcher proposal that reaches the reference means the task needs hardening before it
is anything more than an on-ramp. No frontier draw has been run yet.

## Baseline - `solution.py`

Never zooms. Never declines. Every library species with a line near a default-scan peak is
claimed, with equal fractions. Blank and contaminant worlds are therefore published.

| metric | value |
|---|---|
| combined score | **0.0000** |
| species-set rate | 0.29 |
| fraction score | 0.37 |
| false discovery rate | 1.00 |
| correct refusal rate | 0.00 |
| mean zoom calls | 0.00 |
