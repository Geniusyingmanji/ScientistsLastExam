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

## Public Raynal–Lü–Englert construction

The score-one construction is fully public. Let `omega=exp(2*pi*i/3)`,
`X=diag(conjugate(x),x)`, `Z=diag(1,-1)`,

```text
F = [[1,1],[1,-1]],
T = [[1,omega*t^2],[1,-omega*t^2]].
```

Build the following 3 by 3 arrays of 2 by 2 blocks:

```text
N1 = [[F,F,F], [F,omega*F,conjugate(omega)*F],
      [T,conjugate(omega)*T,omega*T]]
N2 = [[F,F,F], [T,omega*T,conjugate(omega)*T],
      [T,conjugate(omega)*T,omega*T]]
N3 = [[F,F,F], [T,omega*T,conjugate(omega)*T],
      [F,conjugate(omega)*F,omega*F]]
L1 = diag(X, i*conjugate(omega)*t*Z*conjugate(X)*conjugate(X), X)
L3 = diag(conjugate(X), conjugate(omega)*conjugate(X), -i*t*Z*X*X)
(B0,B1,B2,B3) = (I, L1*N1/sqrt(6), N2/sqrt(6), L3*N3/sqrt(6)).
```

Products in `L1` and `L3` are matrix products. Raynal–Lü–Englert Eqs. (19)–(22) set

```text
r = cbrt(21*sqrt(3)-36)
s = (3 + 16*r - r^2)/(28*r)
x = exp(i*asin(sqrt(s)))
t = exp(i*(acos((1-2*s)/sqrt(s)) - pi/3))
ASD_R = (71 - 12*(1-s)^2)/70.
```

Construct the three numerical explicit bases, convert each with
`numerical_to_integer_rays(Bk, bits=32)`, and return those three integer matrices. This inexpensive
route reconstructs the fixed score-one fixture; increasing the conversion precision can slightly
exceed that rational fixture without beating the algebraic construction.

## Scoring and the actual frontier flag

`combined_score = ASD / ASD_fixed_fixture` and is not clipped. The baseline returns three identity
matrices and scores zero. The immutable 32-bit rounded and exactly orthogonalized Raynal fixture
defines score one, with

```text
ASD_fixed_fixture = 0.998291692700123872383322928599388780...
```

The evaluator separately reports `beyond_rational_fixture`. That flag can be reached merely by
requantizing the public equations. The scientifically stronger
`beyond_published_reference` flag requires the exact submitted ASD to exceed a rigorous rational
upper bound on the algebraic `ASD_R`; `frontier_excess_lower_bound` reports the certified excess.
A 36-bit reconstruction beats the fixture but remains below that upper bound by about
`6.34e-23`. No tested numerical search passed the stronger flag, and the Raynal paper does not
prove its construction globally optimal.

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
