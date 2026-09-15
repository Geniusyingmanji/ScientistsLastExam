# Dephrasure reference resources

All numerical anchors are reconstructed from code-state witnesses, never from
printed scalar scores. `verified_reference.json` is the frozen audit output.
Recompute it without modifying any files:

```sh
python benchmarks/Physics/DephrasureCodeDesign/verification/reference_codes.py
```

The output lists each individual rate, the independent Kraus rate, their
difference, and the pointwise/tensor-product winners. Auditing rounds near zero
may vary with LAPACK/BLAS versions; the semantic comparison uses numerical
tolerances rather than byte identity.

## Published 2025 MATLAB witnesses

Eight files named `Dephrasure_{008,032}_R{2,3}_n{3,4}.mat` are byte-for-byte
downloads from the immutable upstream commit
`8af23430a130a66dbfe888dcdbe87894b0cf265a` of
[Chengkai-Zhu/qcapacity-rieopt](https://github.com/Chengkai-Zhu/qcapacity-rieopt/tree/8af23430a130a66dbfe888dcdbe87894b0cf265a/data/Dephrasure_codestates),
retrieved 2026-09-06. The original MIT license is included. Each file is smaller
than 3 KB; the loader caps the file at 10 KB and verifies its frozen SHA-256
before parsing. Hashes are in `verification/reference_codes.py`.

The MAT data contain numeric local unitaries in `best_psi.R1`, `Main`, `R2`,
plus `best_cost`. `scipy.io.loadmat` parses these fields; no MATLAB commands,
pickles, third-party Python, or saved executable model objects run. The
reconstruction follows the published
[cohinfo_cost_localU.m](https://github.com/Chengkai-Zhu/qcapacity-rieopt/blob/8af23430a130a66dbfe888dcdbe87894b0cf265a/Q_lowerbound/cohinfo_cost_localU.m)
and `apply_local_unitary.m`: start in `|0>_(R,A1,...,An)`, apply R1, forward and
backward adjacent unitaries, then R2. Reshape the resulting pure state as
`(reference_dimension,2**n).T` to obtain X. Dimensions, numeric dtypes, finite
entries, and unitarity are checked. All eight reconstructed rates agree with
the stored cost and with the independent full-channel oracle; the stored cost
is only an audit comparison.

## Other numerical inputs

`nn2020.json` contains factual sparse amplitudes from Tables 2 and 10 of
[1806.08781v2](https://arxiv.org/pdf/1806.08781v2), published as NJP 22, 023005
(2020). The binary indices are `A^n|R`; the nonzero amplitudes are transcribed
as printed and the entire state is normalized. Precision is limited to the
printed four decimals. At (.32,.1), the n=4 NN witness recomputes to
`0.00011801746871108513`, exceeding both retrieved 2025 n=4 witnesses and
their available product alternatives. It therefore remains an anchor.

There is one unresolved data discrepancy: the printed n=2 Table 2 amplitudes
at (.08,.4) recompute to approximately `-4.7105866e-5`, while the printed rate
is `2.2502e-5`. Both independent oracles agree on the reconstructed state.
We retain this entry for transparency and never use its printed rate as an
anchor. The other five transcribed NN witnesses agree with their reported
rates to the expected printed precision. The origin of the discrepant table
entry has not been established; it could require corrected/full-precision
author data. No sign, amplitude, or basis index was silently repaired.

`nonorthogonal2025.json` records the mixture weights and single-qubit matrices
from [the official Table 4 evaluator](https://github.com/sujeet-bhalerao/perm-inv-codes/blob/main/eval_codes.m)
for [2508.09978v1](https://arxiv.org/html/2508.09978v1#S5.SS2). Each intended pure
single-qubit code state is recovered from its dominant eigenvector; the source
matrices have only rounded residual eigenvalues. These parameters were
optimized at n=9; transferring them unchanged to n=1..4 gives negative rates
at our two parameter pairs. This observation does not rule out better
nonorthogonal parameters at small n. The full small-n ansatz was not globally
optimized in this resource implementation.

## Reference envelope and limitations

For each (p,q), the audit considers all above witnesses available at n, the
weighted-repetition optimum, and every split k+(n-k) using the best available
lower-n states. The repetition search uses a fixed logit grid plus bounded
scalar refinement. Product additivity makes this dynamic program the complete
tensor-product closure of this finite witness library. It is not exhaustive
over all published codes or all density matrices. Public construction lookup
can attain score one: the benchmark measures finding additional improvements,
not novelty from concealing these known inputs.

The dual-oracle witness discrepancy was at most `6.697279449768834e-15`
bits/use on macOS arm64, NumPy 2.2.6, SciPy 1.18.1. The `1e-9` margin in the
task is an engineering tolerance, not a rigorous floating-point error bound.
CPU timing on that local environment: n=3 fast oracle mean 0.942 ms (50
repeats), full Kraus 2.845 ms (10 repeats); n=4 fast oracle 3.105 ms (50
repeats), full Kraus 45.539 ms (10 repeats). One fixed random full-rank state
was used at each n after warm-up. These are local measurements, not Linux,
H200, GPU, optimizer runtime, or universal latency claims.

Freshness check as of 2026-09-06: [2507.16920v2](https://arxiv.org/html/2507.16920v2#S5)
(published in PRA in January 2026) supplies perturbative/private-information
results, not a replacement small-n numeric code library. The search does not
justify an exhaustive state-of-the-art or exact quantum-capacity claim.
