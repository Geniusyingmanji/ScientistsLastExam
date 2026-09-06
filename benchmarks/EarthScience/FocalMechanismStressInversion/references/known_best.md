# Reference and admission record — FocalMechanismStressInversion

## 1. Reference method

`verification/reference_solver.py` is standalone and uses only the public catalog and
the charged re-analysis budget. Multi-start plane-choice initialization (all-a, all-b,
six seeded random rows), alternating linear least-squares deviatoric-tensor fits with
per-event plane swaps, re-analysis of the worst-misfit events within budget, and
refusal when the converged misfit distribution exceeds a mean of 18 degrees or a 35
degree tail fraction of 0.18. It is a method witness, not independent verification; it
deliberately lacks bootstrapped confidence intervals, gridded four-dimensional global
search, and multi-regime clustering.

## 2. Baseline and normalization

The shipped `solution.py` fits one tensor on the first-listed planes without iteration,
budget use or regime checks, and never abstains. Measured on 2026-09-05 the baseline
scores exactly `0.000000` development and `0.000000` robustness; submitting the true
axes, ratio and plane row scores one.

## 3. Capability comparisons and ablations

Local oracle-direct ablations of the reference, measured 2026-09-05:

| variant | development | robustness | FDR | refusal |
|---|---:|---:|---:|---:|
| full reference | 0.6983 | 0.7307 | 0.00 | 1.00 |
| no re-analysis spend | 0.7195 | 0.6874 | 0.00 | 1.00 |
| no multistart (all-a only) | 0.6983 | 0.7307 | 0.00 | 1.00 |
| no refusal gates | 0.0983 | 0.0000 | 1.00 | 0.00 |

Re-analysis trades development smoothness for held-out robustness on these seeds; the
multistart is neutral on the frozen world set (it is insurance against the
plane-assignment local optimum observed during construction under an earlier converge
schedule) and the refusal gates carry most of the score. These are local debugging
numbers, not frozen benchmark evidence.

## 4. Shortcut probes

- Constant-regime family (twelve fixed azimuths, R = 0.5, plane-a everywhere):
  **0.000** best.
- Removing the refusal gates (always report): **0.098** with false-discovery rate 1.0.

No tested low-dimensional family approaches the reference. All remaining untested
families are admission risks; passing these probes does not prove the absence of
shortcuts.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the competent reference.
Server-held catalogs and independent seismology review remain required.

## 6. Construction errors and revisions

Three construction errors were caught locally on 2026-09-05 before any model saw the
task. (i) The plane-row generator referenced an undefined loop variable and invalidated
every reference run. (ii) A single-start fit converged to a plane-assignment local
optimum on a held-out world (mean misfit 26.6 degrees) and falsely abstained a
supported catalog; the converge schedule and starts were rebuilt. (iii) Refusal gates
set against pre-reanalysis misfits misfired in both directions — a mixed world passed
(mean 21.3 against a 22-degree gate) and a supported world failed; gates were
recalibrated against the converged distribution (18 degrees / 0.18 tail). All three
are pinned in `tests/test_focal_mechanism_stress_inversion.py`.

## 7. Robustness and reproducibility

Development and held-out metrics stay separate; the held-out set uses fresh tensors,
mixtures, incoherent catalogs and noise. Determinism was checked by comparing two full
evaluation dictionaries. Formal Linux sandbox replay, global evidence refresh and
independent replication are pending. See the task card citations for background; the
explicitly declared synthetic catalog is not certified by those publications.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task Geophysics/FocalMechanismStressInversion \
  --reference verification/reference_solver.py \
  --entry infer_stress_orientation
```
