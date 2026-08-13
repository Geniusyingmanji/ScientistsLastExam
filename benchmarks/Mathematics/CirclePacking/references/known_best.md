# CirclePacking — known best values

Pack N non-overlapping unit circles inside the smallest possible square. For most N there is no
closed-form optimum; the listed values are the smallest known square sides from computational
search, and a tighter packing is a genuine result. The score is therefore uncapped.

## Anchors

| N | grid baseline side | best known side | source |
|---:|---:|---:|---|
| 7 | 6.0000 | 5.7321 | proven optimal |
| 10 | 8.0000 | 6.7474 | Packomania (E. Specht) |
| 13 | 8.0000 | 7.6274 | Packomania (E. Specht) |

Score per instance is the fraction of the baseline-to-record gap closed:

```text
progress = (baseline_side − achieved_side) / (baseline_side − best_known_side)
score    = max(0, progress)          # no upper clamp
```

Reaching the record scores exactly 1.0. Worked example at N=7, where the grid baseline is 6.0
and the record is 5.7321: a side of 5.8500 scores 0.5599, 5.7321 scores 1.0000, and 5.6500
scores 1.3065.

## Why uncapped

Packomania is a live record table that has been improved repeatedly over decades. Clipping at
1.0 would make "matched the record" and "beat the record" indistinguishable, which is exactly
the distinction this benchmark exists to measure. N=7 is proven optimal and cannot be beaten;
N=10 and N=13 are conjectured and can.

## Sizing caveat

These instance sizes are small and settled. Measured on this repository: OpenEvolve reaches
0.9906 by its second oracle call and 0.9999 by the twentieth, and plain single-incumbent greedy
reaches 0.999989 by its sixth — the two searchers are indistinguishable because the task is easy
at these N, not because they are equally strong. Larger N, where the Packomania values are still
contested, is required before this task can discriminate between searchers.

## Reproduce

```bash
python -m sle eval --task Optimization/CirclePacking
```
