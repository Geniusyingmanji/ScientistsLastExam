# Finite-block published-witness envelope

## 1. Reference and provenance

The four anchors are reconstructed states, with rates in bits/channel use:

| n | p | q | Reference rate | Witness |
|---:|---:|---:|---:|---|
| 3 | .08 | .4 | 4.789974718208585e-5 | Zhu et al. 2025, R=2 |
| 4 | .08 | .4 | 7.560948545808554e-5 | Zhu et al. 2025, R=3 |
| 3 | .32 | .1 | 1.1178287051553156e-4 | Zhu et al. 2025, R=3 |
| 4 | .32 | .1 | 1.1801746871108513e-4 | Bausch-Leditzky 2020, Table 10 |

[README.md](README.md) gives the primary-source links, immutable upstream commit,
MIT license, hash-gated MAT reconstruction, printed precision and resource bounds.
[verified_reference.json](verified_reference.json) records individual rates and
the selected pointwise envelope; regenerate it to stdout with
`python benchmarks/Physics/DephrasureCodeDesign/verification/reference_codes.py`.
The finite library and its tensor-product closure are reproducible. They do not
establish an exhaustive current global record or the asymptotic quantum capacity.

## 2. Baseline

The pure product input in [solution.py](../solution.py) is valid, has zero coherent
information and scores zero. Reconstructing the selected public witnesses yields
aggregate score one. Scores above one are retained; they express finite-block
improvement over these anchors only.

## 3. Ablations and capability ladder

The reference audit compares optimized weighted repetitions, six transcribed
2020 NN states, eight 2025 MAT states, transferred nonorthogonal repetition
parameters, and tensor products of all selected lower-n witnesses. The full
numeric comparisons live in [verified_reference.json](verified_reference.json).
This is a witness-family comparison, not a completed model capability-ablation
ladder. In particular, the selected 2020 n=4 (.32,.1) witness exceeds the two
retrieved 2025 states at that same blocklength.

## 4. Shortcut probes

Public witness reconstruction cheaply reaches one. Weighted repetition and
finite-library product closure are already included, so tensoring an available
two-qubit state is accounted for in the four-qubit anchor. The published 2025
nonorthogonal parameters were optimized at n=9; their unchanged transfer has
negative rates at these small-n targets. The small-n family was not globally
optimized, and no low-dimensional shortcut ceiling has been established.

## 5. Frontier draws and calibration

Exploratory testing has occurred. Fresh model-produced objects are being verified
and their results belong in a separate report. No formal SLE calibration run is
recorded, so `lineage.calibration_runs` remains empty. Full-program calibration
and trusted candidate execution are blocked by the H200 sandbox mount permissions.
Neither hard-model difficulty nor long-horizon headroom is established.

## 6. Construction errors and unresolved evidence

The printed n=2 (.08,.4) Table 2 NN amplitudes yield about -4.7105866e-5 bits/use,
whereas the table prints 2.2502e-5. Both independent oracles agree on the transcribed
state. The entry remains disclosed and its printed scalar is not used as an anchor;
no amplitude, sign or index was silently repaired. See [README.md](README.md).
The controller did not explicitly record inherited core-builder model IDs, so
the task card records unknown lineage rather than reconstructing a model ID.

## 7. Robustness and remaining gates

Core tests cover analytic channel limits, pure-input zero information, product
additivity, arbitrary-rank factor normalization, independent tensor Kraus/Gram
agreement, hash-pinned reconstruction, and hostile shapes and values. The initial
published-witness audit's maximum oracle discrepancy was
6.697279449768834e-15 bits/use. The 1e-9 margin is a conservative engineering
tolerance for those checks, not a rigorous interval error bound. Local oracle
timings and their exact environment are in [README.md](README.md); they are not
candidate optimizer timings or H200 evaluation evidence. External domain and
evaluator-security review, trusted sandbox runs, formal calibration, and sustained
headroom measurement remain pending.
