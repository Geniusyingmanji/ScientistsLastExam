# Reference and admission record — IceObservationNetworkDesign

## 1. Reference method

`verification/reference_solver.py` is standalone and uses only public inputs and charged interfaces. Unit-normalized forecast A-optimal greedy selection with budget-feasible exchange refinement.
It is a method witness, not independent high-fidelity verification. Normalizing each forecast by its prior standard deviation prevents meters from dominating millimeters. Three exchange passes improve the greedy archive; nonlinear ice-flow validation is still pending.

## 2. Baseline and normalization

The shipped `solution.py` is the baseline. Tests check valid near-zero development scores.
Optimization references define one through recomputed objective differences; discovery scores
retain their fixed supported-world ceilings and refusal normalization. Changed oracle versions
must not be compared as if their score differences were model improvements.

## 3. Capability comparisons and ablations

Run `python scripts/diagnose_new_task_hardening.py --output tmp/hardening/diagnostics.json --sweeps`.
Historical public methods are replayed on the current oracle where available; these comparisons
are **not** isolated causal ablations. HVAC additionally removes occupancy forecasting, and the
wastewater constant controller removes all state feedback. A complete per-capability ladder,
including measured nonzero drops, still requires clean Linux execution before admission.

## 4. Shortcut probes

The diagnostic script includes 528 constant aeration/recycle pairs, 48 historical thermostat
parameter pairs, a source-only single-well archive, and historical public search methods.
`tests/test_new_task_hardening.py` pins the diagnosed scientific failures and known shortcuts.
All remaining untested low-dimensional families are admission risks; passing these probes does
not prove the absence of shortcuts. Numeric tables from a laptop are local debugging output,
not frozen benchmark evidence.

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
