# Known best — IceObservationNetworkDesign

## Scoring anchor

`verification/reference_solver.py` is the shipped truth-blind greedy A-optimal multibudget
archive. The evaluator recomputes its exact-OSSE hypervolume for every world and assigns it score
1.0. The shipped clustered-network baseline scores approximately zero.

The normalization is floored at zero and deliberately not capped above one. The greedy archive is
a search witness, not a proven global optimum; a candidate network archive with greater exact-OSSE
hypervolume must therefore remain visible with a score above 1.0.

The reference and all procedural OSSE worlds were introduced on 2026-09-05. They still require
model calibration, server-held worlds, full ice-flow replication and independent cryosphere
review.

## Difficulty ladder measurement

The same frozen truth-blind witness was evaluated at all three levels on 2026-09-05. Because this
witness defines the per-level normalization anchor, its combined score remains one; raw exact
hypervolume and robustness show the harder regimes.

| level | exact HV | proxy HV | robustness |
|---:|---:|---:|---:|
| 1 | 0.487761 | 0.520869 | 1.000000 |
| 2 | 0.468543 | 0.513062 | 0.250000 |
| 3 | 0.436843 | 0.498975 | 0.000000 |

Exact forecast skill and worst-shift robustness decrease monotonically as observation noise,
model discrepancy and physical stresses increase.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task Cryosphere/IceObservationNetworkDesign \
  --reference verification/reference_solver.py \
  --entry design_ice_observation_network
```
