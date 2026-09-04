# Known best — ActiveFullWaveformInversion

## Scoring anchor

`verification/reference_solver.py` is the shipped truth-blind multishot smooth-lens witness. The
evaluator recomputes its score from the same public acquisition interface available to a
candidate; it does not read the hidden velocity field.

Measured on 2026-09-05, the shipped baseline scores `0.000000` and the reference scores
`0.249539` on development worlds with `0.209638` robustness. This is a reproducibility anchor,
not a claim of optimality or real-Earth validity. The task still requires model calibration,
server-held worlds, higher-fidelity replication and independent seismology review.

## Difficulty ladder measurement

The same frozen truth-blind witness was evaluated at all three levels on 2026-09-05:

| level | combined | held-out robustness |
|---:|---:|---:|
| 1 | 0.249539 | 0.209638 |
| 2 | 0.101852 | 0.276268 |
| 3 | 0.078013 | 0.000000 |

The primary development score decreases monotonically. The small held-out set is not ordered at
level 2, so these are initial ladder measurements rather than a claim of fully calibrated spacing.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task WavePropagation/ActiveFullWaveformInversion \
  --reference verification/reference_solver.py \
  --entry invert_velocity_model
```
