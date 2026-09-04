# Known best — DeformationMechanismInference

## Scoring anchor

`verification/reference_solver.py` is the shipped truth-blind source-family and parameter-search
witness. The evaluator recomputes its score through the same charged GNSS/InSAR interface exposed
to candidates; inactive placeholder parameters are excluded from parameter recovery.

Measured on 2026-09-05, the shipped baseline scores `0.000000` and the reference scores
`0.431014` on development worlds with `0.574436` robustness. This is a reproducibility anchor,
not a claim of optimality or validity for a real volcano. The task still requires model
calibration, server-held worlds, elastic-model replication and independent volcanology review.

## Difficulty ladder measurement

The same frozen truth-blind witness was evaluated at all three levels on 2026-09-05:

| level | combined | held-out robustness |
|---:|---:|---:|
| 1 | 0.431014 | 0.574436 |
| 2 | 0.398049 | 0.470419 |
| 3 | 0.302310 | 0.480655 |

The primary development score decreases monotonically. Held-out robustness at levels 2 and 3 is
close but not ordered, so further model calibration is still required before choosing a harder
default.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task Volcanology/DeformationMechanismInference \
  --reference verification/reference_solver.py \
  --entry infer_deformation_source
```
