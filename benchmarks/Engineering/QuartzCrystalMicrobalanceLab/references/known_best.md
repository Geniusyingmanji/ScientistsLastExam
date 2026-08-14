# Known best — QuartzCrystalMicrobalanceLab

## Anchor

`verification/reference_qcm.py` analyses the raw signal chain, run through the task's own
evaluator. It works from the supplied problem alone and never reads the hidden world.

Reproduce with:

```bash
python scripts/measure_reference.py --task Engineering/QuartzCrystalMicrobalanceLab \
    --reference verification/reference_qcm.py --entry analyze_qcm
```

| | every recorded model proposal | reference |
|---|---:|---:|
| `combined_score` | 0.0000 | **0.8330** |
| `development_mechanism_score` | 0.0 | **0.9585** |
| `heldout_mechanism_score` | — | 0.9477 |
| `development_supported_claim_coverage` | 0.0 | 1.0 |
| `development_false_discovery_rate` | 0.0 | 0.0 |
| `development_unsupported_refusal_rate` | 1.0 | 1.0 |

The diagnosis is correct on **10 of 10** worlds across both splits.

## What the reference does

1. **Calibrate** — each block gives eight records of a known admittance beside its raw I/Q counts,
   so `raw = offset + gain * admittance` is a two-parameter complex least squares. The blocks
   bracket the run and the instrument drifts linearly between them, so every sweep is calibrated
   at its own capture index.
2. **Extract** — conductance, the real part of the calibrated admittance with the shunt removed,
   peaks at resonance. The peak frequency, refined parabolically on its neighbours, and the
   half-power width give the resonance frequency and quality factor without a full BVD fit.
3. **Weigh** — Sauerbrey per harmonic, `delta_f_n / n = -S * mass`, which is what makes overtone
   dispersion visible at all.
4. **Diagnose** — four measured tests, in order.

## The measured tests

| world kind | dispersion span | 20 s linearity | conjugate ratio | peak / ADC |
|---|---|---|---|---|
| `rigid_linear` | 0.004 – 0.006 | 0.001 – 0.004 | 2033 – 4055 | 0.58 – 0.72 |
| `rigid_missing` | 0.105, 0.281 | 0.003 – 0.069 | 1903 – 3395 | 0.61 – 0.75 |
| `viscoelastic` | 0.157, 0.160 | 0.002 – 0.005 | 3343 – 3755 | 0.66 – 0.72 |
| `rate_change` | 0.002 | 0.123 | 3767 | 0.64 |
| `iq_conjugated` | 1.243 | 0.757 | **0.963** | 0.64 |
| `clipped` | 0.029 | 0.001 | 6237 | **1.000** |

Clipping, the changing rate and the conjugated quadrature each separate on a single number.
Dispersion does not, and that is the part worth recording.

## Overtone dispersion is a trend, not a spread

Judging dispersion by how far the per-harmonic masses scatter marks the wrong worlds. One
`rigid_missing` world scatters at 0.281 — wider than either real viscoelastic world, at 0.157 and
0.160 — because missing raw samples corrupt one harmonic's resonance estimate.

The per-harmonic masses say why:

| world | n=1 | n=3 | n=5 |
|---|---|---|---|
| `viscoelastic` | 1.095 | 1.299 | 1.478 |
| `viscoelastic` | 1.221 | 1.454 | 1.623 |
| `rigid_missing` | 1.330 | 1.200 | 1.203 |
| `rigid_missing` | 0.770 | 0.991 | 0.773 |

Viscoelastic loading rises **monotonically** with harmonic; missing samples produce a single
outlier in whichever harmonic lost data. Requiring a monotone trend before calling it dispersion
separates them, and the span threshold then only has to clear the rigid worlds, which drift by
about 0.01. That change took the diagnosis from 6 of 10 correct to 10 of 10.

## A contract defect this reference found

The submission's calibration dictionary must use exactly `start_offset_counts`,
`end_offset_counts`, `start_complex_gain_counts_per_siemens` and
`end_complex_gain_counts_per_siemens`. Those four names appeared **nowhere** in the task prompt,
which said only "start/end complex offsets and complex gains". A submission with any other key
set is rejected before it is scored, so guessing the names wrong costs everything and the
resulting zero is indistinguishable from one earned on the science. The names are now in the
prompt, and `scripts/audit_documented_keys.py` checks this side of the interface across the
inventory.
