# Reference and admission record — ThermochemicalCycleAudit

## 1. Reference method

`verification/reference_solver.py` is standalone and uses only public measurements and
the charged laboratory. Weighted least squares over the eight species reconciles Hess
closure; every non-ambiguous row is tested by drop-and-refit before any drift test,
because least squares otherwise smears one giant slip across the culprit's own
instrument class and fakes a coherent calibration drift; a class with two or more
members shifted in the same direction (individually large, or all same-signed with a
strong aggregate) is confirmed by one cross-check; the pendant pair is either resolved
by a cross-check or declared underdetermined with reconciled values returned regardless.
It is a method witness, not independent verification; it deliberately lacks robust
(M-estimator or Huber) adjustment, joint model selection over all corruption hypotheses,
and any second confirming query.

## 2. Baseline and normalization

**2026-09-08 correction:** R12/R13 now form the only observations of the eighth
species. The original pair duplicated R8 and was identifiable from the core; its
replicates also incorrectly erased the offset. The repaired model has rank 7 over
8 species, randomizes the faulty pair member, and preserves its systematic offset
in same-instrument replicates. A noise-free algebraic test exhibits two different
fault attributions producing exactly the same observations without a cross-check.

Both all-consistent and all-underdetermined strategies now normalize to zero, even
with better corrections. Oracle-direct debugging on the hardened head gives baseline 0,
reference development 0.535168 and heldout 0.565973. Both development rank-deficient
worlds are resolved by cross-checks, so `resolved_world_count = 2` and the eligible
refusal denominator is zero; `development_correct_refusal_rate` is therefore `null`.
Coverage is divided by the six worlds in which an attribution is warranted after the
reference's queries. These are local debugging results.


The shipped `solution.py` trusts every reported value and calls the batch consistent.
Measured on 2026-09-05 the baseline scores exactly `0.000000` development and
`0.000000` robustness; the passive auditor defines zero by construction. A
truth-informed auditor (correct verdict, full flags, truth-corrected values) scores
`1.000000` mean mechanism on development worlds.

## 3. Capability comparisons and ablations

Local oracle-direct ablations of the current reference, measured 2026-09-12:

| variant | development | robustness | FDR | refusal |
|---|---:|---:|---:|---:|
| full reference | 0.535168 | 0.565973 | 0.00 | null¹ |
| largest-residual-only drop/refit | 0.535168 | 0.233600 | 0.00 | null¹ |
| no rank-deficient-branch resolution | 0.509228 | 0.554594 | 0.00 | 1.00 |
| no drift diagnosis | 0.314229 | 0.422570 | 0.00 | null¹ |

¹ The reference resolves every eligible development refusal world; a rate with a zero
denominator is intentionally null. Every capability changes a target axis. These are
local debugging numbers, not frozen benchmark evidence.

## 4. Shortcut probes

- Always-underdetermined and always-consistent auditors: **0.000000** each under the
  current two-null normalization.
- Naive single-outlier flagging on the repaired network: **0.015436** (reviewer replay).
- A 264-setting three-parameter rule (chi-square gate × dominant-residual gate ×
  rank-deficient-branch policy): **0.448770/0.250966** development/robustness. This is
  retained as reviewer provenance.
- The stronger executable `verification/probe_three_gate_rules.py` derives the
  rank-deficient pair from antiparallel stoichiometric rows and makes no laboratory
  calls: **0.509228/0.382935**. It is below the repaired reference on both splits, but
  only 4.85% below on development, so the narrow margin remains an explicit admission
  risk rather than being described as safely dominated.

The task remains candidate until the development/robustness tradeoff and stronger robust
adjustment are independently calibrated.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the competent reference.
Server-held networks and independent thermochemistry review remain required.

## 6. Construction errors and revisions

Four construction errors were caught locally on 2026-09-05 before any model saw the
task. (i) Least squares smears a single giant slip across the culprit's instrument
class, so a coherent-sign drift test fired on transcription worlds — every
non-ambiguous row is now drop-and-refit tested before drift classification; choosing
only the largest residual fails both held-out single-fault worlds. (ii) Drop-and-refit corrections
silently dropped one row, leaving corrected enthalpies one key short and invalidating
otherwise-correct answers — corrected values are now evaluated for every measurement.
(iii) An absolute chi-square gate false-alarmed a clean world whose background noise
sat at 2.46; the recovery test is now relative to the original tension. (iv) A
coherent drift absorbed by least squares down to four same-signed small residuals fell
below the aggregate detection gate (z 2.22 against 2.3) — the gate is 2.0 with a
lenient cross-check confirmation. All four are pinned in
`tests/test_thermochemical_cycle_audit.py`.

The 2026-09-08 review also corrected the reference degrees of freedom to use the
actual design rank, prevented invalid submissions from registering as discoveries,
and separated actual clean-world counts from false-discovery eligibility counts.
The public citation for doi:10.1021/acs.jpca.6c03567 is Bross, Thorpe & Ruscic (2026),
not the previously stated 2024 date; the DOI supports network auditing, not the
original synthetic network's unidentifiability claim.

The 2026-09-12 hardening removes the rank-deficient measurements' ids, instrument class
and scoring branch predicates from candidate-facing prose. Candidates must recover the
ambiguous branch from the published stoichiometric rank. Refusal rates now return null
when no world remains unresolved, and discovery coverage uses only post-query worlds in
which attribution is warranted.

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
