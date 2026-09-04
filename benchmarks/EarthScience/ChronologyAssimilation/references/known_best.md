# Known best — ChronologyAssimilation

## Scoring anchor

`verification/reference_solver.py` is the shipped truth-blind dated-proxy interpolation witness.
The evaluator recomputes its score from the public proxy archive and charged dating interface
without reading hidden ages or the hidden climate field.

Measured on 2026-09-05, the shipped baseline scores `0.000000` and the reference scores
`0.362243` on development worlds with `0.195631` robustness. This is a reproducibility anchor,
not a claim of optimality or paleoclimate validity. The task still requires model calibration,
server-held proxy systems, public-data replay and independent paleoclimate review.

## Difficulty ladder measurement

The same frozen truth-blind witness was evaluated at all three levels on 2026-09-05:

| level | combined | held-out robustness |
|---:|---:|---:|
| 1 | 0.362243 | 0.195631 |
| 2 | 0.327493 | 0.165201 |
| 3 | 0.299300 | 0.130898 |

Both axes decrease monotonically as chronology span and proxy/dating noise increase.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task Paleoclimate/ChronologyAssimilation \
  --reference verification/reference_solver.py \
  --entry reconstruct_climate
```
