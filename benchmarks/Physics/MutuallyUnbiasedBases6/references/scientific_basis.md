# Approximate four-basis design in dimension six

This resource optimizes approximate mutual unbiasedness. Its Gaussian-integer
ray representation **cannot express even three exact mutually unbiased bases
including the standard basis in dimension six**. A score close to one is not an
existence certificate, a nonexistence theorem, or a global optimality proof.

## Contract and exact metric

`build_bases(problem)` receives `dimension=6`, `num_bases=4`, and
`max_coordinate_bits=384`. Return `{"bases": [B1,B2,B3]}`. Each B is a row-major
6×6 list of integer pairs `[real,imaginary]`. Columns are nonzero, already
orthogonal Gaussian-integer rays; their lengths are arbitrary. B0=I is implicit.
Every coordinate must satisfy `abs(x).bit_length() <= 384`. Floats, bools,
incorrect shapes, zero columns, and any nonzero inner product are rejected.
Shape/type/bit validation occurs before arithmetic. No oracle-side repair occurs.

For columns u and v, the transition probability is exactly

`p(u,v) = |sum(conj(u_i)*v_i)|² / (sum|u_i|² * sum|v_i|²)`.

`SSE = sum_(a<b,i,j) (p_abij - 1/6)²`; `ASD = 1 - SSE/30`.
All arithmetic uses integers and rational fractions. Probability row/column sums
equal one; hence 0≤ASD≤1. Coincident bases give ASD=0. ASD=1 would require every
cross probability to equal 1/6, which this representation precludes. Operationally,
uniform cross probabilities mean one measurement basis reveals no information
about which state was prepared in the other. The metric follows the pairwise
distance and averaging definitions in [Raynal–Lü–Englert, Eqs.(2)–(3)](https://arxiv.org/html/1103.1025v1).

`score_bases(complete_bases, dimension=6, max_coordinate_bits=384)` is the pure
metric: callers must include I themselves. Small-dimensional controls are tests,
not additional scored instances. The callable evaluator supplies I automatically.
`combined_score = ASD / ASD_fixed_fixture` is uncapped; `raw_score = ASD`.
Float values are convenience displays. Exact outputs use records
`{"numerator_hex": "0x...", "denominator_hex": "0x..."}`; parse both with
`int(value,16)` and form a rational. Hex avoids Python's decimal-integer digit cap.

## Why this representation excludes exact triples

Suppose I,A,B were mutually unbiased with A,B rays over Q(i). Divide each ray
by its nonzero first coordinate. All six coordinates then have modulus one and
remain in Q(i); each squared norm equals six. For an A-ray u and B-ray v,
unbiasedness would imply `|u†v|² / 36 = 1/6`, so a Gaussian rational would have
squared modulus six. This is impossible: if rational a,b satisfied a²+b²=6,
clearing denominators gives a primitive integer solution A²+B²=6C². Modulo three
forces A,B divisible by three, then forces C divisible by three, a contradiction.
This argument is about the chosen field, not arbitrary complex bases.

Without the bit cap, rational-ray orthogonal bases are dense: approximate an
invertible unitary by Gaussian-rational columns and apply exact Gram–Schmidt;
the normalized result converges locally to the original basis. Clearing
denominators yields integer rays. With 384 bits the search family is finite.

## Conversion is public, validation remains strict

`solution.py` supplies `numerical_to_integer_rays(matrix,bits=32)` and
`gaussian_integer_gram_schmidt(matrix)`. The former rounds real/imaginary parts
after multiplying by 2**bits. The latter projects using
`v <- ||u||² v - u <u,v>` and removes a common integer gcd after each projection.
It rejects dependence; it does not guarantee the final 384-bit budget. These
helpers run only as candidate conveniences, never to fix an invalid submission.
The baseline returns three identity matrices and receives score zero.

## Reference equations and the two comparison gates

The public constructor implements [Raynal–Lü–Englert Eqs.(5)–(6)](https://arxiv.org/html/1103.1025v1#S4.SS1):
with ω=exp(2πi/3), X=diag(conj(x),x), Z=diag(1,−1), F=[[1,1],[1,−1]],
T=[[1,ωt²],[1,−ωt²]], its three 2×2-block arrays are

```
N1 = [[F,F,F], [F,ωF,conj(ω)F], [T,conj(ω)T,ωT]]
N2 = [[F,F,F], [T,ωT,conj(ω)T], [T,conj(ω)T,ωT]]
N3 = [[F,F,F], [T,ωT,conj(ω)T], [F,conj(ω)F,ωF]]
L1 = diag(X, i*conj(ω)*t*Z*conj(X)^2, X)
L3 = diag(conj(X), conj(ω)*conj(X), -i*t*Z*X^2)
(B0,B1,B2,B3) = (I, L1*N1/sqrt(6), N2/sqrt(6), L3*N3/sqrt(6))
```

Here squares denote matrix products. Eqs.(19)–(22) set
`r = cbrt(21*sqrt(3)-36)`, `s = (3+16*r-r²)/(28*r)`,
`x = exp(i*asin(sqrt(s)))`, `t = exp(i*(acos((1-2*s)/sqrt(s))-π/3))`,
and give the independent closed value `ASD_R = (71-12*(1-s)²)/70`.

The immutable 32-bit rounded/orthogonalized JSON fixture defines score one. Its
metric is recomputed from trusted data, without importing `solution.py` or the
reference generator into the oracle. `beyond_rational_fixture` compares exact
ASD against that fixed rational score; requantization can legitimately pass it.

`beyond_published_reference` instead requires exact ASD > U, where [L,U] encloses
the real algebraic ASD_R. At binary precision 80, integer square root brackets
sqrt(3), then interval arithmetic brackets y=21sqrt(3)−36. Integer bisection
brackets cbrt(y). The function s(r)=(3/r+16−r)/28 decreases for r>0; ASD(s)
increases for s<1. The oracle verifies these domains before propagation.
`frontier_excess_lower_bound = max(0, ASD-U)` certifies excess over this
construction only. The interval width is approximately 3.151×10⁻²⁵. Scores inside
the interval do not pass the gate; float rounding is never used for this decision.

## Full-space numerical reference

`reference_bases.py` also exposes Gaussian-QR random starts, numerical SSE and its
Euclidean gradient, and a seeded full-space optimizer. For C=Ua†Ub and
E=(|C|²−1/d)C, pair contributions are 4UbE† and 4UaE. Project G to
`G-U*(U†G+G†U)/2`, retract `U-step*tangent` using its polar/SVD factor, and backtrack
until SSE strictly decreases and satisfies Armijo decrease. U0=I stays fixed;
the other three unitaries have no Hadamard restriction. Iterations/backtracking
are bounded. Tests compare the gradient with independent directional differences.
Numerical stationarity and unsuccessful starts supply no global bounds. Only the
converted, exactly validated rays receive a score.
