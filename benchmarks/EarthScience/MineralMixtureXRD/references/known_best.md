# Reference and admission record — MineralMixtureXRD

## 1. Reference method

`verification/reference_solver.py` is standalone: nonnegative least squares over
the library feature positions on the free coarse scan, refinement by charged
slow windows at the strongest peaks of the top candidates (noise-weighted merge),
fraction normalization over the survivors, and refusal when the coarse fit
residual carries local-contrast sharpness — a rise over the half-degree
neighborhood that a broad amorphous hump cannot produce but a sharp unknown peak
must. It deliberately lacks full-pattern refinement, per-peak width fitting and
amorphous quantification.

## 2. Baseline and normalization

The shipped `solution.py` claims a fixed fifty-fifty calcite-quartz mixture:
`0.000000`. A truth-informed claim scores one. Measured on 2026-09-05 the
reference reaches `0.3961` development and `0.4504` robustness with zero false
discoveries and full refusal.

## 3. Capability comparisons and ablations

| variant | development | refusal |
|---|---:|---:|
| full reference | 0.396 | 1.00 |
| coarse NNLS only (no slow windows) | 0.328 | 1.00 |
| no sharpness gate | 0.328 | 0.50 |

Slow-window refinement and the sharpness gate each carry part of the score. Local
debugging numbers, not frozen benchmark evidence.

## 4. Shortcut probes

Fixed two-mineral claims score zero; top-three-by-tallest-peak with uniform
fractions scored 0.156 before the library fix and the weaker fixed baseline ships
instead. The mixture axis resists naive matching because library peaks overlap.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the reference on the
mixture and refusal axes together.

## 6. Construction errors and revisions

Four construction errors were caught locally on 2026-09-05. (i) Noise was absolute
rather than relative to peak intensity, making coarse scans nearly noiseless. (ii)
Mica's strongest peak sat below the observable range (library peaks moved in
range). (iii) A matched-filter presence test cross-contaminated overlapping peaks
and called every mineral present (replaced by nonnegative least squares). (iv) The
sharpness gate fired on legitimate width-mismatch residuals (fit width widened,
gate recalibrated, local-contrast form). All pinned in
`tests/test_mineral_mixture_xrd.py`.

## 7. Robustness and reproducibility

Development and held-out mixtures use fresh seeds; noise draws are seeded per scan
call. Determinism was checked by comparing two full evaluation dictionaries.
Formal Linux sandbox replay, global evidence refresh and independent replication
are pending.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task Mineralogy/MineralMixtureXRD \
  --reference verification/reference_solver.py \
  --entry identify_minerals
```
