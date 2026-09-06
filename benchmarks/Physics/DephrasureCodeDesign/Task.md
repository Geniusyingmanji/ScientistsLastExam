# DephrasureCodeDesign — finite-block dephrasure input-state design

Find an input quantum state with high coherent information for three or four
independent uses of a dephrasure channel. This is finite-block state design: a
positive score does not establish the channel's asymptotic quantum capacity,
global optimality, an efficient decoder, or experimental performance.

## Entry point and artifact

Implement `design_code(problem)`. Use CPU Python with NumPy/SciPy as needed.
Return exactly `{"real": [...], "imag": [...]}`: two rectangular nested lists of
ordinary finite Python numbers, each with `dimension` rows and the same number
`r` of columns, where `1 <= r <= max_rank`. Boolean, string, complex, NumPy-array,
ragged, nonfinite, extra-field, oversized, and all-zero submissions are invalid.
Every real/imaginary component must have magnitude at most
`max_abs_coefficient`. There are at most 512 scalar components in either shipped
world size. Return `.tolist()` values if constructing arrays with NumPy.

The lists define `X = real + 1j * imag`. The physical input is defined as

\[
\rho=XX^\dagger/\operatorname{tr}(XX^\dagger).
\]

This factor contract includes every density matrix on n qubits when `r=2**n`;
it also permits lower rank. Global nonzero rescaling has no physical effect.
The evaluator rescales X before multiplication for numerical stability. It
does not project an arbitrary submitted matrix onto the density matrices.
Computational basis rows are the binary strings `00...0` through `11...1`, with
the first qubit the most significant bit. The column space is an unconstrained
purifying/reference space.

`problem` is a fresh JSON-compatible dictionary with these complete keys:

| Key | Meaning |
|---|---|
| `n` | Number of identical channel uses, 3 or 4 |
| `p` | Pauli Z-flip probability |
| `q` | Erasure probability |
| `dimension` | Input dimension `2**n` |
| `max_rank` | Maximum factor columns, `2**n` |
| `max_abs_coefficient` | Component magnitude bound, `1e100` |
| `reference_id` | Public witness identifier; not a claim of an optimum |
| `reference_rate` | Recomputed witness-envelope rate, bits per channel use |
| `single_letter_rate` | Optimized one-channel coherent information |
| `numerical_margin` | `1e-9` bits/use, used for qualified reference excess |

The initial `solution.py` returns a pure product input. Its coherent information
is zero and its score is zero. Known reference constructions are public in
`verification/reference_codes.py` and `references/`; they are legitimate seeds.

## Channel and objective

Let J embed a qubit into the first two coordinates of a qutrit, let
`Z=diag(1,-1)`, and let `|e>=(0,0,1)`. One channel use is

\[
\mathcal N_{p,q}(\rho)=(1-q)J[(1-p)\rho+pZ\rho Z]J^\dagger
 +q\operatorname{tr}(\rho)|e\rangle\langle e|.
\]

Its four Kraus matrices are
`sqrt((1-q)*(1-p))*J`, `sqrt((1-q)*p)*J@Z`,
`sqrt(q)*|e><0|`, and `sqrt(q)*|e><1|`.
An entropy-equivalent complementary channel is

\[
\mathcal N^c_{p,q}(\rho)=q\rho\oplus(1-q)\sum_{x=0,1}
 \rho_{xx}|\phi_x\rangle\langle\phi_x|,\qquad
 |\phi_x\rangle=\sqrt{1-p}|0\rangle+(-1)^x\sqrt p|1\rangle.
\]

The raw objective is

\[
 R_n(\rho;p,q)=\frac{S(\mathcal N_{p,q}^{\otimes n}(\rho))-
 S((\mathcal N^c_{p,q})^{\otimes n}(\rho))}{n},\quad
 S(\sigma)=-\operatorname{tr}\sigma\log_2\sigma.
\]

All rates use bits/channel use. `coherent_information` and the independent
`coherent_information_kraus` audit function return **total bits**, so divide
by n. The production calculation conditions on each erasure subset and cancels
the common flag entropy. The audit constructs the complete tensor Kraus/Gram
environment separately. At n=4 these use at most sixteen 16-dimensional
environment blocks versus one 256-dimensional matrix, respectively.

## Frozen worlds and references

These four cases were selected after reconstructing eight published MAT
witnesses, transcribing six old NN witnesses, and recomputing a pointwise
envelope with tensor products of all selected lower-blocklength witnesses.

| n | p | q | Reference rate | Selected witness |
|---:|---:|---:|---:|---|
| 3 | .08 | .4 | 4.789974718208585e-5 | Zhu et al. 2025, R=2 |
| 4 | .08 | .4 | 7.560948545808554e-5 | Zhu et al. 2025, R=3 |
| 3 | .32 | .1 | 1.1178287051553156e-4 | Zhu et al. 2025, R=3 |
| 4 | .32 | .1 | 1.1801746871108513e-4 | Bausch–Leditzky 2020, Table 10 |

The envelope includes optimized weighted repetitions and product closure;
otherwise, for example, the tensor square of a good 2-qubit code is an obvious
4-qubit shortcut. It also evaluates the published 2025 nonorthogonal repetition
parameters at each target n. Those parameters were optimized at n=9 and are
not claimed optimal at n=3/4. This reference suite is a reproducible published
witness envelope, **not an exhaustive current-record assertion**.

## Score and verification boundary

For a valid candidate rate R, single-letter rate L, and reference rate B:

\[
 \mathrm{score}=\max(0,(R-L)/(B-L)).
\]

One matches the frozen reference. Scores above one are retained; the score is
not clipped. `combined_score` averages all four cases. Invalid cases contribute
zero and remain in `per_instance`. The return value of
`evaluate(candidate_callable)` is finite JSON containing `valid`,
`feasibility_rate`, and each case's `raw_rate`, `score`, `reference_rate`,
`single_letter_rate`, `reference_excess=max(0,R-B)`, and
`margin_qualified_excess=max(0,R-B-1e-9)`. The top-level `reference_excess`
averages the **margin-qualified excess in bits/use**. Feasibility is reported
separately from optimization success.

Floating-point eigenvalues at the roundoff scale are handled numerically;
there is no entropy smoothing or formal interval certificate. The initial
published-witness audit had maximum dual-oracle discrepancy
`6.70e-15` bits/use. The `1e-9` excess margin is conservative for those checks,
not a mathematical proof of positivity or optimality. Larger excesses should
still be independently recomputed from the submitted factor.

The verifier bounds artifact shape, coefficient magnitude, numerical dimensions,
and trusted reference resource sizes. `evaluate` is a callable adapter, not a
security sandbox or an in-process timeout mechanism. Candidate CPU time, memory,
process isolation, and output transport limits must be enforced by the outer
runner. This task resource does not launch GPU work or change that runner.

Useful invariants: every pure input has zero coherent information; q=1 gives
`-S(rho)` total bits; the p=0 erasure channel has optimal rate
`max(0,1-2*q)`; q=0 has optimal rate `1-h2(p)`; at p=0,q=.5 every input has zero
coherent information. The single-input erasure identity
`Ic=(1-2*q)*S(rho)` must not be applied to arbitrary entangled n-use inputs.

## Sources

- [Leditzky–Leung–Smith 2018](https://arxiv.org/html/1806.08327v3), equations (8)–(9), (17)–(19), Appendix F: channel, complement, repetition expression, and shared positivity threshold.
- [Bausch–Leditzky 2020](https://arxiv.org/pdf/1806.08781v2), section 4.2 and Tables 2, 10: NN code-state amplitudes.
- [Bhalerao–Leditzky 2025](https://arxiv.org/html/2508.09978v1#S5.SS2), section 5.2: nonorthogonal repetition family; its n=9 rate is not compared as an n=4 same-budget reference.
- [Zhu et al. 2025](https://arxiv.org/html/2509.15106v2#S4.SS4), section 4.4, Tables 6 and 9: small-blocklength Riemannian code-state optimization.
- [Yu et al. 2020 experiment](https://arxiv.org/abs/2003.13000): physical motivation, not a numerical optimum oracle.
