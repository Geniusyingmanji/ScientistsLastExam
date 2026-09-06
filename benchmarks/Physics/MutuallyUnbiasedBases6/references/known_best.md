# Reference provenance and measured local controls

Scope: approximate four-basis optimization under the finite Gaussian-integer ray
contract. This representation excludes exact three-MUB sets including I in d=6;
see [the field obstruction and metric](scientific_basis.md). No result here proves
global optimality or resolves the unrestricted MUB existence question.

The constructive reference is Philippe Raynal, Xin Lü, and Berthold-Georg Englert,
[Phys. Rev. A 83, 062303 (2011)](https://doi.org/10.1103/PhysRevA.83.062303),
[arXiv:1103.1025v1](https://arxiv.org/html/1103.1025v1). Eqs.(5)–(6),(19)–(22)
specify the matrices and the algebraic value ASD≈0.998291692700123872407237,
SSE≈0.05124921899628383. This is a published construction matching numerical
searches; the paper does not establish its optimum over all complex bases.

Source status checked 2026-09-06: [McNulty–Weigert's March 2026 review,
§8.2](https://arxiv.org/html/2410.23997v2#S8.SS2) retains the same numerical
construction. [The August 2026 order-six Hadamard classification
preprint](https://arxiv.org/html/2608.18053v1) treats classification and identifies
the MUB problem as open; classification alone does not settle existence of four
MUB or this objective's global optimum. These source checks are not an exhaustive
claim about all unpublished or subsequent results.

## Fixed rational fixture

`raynal_rays.json` contains exactly three legal row-major integer-pair matrices,
generated from the public constructor with binary64 NumPy arithmetic, rounded at
2**32, then exactly orthogonalized by the public Gaussian-integer helper. Its
largest coordinate uses 288 bits, below the 384-bit limit. On the checked fixture:

`ASD = 0.998291692700123872383322928599388780053382140818387621155358…`

The evaluator recomputes this rational value to define score one. It certifies
orthogonality and overlaps of the stored integer data; it does not certify that
floating evaluation of the source equations was exact. Retrieval of the formula
or raising quantization precision is an expected shortcut, not a research result.

From the repository root, inspect deterministic regeneration and verify it:

```sh
python benchmarks/Physics/MutuallyUnbiasedBases6/verification/reference_bases.py --fixture emit
python benchmarks/Physics/MutuallyUnbiasedBases6/verification/reference_bases.py --fixture check
python -m pytest tests/test_mutually_unbiased_bases6.py -q
```

The emitter prints the proposed full JSON. Any intentional fixture replacement
must be reviewed as a change to the benchmark's score scale; the oracle never
updates it during evaluation. The exact fixture is authoritative if floating
libraries differ. Checked runtime: CPython 3.12.14, NumPy 2.2.6 (macOS).

The independent algebraic enclosure is

```
L = 0.998291692700123872407236997915274208142963984204791432826106…
U = 0.998291692700123872407237312968554531999133782663433152627969…
```

These decimals display the rational endpoints; the evaluator returns their exact
hexadecimal ratios. A 36-bit conversion attains
0.998291692700123872407173886836217069352095515415890319202841…,
which is strictly above the fixed fixture but still below U by about 6.34×10⁻²³.
It correctly receives `beyond_rational_fixture=true` and
`beyond_published_reference=false`. A 20-bit conversion differs from the algebraic
value by about 4.83×10⁻¹³. Both are covered by tests with independent SymPy bounds.

## Local reference controls measured 2026-09-06

Command: `python benchmarks/Physics/MutuallyUnbiasedBases6/verification/reference_bases.py --seeds 0 1 2 --iterations 2000`.
Settings: initial step 1, 40 backtracks, Armijo coefficient 10⁻⁴, tangent-gradient
tolerance 10⁻¹⁰; full three-unitary space, with I fixed. Runtime is diagnostic and
excluded from oracle payloads.

| Start | Initial SSE | Accepted steps | SSE evaluations | Final ASD | Seconds | Stop |
|---|---:|---:|---:|---:|---:|---|
| Gaussian-QR seed 0 | 3.9633342903 | 310 | 697 | 0.9934782626536175 | 0.079 | Backtracking stalled |
| Gaussian-QR seed 1 | 3.8210077421 | 281 | 639 | 0.9921998107715669 | 0.064 | Backtracking stalled |
| Gaussian-QR seed 2 | 4.5177100861 | 377 | 907 | 0.9982916927001239 | 0.088 | Backtracking stalled |
| Published warm start | 0.05124921899628383 | 0 | 1 | 0.9982916927001239 | 0.00016 | Gradient tolerance |

All three random outputs converted at 32 bits pass exact orthogonality with maximum
coordinate sizes 349, 350, 350 bits, respectively. None exceeds the algebraic
reference's upper bound. One of three random starts recovered the known objective
to displayed precision; the other two stalled at worse values. Three starts do not
estimate basin frequencies reliably. Warm-start stationarity is a control, not a
novelty result. No external models or remote/Linux experiments were run.
