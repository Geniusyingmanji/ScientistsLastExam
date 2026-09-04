# Known best — GroundwaterRemediationDesign

## Scoring anchor

`verification/reference_solver.py` is the shipped truth-blind plume-aligned multirate archive.
The evaluator recomputes its exact-model hypervolume for every aquifer and assigns it score 1.0.
The shipped baseline scores 0.0.

The normalization is floored at zero and deliberately not capped above one. The reference is a
search witness, not a proven global optimum; a candidate archive with greater exact-model
hypervolume must therefore remain visible with a score above 1.0.

The reference and all procedural aquifers were introduced on 2026-09-05. They still require model
calibration, server-held aquifers, MODFLOW replication and independent hydrogeology review.

## Difficulty ladder measurement

The same frozen truth-blind witness was evaluated at all three levels on 2026-09-05. Because this
witness defines the per-level normalization anchor, its combined score remains one; raw
hypervolume and worst-shift robustness expose the changed regime.

| level | exact HV | proxy HV | robustness |
|---:|---:|---:|---:|
| 1 | 0.554781 | 0.540886 | 1.000000 |
| 2 | 0.557896 | 0.521516 | 1.000000 |
| 3 | 0.551663 | 0.488367 | 0.250000 |

The growing proxy/exact separation and level-3 robustness loss confirm that the tighter compliance
and stress settings reach the scored path. Candidate calibration is still required to space the
three levels reliably.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task Hydrology/GroundwaterRemediationDesign \
  --reference verification/reference_solver.py \
  --entry design_remediation
```
