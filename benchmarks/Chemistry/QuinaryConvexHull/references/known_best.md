# QuinaryConvexHull — reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_hull.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_hull.py`

Truth-blind: it reads only the public catalog and the budgeted `relax` callback.

| metric | development | held out |
|---|---|---|
| combined / mechanism score (normalized) | **1.0000** | 1.0000 |
| signal recovery rate | 1.00 | 1.00 |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |

It reserves replicate calls. Energies that do not reproduce are glass and are declined.
Remaining points are placed on the lower convex envelope of formation energy versus
composition; only non-unary vertices are claimed. E_f < 0 is not the stable set. The
reference sits at the scoring ceiling this contract admits on the 35-name catalog: a first
searcher that reaches it is an on-ramp warning, not MADE-scale evidence. Adaptive query
order on a larger catalog is leftover headroom. No frontier draw has been run yet.

The oracle is a frozen analytic mixing-plus-well energy. It does not call MACE, ORB, or
AlphaFold. MADE (arXiv:2601.20996) is the hardness citation, not the energy engine.

## Baseline - `solution.py`

Never replicates. Never declines. Every catalog name with E_f < 0 is published as a new
stable, including near-hull junk ~12 meV/atom above the envelope.

| metric | value |
|---|---|
| combined score | **0.0000** |
| signal recovery rate | 0.25 |
| false discovery rate | 1.00 |
| correct refusal rate | 0.00 |
