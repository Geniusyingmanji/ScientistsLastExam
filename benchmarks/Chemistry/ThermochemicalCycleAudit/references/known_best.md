# Reference and admission record — ThermochemicalCycleAudit

## 1. Reference method

`verification/reference_solver.py` is standalone and uses only public measurements and
the charged laboratory. Weighted least squares over the seven species reconciles Hess
closure; a dominant single outlier is tested by drop-and-refit before any drift test,
because least squares otherwise smears one giant slip across the culprit's own
instrument class and fakes a coherent calibration drift; a class with two or more
members shifted in the same direction (individually large, or all same-signed with a
strong aggregate) is confirmed by one cross-check; the pendant pair is either resolved
by a cross-check or declared underdetermined with reconciled values returned regardless.
It is a method witness, not independent verification; it deliberately lacks robust
(M-estimator or Huber) adjustment, joint model selection over all corruption hypotheses,
and any second confirming query.

## 2. Baseline and normalization

The shipped `solution.py` trusts every reported value and calls the batch consistent.
Measured on 2026-09-05 the baseline scores exactly `0.000000` development and
`0.000000` robustness; the passive auditor defines zero by construction. A
truth-informed auditor (correct verdict, full flags, truth-corrected values) scores
`1.000000` mean mechanism on development worlds.

## 3. Capability comparisons and ablations

Local oracle-direct ablations of the reference, measured 2026-09-05:

| variant | development | robustness | FDR | refusal |
|---|---:|---:|---:|---:|
| full reference | 0.5565 | 0.6555 | 0.00 | 1.00 |
| no laboratory calls | 0.4633 | 0.5046 | 0.00 | 1.00 |
| no corrected values (report raw) | 0.4783 | — | 0.00 | 1.00 |
| never refuse the pendant pair | 0.4261 | — | 0.50 | 0.00 |
| no dominant-outlier pre-test | 0.3747 | — | 0.00 | 1.00 |

Every capability contributes. These are local debugging numbers, not frozen benchmark
evidence.

## 4. Shortcut probes

- Naive single-outlier flagging (largest studentized residual of a plain weighted fit,
  drop-and-refit corrections): **0.202**.
- Always-underdetermined auditor with least-squares corrections: **0.117**.
- Constant instrument-drift claims (each instrument name): **0.000** each.

All sit far below the 0.556 reference. All remaining untested families are admission
risks; passing these probes does not prove the absence of shortcuts.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the competent reference.
Server-held networks and independent thermochemistry review remain required.

## 6. Construction errors and revisions

Four construction errors were caught locally on 2026-09-05 before any model saw the
task. (i) Least squares smears a single giant slip across the culprit's instrument
class, so a coherent-sign drift test fired on transcription worlds — the dominant
single outlier is now drop-and-refit tested first. (ii) Drop-and-refit corrections
silently dropped one row, leaving corrected enthalpies one key short and invalidating
otherwise-correct answers — corrected values are now evaluated for every measurement.
(iii) An absolute chi-square gate false-alarmed a clean world whose background noise
sat at 2.46; the recovery test is now relative to the original tension. (iv) A
coherent drift absorbed by least squares down to four same-signed small residuals fell
below the aggregate detection gate (z 2.22 against 2.3) — the gate is 2.0 with a
lenient cross-check confirmation. All four are pinned in
`tests/test_thermochemical_cycle_audit.py`.

## 7. Robustness and reproducibility

Development and held-out metrics stay separate; the held-out set uses fresh enthalpies,
instruments, noise and corruptions. Determinism was checked by comparing two full
evaluation dictionaries. Formal Linux sandbox replay, global evidence refresh and
independent replication are pending. See the task card citations for background; the
explicitly declared synthetic network is not certified by those publications.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task ChemicalProcess/ThermochemicalCycleAudit \
  --reference verification/reference_solver.py \
  --entry audit_thermochemical_cycle
```
