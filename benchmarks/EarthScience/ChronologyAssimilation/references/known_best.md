> Version note (2026-09-05, second local hardening): Variable positive accumulation across 6/9/12 segments; joint age/climate inference remains approximate. The sections below include historical measurements from the first hardening; they are not measurements of the current version. Current local comparisons are recorded in `docs/reviews/new_tasks_difficulty_v2.md`.

# Reference and admission record — ChronologyAssimilation

## 1. Reference method

`verification/reference_solver.py` is standalone and uses only public inputs and charged interfaces. Calibration-tested, dated Gaussian-process reconstruction with propagated age error and coherence refusal.
It is a method witness, not independent high-fidelity verification. Public noisy proxy calibration observations make shared nonlinear response misspecification testable. Dating avoids clipped endpoints. The posterior still approximates shared chronology errors diagonally.

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

2026-09-05 hardening: Public noisy proxy calibration observations make shared nonlinear response misspecification testable. Dating avoids clipped endpoints. The posterior still approximates shared chronology errors diagonally.
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
