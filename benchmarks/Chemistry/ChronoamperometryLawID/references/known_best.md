# Reference and admission record — ChronoamperometryLawID

## 1. Reference method

`verification/reference_solver.py` is standalone and uses only the public laws and
the charged potentiostat. Three potential steps (0.15, 0.45, 0.85 V) cover the
amplitude response; every family is fitted to the merged transients by bounded least
squares from two seeds, with an Akaike-style penalty (chi-square plus twice the
parameter count) so extra freedom must pay for itself; refusal fires when the best
chi-square per degree of freedom exceeds 2.2 (no family can absorb fractional
transport or strong drift) or when a variable projection of a shared linear time
term across all three potentials is significant beyond three standard errors and
0.02 units. It deliberately lacks information-criterion model averaging, weighted
tail fitting and more than three steps.

## 2. Baseline and normalization

The shipped `solution.py` charges one step, splits probability evenly and guesses
mid-range parameters: `0.000000` development and robustness. Submitting the true
family with sharp probabilities, true active parameters and the sealed extrapolation
scores one only at the zero-cost ideal ceiling. Supported-world mechanism recovery is multiplied
by `1 - 0.50 * budget_used / 6`; correct-refusal credit stays unweighted and separately reported.
The three-step reference has evidence efficiency `0.750`. Re-measured on 2026-09-06, it reaches
`0.721861` development and `0.661269` robustness with zero false discoveries and full refusal.

## 3. Capability comparisons and ablations

Local oracle-direct ablations of the reference, measured 2026-09-05, remeasured
2026-09-07 under evidence-efficiency weighting:

| variant | development | robustness |
|---|---:|---:|
| full reference | 0.721861 | 0.661269 |
| no Akaike penalty (raw chi-square selection) | 0.656793 | 0.661269 |
| chi-square gate alone disabled | 0.721861 | 0.327936 |

The freedom penalty is load-bearing (without it the three-parameter surface law beats
the one-parameter Cottrell law on noise); the chi-square gate is redundant with the
drift projection on the frozen worlds but guards the level-2/3 noise ladders. These
are local debugging numbers, not frozen benchmark evidence.

## 4. Shortcut probes

Uniform family probabilities with mid-range parameters score exactly zero, and any
single-family constant guess is capped by the class-probability term. No
low-dimensional family reaches the reference; the artifact is a functional fit, so
shortcut risk concentrates in fitting skill, which is the intended difficulty.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the competent reference.
Independent electrochemistry review remains required.

## 6. Construction errors and revisions

Five construction errors were caught locally on 2026-09-05 before any model saw the
task. (i) Drift worlds carried a non-family family field, so every transient raised.
(ii) Validation bounded all three parameter slots, rejecting legal padded
two-parameter answers — inactive slots are now free and parameter scoring uses only
the true family's active slots. (iii) A tail log-slope refusal test was dominated by
noise (a true Cottrell world measured -0.78) and was replaced by the chi-square gate.
(iv) A residual-correlation drift test misfired in both directions and was replaced
by variable projection of the shared linear term. (v) The family softmax temperature
flattened probabilities to uniform; scores now sharpen by a factor of four. All are
pinned in `tests/test_chronoamperometry_law_id.py`.

## 7. Robustness and reproducibility

Development and held-out metrics stay separate; the held-out set uses fresh families,
parameters and failures. Determinism was checked by comparing two full evaluation
dictionaries. Formal Linux sandbox replay, global evidence refresh and independent
replication are pending. The cited textbook motivates the families; the declared
closed forms are the contract.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task Electrochemistry/ChronoamperometryLawID \
  --reference verification/reference_solver.py \
  --entry identify_current_law
```
