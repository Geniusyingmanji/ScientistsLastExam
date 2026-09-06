# FedBatchBioprocessDesign reference evidence

## Scoring
Worst-shift productivity is clipped from the constant-feed baseline to a recomputed robust grid witness.
## Anchor
The witness is internal and recomputed; no published process record is used.
## Baseline
Constant feed 0.10 L/h with fixed induction/harvest scores 0.
## Reference
A bounded three-stage grid scores 1.0 development and held out by construction.
## Ablations
Constant feed, exponential-like profiles, nominal-only ranking and fixed induction/harvest remain required probes.
## Shortcut and robustness
Nested arrays, boolean/string rates, invalid lengths, and nonfinite/out-of-range values now
fail closed; the public task supplies all model coefficients, state units, scenario shifts and
Euler boundary conventions needed to implement a simulator independently.
Low dimensionality is an explicit saturation risk; the task cannot pass admission without model and open-loop calibration.
## Provenance
The reduced overflow-control form follows doi:10.1016/j.ifacol.2020.12.1167. Retrieved 2026-09-05.
