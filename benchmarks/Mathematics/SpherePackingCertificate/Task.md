# SpherePackingCertificate — prove a packing bound, exactly

## Scientific setting

How densely can unit balls be packed in `R^n`? Solved in dimensions 1, 2, 3, 8 and 24, and open
everywhere else — with gaps that are not small. In dimension 12 the best packing anyone has built
reaches a centre density of 0.03704 while the best proof stops at 0.06279, so a factor of 1.7 of
the answer is simply unknown.

Cohn and Elkies turned the upper half of that gap into analysis. If `f : R^n -> R` satisfies

1. `f(x) <= 0` for `|x| >= 1`, and
2. `fhat(y) >= 0` for all `y`,

then the centre density of any packing is at most `f(0) / (2^n fhat(0))` (Ann. of Math. **157**
(2003), Theorem 3.1). The theorem is a page of Poisson summation. Producing a function that makes
it say something strong is the research problem, and it is the one Viazovska solved in dimension 8.

## What is scored

Not a number. **An argument**, and one that is checked rather than trusted.

The submission is exact and rational throughout, and both hypotheses are *verified*, not sampled.
The variable is what makes that possible. The Fourier eigenbasis for radial functions is
`L_k^{(n/2-1)}(2*pi*|x|^2) exp(-pi*|x|^2)` with eigenvalue `(-1)^k`, so a function written in that
basis has an exactly known transform: the same coefficients with alternating signs. Written in
`|x|^2` those polynomials carry powers of `2*pi` and nothing is rational. Written in

    w = 2*pi*|x|^2

they are rational, and `|x| >= r` becomes `w >= R` with `R = 2*pi*r^2` chosen by you. Choose `R`
rational and both hypotheses become statements about rational polynomials on rational half-lines —
and a univariate polynomial is non-negative on `[0, infinity)` **exactly when** it can be written
`sigma0(w) + w*sigma1(w)` with both parts sums of squares. That characterisation is complete, so
the check is a proof: no sampling, no tolerance, no root isolation. `pi` enters only the number
finally reported.

**Floats are rejected, not rounded.** A numerical solution of the linear program is not a
certificate, and here that is not a formality: the grid relaxation, which is the textbook numerical
method, returns bounds that are *false*. At degree 16 it reports 0.06237 in dimension 8 — below what
the E8 lattice actually achieves — because the polynomial satisfies every grid constraint and dips
between the points. Making a numerical solution into a proof is the work.

## Instances and scale

| dimension | best packing known | Rogers' bound | Cohn–Elkies bound | two-term certificate |
|---|---|---|---|---|
| 8 | 0.0625 | 0.06326 | 0.06251 | 0.125317 |
| 12 | 0.03704 | 0.06559 | 0.06279 | 0.209135 |
| 16 | 0.0625 | 0.11774 | 0.10738 | 0.623022 |
| 20 | 0.13154 | 0.32454 | 0.27855 | 2.905500 |

The zero of the scale is the **two-term certificate** — what this method gives with no work at all,
in closed form, derived in `solution.py`. It is not Rogers' bound: Rogers comes from a different
technique and is not reachable by this one at any degree anyone has certified exactly, so anchoring
there would score every honest submission at zero.

The one is the **published Cohn–Elkies bound**. Reaching it means writing down an exact rational
certificate as strong as their numerical one, which as far as we can find has not been published in
any dimension. The scale is uncapped above it.

```
score = (two_term_bound - your_bound) / (two_term_bound - cohn_elkies_bound)
```

clipped below at zero, meaned over the four dimensions. Dimension 8 is the rung with a known
answer: Viazovska proved the optimum is exactly 1/16 and that the linear programming bound is tight
there. A certificate proving a bound **below the best packing known** would contradict an explicitly
exhibited packing; that is reported as `below_best_packing_known` and scored zero rather than
rewarded.

## Contract

Implement `build_certificate(instance)`, called once per dimension, returning

```python
{"threshold":   [num, den],                       # R = 2*pi*r^2, rational and positive
 "coefficients": [[num, den], ...],               # Laguerre coefficients c_0 .. c_d of f
 "transform_nonnegative": {"sigma0": [...], "sigma1": [...]},   # proves fhat >= 0 on [0, inf)
 "tail_nonpositive":      {"sigma0": [...], "sigma1": [...]}}   # proves -f(R+s) >= 0 on s >= 0
```

Each `sigma` is a list of `{"weight": [num, den], "poly": [[num, den], ...]}`; the sum of
`weight * poly(w)^2` over the list is that part, weights must be non-negative, and
`sigma0 + w*sigma1` must reconstruct the target **exactly**. `f(0)` and `fhat(0)` must both be
positive.

`instance` carries these keys, all public:

| key | meaning |
|---|---|
| `dimension` | the dimension `n` |
| `laguerre_alpha` | `[n - 2, 2]`, the rational `alpha = n/2 - 1` as numerator and denominator |
| `max_degree` | cap on the number of Laguerre coefficients and on each `poly` |
| `max_squares` | cap on the number of squares in each `sigma` |
| `max_numerator`, `max_denominator` | magnitude caps on every rational entry |
| `best_packing_known` | a bound below this contradicts an exhibited packing |
| `rogers_bound` | the classical bound, reported as a milestone |
| `cohn_elkies_bound` | the published bound; worth 1 |
| `two_term_certificate_bound` | the zero of the scale |

Submission shape is checked by `sle.contract_lint` before scoring. A submission that raises, returns
the wrong shape, or returns a certificate whose identity fails scores zero on that dimension without
disturbing the others.

## Relation to the rest of this benchmark

`Physics/BellBoundCertificate` is the other task in this cell and the other place where the product
is a verifiable argument; it bounds a Bell functional rather than a packing, and its algebra is
non-commutative words rather than univariate polynomials. `Optimization/CirclePacking` is the
opposite half of the same subject: it *builds* a packing and the verifier measures it, where this
one proves that no packing can do better. No task in the Frontier-Eng catalogue (47 tasks in the
paper appendix, 95 entries in its `TASK_DETAILS`) concerns sphere packing, linear programming bounds
or certificate extraction.
