# Reference and admission record — ExactIdentityEvidence

## 1. Reference method

`verification/reference_solver.py` is standalone and uses only the published digits
and the charged library. Every claim gets a brute-force best-fit coefficient row at
base precision; gross failures (relative residual above 1e-6) are rejected outright;
claims containing a value whose public cap sits below the epsilon-floor exponent are
refused without spending; the remaining budget completes claims fewest-missing-values
first at the 80-digit tier, certifying exact (residual identically zero) or false
(nonzero residual). It is a method witness, not independent verification; it
deliberately lacks 150-digit escalation, adaptive replanning, and any treatment of
the gamble between certified and guessed verdicts beyond honest refusal.

## 2. Baseline and normalization

The shipped `solution.py` refuses every claim without spending — the passive floor,
scoring exactly `0.000000`. A truth-informed verdict vector (correct verdict and row
everywhere) scores one. Measured on 2026-09-05 the reference reaches `0.900`
development and `0.925` robustness with zero false discoveries.

## 3. Capability comparisons and ablations

Local oracle-direct ablations of the reference, measured 2026-09-05:

| variant | development | robustness | FDR |
|---|---:|---:|---:|
| full reference | 0.900 | 0.925 | 0.00 |
| no purchases (cap refusal + base rows only) | 0.600 | — | 0.083 |
| no cap-driven refusal | 0.850 | — | 0.042 |
| gamble on uncovered claims (call them exact) | 0.633 | — | 0.056 |

Every capability contributes; refusing to gamble is what keeps the false-discovery
rate at zero. These are local debugging numbers, not frozen benchmark evidence.

## 4. Shortcut probes

- Base-precision-only auditor (reject gross, call every near-zero claim exact with
  its fitted row, never purchase): **0.600**.
- All-exact with fixed rows: near the passive floor (wrong rows score 0.5 on true
  claims only).
- All-false: negative on true relations (the −0.5 penalty), below the passive floor.

The 0.600 shortcut sits well below the 0.900 reference; the certification and refusal
gap is the remaining difficulty. All remaining untested families are admission risks;
passing these probes does not prove the absence of shortcuts.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the competent reference.
Server-held worlds and independent mathematics review remain required.

## 6. Construction errors and revisions

Three construction errors were caught locally on 2026-09-05 before any model saw the
task. (i) Epsilon values had random vectors, so their claims failed grossly instead
of subtly — the vectors now cancel the claim coefficients exactly, leaving the
epsilon as the only residual. (ii) The certification gate checked the maximum instead
of the minimum precision cap across a claim's values, letting capped claims through
to a gamble. (iii) The default Decimal context (28 digits) silently rounded 80-digit
residuals, corrupting certification in both directions; the reference now pins a
400-digit context, and the rule is documented for candidates. All three are pinned in
`tests/test_exact_identity_evidence.py`.

## 7. Robustness and reproducibility

The six base series (Machin pi, atanh logarithms, Newton square roots, factorial e,
integer golden ratio) are pure-integer and were checked against known digits; exact
residuals are integer identities, so determinism is exact. Development and held-out
worlds use fresh seeds, epsilons and cap placements. Formal Linux sandbox replay,
global evidence refresh and independent replication are pending.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task Mathematics/ExactIdentityEvidence \
  --reference verification/reference_solver.py \
  --entry audit_identity_claims
```
