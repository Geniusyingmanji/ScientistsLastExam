# AffineLoopRankingCertificate — reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_ranking.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_ranking.py`

Truth-blind: it reads only the published guards and update, searches a catalog
of 1-norm rational ranking directions, and keeps the largest exact-feasible
decrease.

| metric | value |
|---|---|
| combined score | **0.749975** |
| instances with a valid certificate | 4 / 4 |
| cut_x proven delta | 2 |
| cut_y proven delta | 3 |
| skew proven delta | 1 |
| cut3 proven delta | 4 (clips at the unit 3) |

A larger rational catalog, or a ranking that uses a nonzero decrease multiplier,
is leftover headroom, not an exploit. No frontier draw has been run yet.

## Baseline - `solution.py`

The first standard-basis ranking at `delta = 1/10000`, which is a valid linear
ranking on every published loop.

| metric | value |
|---|---|
| combined score | **0.000000** |
| instances with a valid certificate | 4 / 4 |
