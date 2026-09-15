# MutuallyUnbiasedBases6 — optimize four approximate measurement bases exactly

## Scientific problem

Construct four orthonormal bases in complex dimension six whose pairwise transition probabilities
are as close as possible to the mutually unbiased value `1/6`. The standard basis `B0=I` is fixed
and implicit; submit the other three bases as exactly orthogonal Gaussian-integer rays.

This is approximate measurement-design optimization. The representation cannot express even three
exact mutually unbiased bases including `I` in dimension six, so no score is evidence for or against
the unrestricted complex MUB existence problem.

## Contract and exact metric

Implement `build_bases(problem)` and return

```python
{"bases": [B1, B2, B3]}
```

Each `B` is a row-major 6 by 6 matrix. Each entry is `[real, imaginary]` with actual integers, and
each column is a nonzero Gaussian-integer ray. Columns within each submitted basis must already be
exactly orthogonal; the verifier never rounds or repairs them. The public problem has exactly these
keys:

| key | meaning |
|---|---|
| `dimension` | 6 |
| `num_bases` | 4, including the implicit identity basis |
| `max_coordinate_bits` | 384-bit cap for every signed integer coordinate |

Floats, booleans, a wrong matrix shape, a zero column, an oversized coordinate, or any nonzero
cross-column inner product invalidate the submission. For rays `u,v`, the verifier computes

```text
p(u,v) = |sum_i conjugate(u_i)*v_i|^2 / ((sum_i |u_i|^2)*(sum_i |v_i|^2)),
SSE = sum_(a<b,i,j) (p(B_a[:,i], B_b[:,j]) - 1/6)^2,
ASD = 1 - SSE/30.
```

All these quantities are exact rationals. Probability rows and columns sum to one, `0<=ASD<=1`,
and four coincident identity bases have `ASD=0`.

## Public exact-orthogonalization helpers

`solution.py` already provides `numerical_to_integer_rays(matrix, bits=32)` and
`gaussian_integer_gram_schmidt(matrix)`. You may keep and call them directly from your edited
`solution.py`; do not import hidden verification files. The first helper multiplies numerical
complex entries by `2**bits`, rounds real and imaginary parts, and calls the second. For a current
integer column `v` and an accepted column `u`, exact Gram-Schmidt applies

```text
v <- ||u||^2 v - u <u,v>
```

and removes a common integer gcd after every projection. The helper rejects dependent columns and
does not guarantee the resulting coordinates satisfy `max_coordinate_bits`; choose precision and
check the returned integers yourself.

## Published-reference boundary

The normalization uses an exactly orthogonalized rational reconstruction of the
Raynal–Lü–Englert construction (Phys. Rev. A 83, 062303, 2011,
https://doi.org/10.1103/PhysRevA.83.062303). Its executable reconstruction and
stored witness belong to the evaluator-side audit, not the candidate-visible
worked example. Published knowledge may still reconstruct the reference cheaply;
this task does not claim contamination resistance or qualified model difficulty.

## Scoring and the actual frontier flag

`combined_score = ASD / ASD_fixed_fixture` and is not clipped. The baseline returns three identity
matrices and scores zero. The immutable 32-bit rounded and exactly orthogonalized Raynal fixture
defines score one.

The evaluator separately reports `beyond_rational_fixture`. That flag can be reached merely by
requantizing the public equations. The scientifically stronger
`beyond_published_reference` flag requires the exact submitted ASD to exceed a rigorous rational
upper bound on the algebraic `ASD_R`; `frontier_excess_lower_bound` reports the certified excess.
Requantization improvements are not advances over the published construction.
The Raynal paper does not prove its construction globally optimal.

## Representation boundary and neighboring tasks

If `I,A,B` had Gaussian-rational rays and were exactly mutually unbiased, scale every ray by its
nonzero first coordinate. Its six entries would have modulus one, while unbiasedness between `A`
and `B` would require a Gaussian rational of squared modulus six. Clearing denominators in
`a^2+b^2=6` gives a primitive integer equation `A^2+B^2=6C^2`; reduction modulo three forces all
three integers divisible by three, a contradiction. This excludes exact triples only in this
chosen field, not arbitrary complex MUBs. Without the bit cap, exactly orthogonal rational rays are
dense; the cap makes the search family finite.

`QuantumFoundations/BellBoundCertificate` proves an operator upper bound; this task constructs
measurement bases and exactly evaluates their pairwise geometry. Engineering-design tasks elsewhere
use frozen physical simulators, whereas this one has an algebraic quantum-measurement objective.
No MUB or equivalent basis-design task was found in the checked Frontier-Eng appendix or catalogue
as of 2026-09-06.
