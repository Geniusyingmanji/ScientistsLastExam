# Reference and admission record — MetabolicStrainDesign

## 1. Reference method

`verification/reference_solver.py` is standalone: it rebuilds the linear programs
from the public problem statement and greedily applies the edit (knockout of an
editable reaction or an overexpression multiplier from the ladder 1.5/2/2.5/4) that
most improves the worst-case product flux across stratified draws from the public
deviation model (nominal, both 0.65/1.35 corners, two random spreads), until the
five-edit budget is spent. It deliberately lacks lookahead beyond one edit,
continuous multiplier optimization and any knowledge of the sealed draw seeds.

## 2. Baseline and normalization

The wild type (no edits) scores exactly `0.000000` by construction: per draw the
score is (product − wildtype)/(witness − wildtype) with every quantity re-solved by
the oracle at scoring time. The frozen witness design is `{knockouts: [], overexpressions: {E_bypass: 2.0,
E_product: 2.0}}` — found by exhaustive enumeration over the edit grid as the
worst-draw-optimal design; it strictly beats the wild type on all six draws
gaps 1.2-2.2, and better designs score above one.

## 3. Capability comparisons and ablations

| variant | development | robustness |
|---|---:|---:|
| witness design | 1.000 | 1.000 |
| greedy reference (stratified draws) | 0.851 | 0.839 |
| intuitive overflow knockout + product x3 | 0.100 | 0.120 |
| old 4x/4x hand pair | rejected by the engineering budget | — |

After the stratified-draw fix both greedy variants converge on the same edits on
these worlds; before it, nominal-only greedy stopped after one edit and lost a third
of the score. Local debugging numbers, not frozen benchmark evidence.

## 4. Shortcut probes

The naive knockout intuition scores 0.10 and the pre-hardening hand pair is
illegal under the engineering budget. No parameterized family dominates; the
artifact is the enzyme edit set and multiplier allocation under budget.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not beat the witness. Independent
metabolic-engineering review remains required.

## 6. Construction errors and revisions

Four construction errors were caught locally, the last two in the 2026-09-06
difficulty rework. (i) The first witness multiplier ladder made the witness the
linear-program optimum, so the uncapped record was unreachable. (ii) The reference
computed the biomass gate from edited capacities. (iii) biosynthesis was listed as
both essential and editable. (iv) The difficulty audit found a tiny network a
hand-computed pair saturated (1.0) and three held-out draws with degenerate
anchors (witness equal to the wild type, robustness vacuous) — the network grew to
seventeen reactions with pleiotropic enzymes, a shared engineering budget and an
alternative route, the witness is the worst-draw optimum by enumeration, and
degenerate draws are excluded by construction with a defensive zero. All pinned in
`tests/test_round4_new_tasks.py`.

## 7. Robustness and reproducibility

All anchors are recomputed by the same deterministic solver; linprog (HiGHS) is
deterministic on fixed inputs. Development and held-out draws use fresh seeds.
Formal Linux sandbox replay, global evidence refresh and independent replication
are pending.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task MetabolicEngineering/MetabolicStrainDesign \
  --reference verification/reference_solver.py \
  --entry design_strain
```
