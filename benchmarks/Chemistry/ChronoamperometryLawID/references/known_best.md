# Reference and admission record — ChronoamperometryLawID

## 1. Reference method

`verification/reference_solver.py` is standalone and uses only the public laws and
the charged potentiostat. Three potential steps (0.15, 0.45, 0.85 V) cover the
amplitude response; every family is fitted to the merged transients by bounded least
squares from two seeds, with an Akaike-style penalty (chi-square plus twice the
parameter count) so extra freedom must pay for itself. A chi-square-per-degree-of-freedom
gate at 3.5 detects the t^-1/4 fractional-transport world. Separately, dividing the
lowest- and highest-potential traces by their public amplitude factors cancels every
supported family and fractional transport; a 4.5-sigma projection of the remaining
signal onto time detects additive drift. It deliberately lacks model averaging, weighted
tail fitting and more than three steps.

## 2. Baseline and normalization

The shipped `solution.py` charges one step, splits probability evenly and guesses
mid-range parameters: `0.000000` development and robustness. The budget is three steps,
exactly the reference's own acquisition tier. A perfect truth-informed answer can still
score one. Tightened scientific tolerances give half parameter credit at 1.73% normalized
RMS error and half prediction credit at 2.89% sealed maximum relative error. Re-measured
on 2026-09-12, the reference reaches `0.798322` development and `0.514162` robustness,
with zero false discoveries and full refusal.

## 3. Capability comparisons and ablations

Local oracle-direct ablations of the hardened reference, measured 2026-09-12:

| variant | development | robustness |
|---|---:|---:|
| full reference | 0.798322 | 0.514162 |
| no anomalous-shape gate | 0.631655 | 0.180828 |
| no cross-potential drift gate | 0.631655 | 0.180828 |
| neither refusal gate | 0.464989 | 0.000000 |

Each gate alone catches exactly one of the two development refusal worlds; neither is
redundant. These are local debugging numbers, not frozen benchmark evidence.

## 4. Shortcut probes

Uniform family probabilities with mid-range parameters score exactly zero. Removing
one reference step reaches `0.788740/0.472766`, below the full reference; one step reaches
`0.589515/0.454747`. A reviewer-reported 960-strategy low-dimensional sweep on the prior
head topped out at `0.152258/0.000000`; because scoring is now stricter, it is retained
only as an upper-bound diagnostic rather than relabelled as a new calibration draw.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the competent reference.
Independent electrochemistry review remains required.

## 6. Construction errors and revisions

Five construction errors were caught locally on 2026-09-05 before any model saw the
task. (i) Drift worlds carried a non-family family field, so every transient raised.
(ii) Validation bounded all three parameter slots, rejecting legal padded
two-parameter answers — inactive slots are now free and parameter scoring uses the
claimed family's active slots. (iii) A tail log-slope refusal test was dominated by
noise (a true Cottrell world measured -0.78) and was replaced by the chi-square gate.
(iv) A residual-correlation drift test misfired in both directions and was replaced
by cross-potential cancellation of the public amplitude factor. (v) The family softmax temperature
flattened probabilities to uniform; scores now sharpen by a factor of four. All are
pinned in `tests/test_pr9_chem_bio_contracts.py`.

The 2026-09-12 review hardening removed the evidence-cost multiplier, reduced the
budget to the reference's three-step tier and tightened the two continuous recovery
axes. The anomalous world now uses a more separated fractional exponent, while drift
is scaled relative to the amplitude-normalized transient. Frozen development and
held-out sets each contain one world caught only by the shape gate and one caught only
by the cross-potential drift statistic.

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
