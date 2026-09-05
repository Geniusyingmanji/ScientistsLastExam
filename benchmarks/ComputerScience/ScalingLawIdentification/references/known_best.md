# Reference and admission record — ScalingLawIdentification

## 1. Reference method

`verification/reference_solver.py` is standalone: a seven-size ladder (16, 32, 64,
128, 256, 256, 1024) that covers both mod-3 residue classes of a branching runtime
and repeats one size for the noise floor; per-class one-parameter log-space
regression with an exponent penalty (and a closed form for the constant class); a
split-fit branch test (refuse when the two residue-class subsets choose different
classes and each fits four times better than the pooled fit); a jitter gate (refuse
when the repeat-estimated noise floor exceeds fifteen percent). It deliberately
lacks adaptive ladders and information-criterion averaging.

## 2. Baseline and normalization

The shipped `solution.py` times one size and guesses uniformly: `0.000000`. A
truth-informed claim scores one. Measured on 2026-09-05 the reference reaches
`0.9294` development and `0.6223` robustness with zero false discoveries and full
refusal.

## 3. Capability comparisons and ablations

| variant | development |
|---|---:|
| full reference | 0.9294 |
| jitter gate disabled | 0.7627 |
| no repeated size (no noise estimate) | 0.7627 |

Local debugging numbers, not frozen benchmark evidence.

## 4. Shortcut probes

Uniform probabilities with a fixed scale score zero; the discriminating axes are the
class probability sharpening and the sealed extrapolation. No low-dimensional family
reaches the reference.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the reference.

## 6. Construction errors and revisions

Five construction errors were caught locally on 2026-09-05. (i) Jitter worlds
carried a non-class family field and crashed the oracle. (ii) The constant class had
no shape column and its regression went degenerate. (iii) After the ladder grew, the
repeated-size index pointed at a unique size and the jitter gate silently skipped.
(iv) The branch split held one point. (v) The branch criterion compared regression
exponents that are both near one by construction; it now compares split-versus-pooled
residuals. All pinned in `tests/test_scaling_law_identification.py`.

## 7. Robustness and reproducibility

Development and held-out worlds use fresh seeds; branch runtimes are exact functions
of the size. Determinism was checked by comparing two full evaluation dictionaries.
Formal Linux sandbox replay, global evidence refresh and independent replication are
pending.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task Algorithm/ScalingLawIdentification \
  --reference verification/reference_solver.py \
  --entry identify_scaling_law
```
