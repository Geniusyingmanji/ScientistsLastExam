# Reference and admission record — IceObservationNetworkDesign

## 1. Reference method

`verification/reference_solver.py` is standalone and uses only public inputs and charged interfaces. Unit-normalized forecast A-optimal greedy selection with budget-feasible exchange refinement.
It is a method witness, not independent high-fidelity verification. Normalizing each forecast by its prior standard deviation prevents meters from dominating millimeters. Three exchange passes improve the greedy archive; nonlinear ice-flow validation is still pending.

## 2. Baseline and normalization

The shipped `solution.py` is the zero baseline. The runnable public reference searches the coarse
budget grid 7/9/11/13/15/16/17/18 and scores `0.679581` development / `0.554644`
robustness. The evaluator's score-one anchor uses the same public greedy/exchange method for every
integer budget from 5 through 18. Better exact-OSSE archives remain visible above one.
Changed oracle versions must not be compared as if their score differences were model improvements.

## 3. Capability comparisons and ablations

Run `python scripts/diagnose_pr9_earth.py --output tmp/hardening/diagnostics.json --sweeps`.
On the current dirty macOS tree, the dense-exchange reference scores `0.679581` development and
`0.554644` robustness. Replaying the historical greedy method on the current OSSE scores
`0.435609` / `0.317681`. This comparison measures the combined effect of forecast-unit
normalization, exchange refinement and the changed oracle; it is not an isolated causal ablation.

## 4. Shortcut probes

The historical greedy construction is the only task-specific shortcut probe currently measured;
it remains below the current reference. Filling the omitted integer budgets with the same public
greedy/exchange method reaches the score-one anchor by construction, so the `0.679581` reference
score alone is not a difficulty result. Sensor-type quotas, cost-only selections and single-forecast
A-optimal grids remain unmeasured. The values above are local diagnostics, not frozen benchmark
evidence.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before exposure, must
show that the first proposal does not reach the competent reference. No calibration or external
review is implied by these local code changes. Server-held worlds and independent model review
remain required.

## 6. Construction errors and revisions

2026-09-05 hardening: Normalizing each forecast by its prior standard deviation prevents meters from dominating millimeters. Three exchange passes improve the greedy archive; nonlinear ice-flow validation is still pending.
Standalone references no longer import the hidden evaluator. The task card records the review
lineage, licensing uncertainty and public-world contamination risk. Earlier measurements below
belong to the pre-hardening version and are retained only as history.

## 7. Robustness and reproducibility

Development and heldout metrics remain separate. The new tests cover anchor feasibility,
equivalent-parameter scoring, mass conservation, time refinement, forecast-unit invariance,
instrument error poisoning and malformed submissions as applicable. Formal Linux sandbox
replay, global evidence refresh and independent scientific replication are still pending.
See the task card citations for background; the explicitly declared reduced model is not
certified by those publications.

## Historical pre-hardening record (obsolete scores)

# Known best — IceObservationNetworkDesign

## Scoring anchor

`verification/reference_solver.py` is the shipped truth-blind greedy A-optimal multibudget
archive. The evaluator recomputes its exact-OSSE hypervolume for every world and assigns it score
1.0. The shipped clustered-network baseline scores approximately zero.

The normalization was floored at zero and deliberately not capped above one. The greedy archive was
a search witness, not a proven global optimum; a candidate network archive with greater exact-OSSE
hypervolume remained visible above 1.0.

The reference and all procedural OSSE worlds were introduced on 2026-09-05. They still require
model calibration, server-held worlds, full ice-flow replication and independent cryosphere
review.

## Difficulty ladder measurement

The same frozen truth-blind witness was evaluated at all three levels on 2026-09-05. Because this
witness defined the per-level normalization anchor, its combined score remained one; raw exact
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
