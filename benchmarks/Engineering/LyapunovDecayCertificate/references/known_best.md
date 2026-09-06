# LyapunovDecayCertificate — reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_lyapunov.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_lyapunov.py`

Truth-blind: it reads only the published modes and searches a catalog of rational Gram matrices, keeping the largest exact-feasible rate.

| metric | value |
|---|---|
| combined score | **0.749867** |
| instances with a valid certificate | 4 / 4 |
| shear / pair / three proven alpha | 1/2 |
| mid proven alpha | 3/4 |

A larger rational catalog, or a better-conditioned Gram than the eight catalog entries, is leftover headroom, not an exploit. No frontier draw has been run yet.

## Baseline - `solution.py`

The identity Gram at `alpha = 1/10000`, which is a valid common Lyapunov function because every published mode has a negative numerical abscissa.

| metric | value |
|---|---|
| combined score | **0.000000** |
| instances with a valid certificate | 4 / 4 |
