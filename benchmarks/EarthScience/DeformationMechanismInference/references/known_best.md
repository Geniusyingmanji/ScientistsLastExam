> Version note (2026-09-05, second local hardening): Five linear nuisance terms now require separation from physical sources; single-source nonlinear least squares still approaches the ceiling. The sections below include historical measurements from the first hardening; they are not measurements of the current version. Current local comparisons are recorded in `docs/reviews/new_tasks_difficulty_v2.md`.

# Reference and admission record — DeformationMechanismInference

## 1. Reference method

`verification/reference_solver.py` is standalone and uses only public inputs and charged interfaces. Coarse multistart source-family search refined by bounded least squares; sill scores strength/depth equivalence classes.
It is a method witness, not independent high-fidelity verification. Equivalent sill strength/depth pairs now receive identical parameter credit. The complete sill and rotated dike equations are public. Multi-source/elastic high-fidelity replication remains pending.

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

2026-09-05 hardening: Equivalent sill strength/depth pairs now receive identical parameter credit. The complete sill and rotated dike equations are public. Multi-source/elastic high-fidelity replication remains pending.
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
