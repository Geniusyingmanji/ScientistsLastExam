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
the oracle at scoring time. The frozen witness design is `{knockouts: [overflow],
overexpressions: {product: 2.0, pdh: 2.0}}`; better designs score above one.

## 3. Capability comparisons and ablations

| variant | development | robustness |
|---|---:|---:|
| full reference | 0.9982 | 1.000 |
| greedy on nominal capacities only | 0.9982 | — |
| single pdh overexpression | ≈0.67 | — |

After the stratified-draw fix both greedy variants converge on the same edits on
these worlds; before it, nominal-only greedy stopped after one edit and lost a third
of the score. Local debugging numbers, not frozen benchmark evidence.

## 4. Shortcut probes

A single pdh×1.5 edit closes most of the gap (0.67); the record side requires
beating the witness on capacity-corner draws, which single edits cannot. No
parameterized family dominates; the artifact is the edit set itself.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not beat the witness. Independent
metabolic-engineering review remains required.

## 6. Construction errors and revisions

Three construction errors were caught locally on 2026-09-05. (i) The first witness
multiplier ladder made the witness the linear-program optimum, so the uncapped
record was unreachable — relaxed to a beatable ladder. (ii) The reference computed
the biomass gate from edited capacities, making knockout candidates look viable at
zero demand; the gate now uses un-engineered capacities per draw, matching the
oracle. (iii) biosynthesis was listed as both essential and editable. All pinned in
`tests/test_metabolic_strain_design.py`.

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
