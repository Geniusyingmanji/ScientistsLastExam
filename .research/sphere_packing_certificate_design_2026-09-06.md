# SpherePackingCertificate — design, validations, and the open piece (2026-09-06)

Second task for the `certificate_bound` cell, in a different discipline from `BellBoundCertificate`.
The design is settled and most of the package is built and validated. The reference is the one
remaining piece, and the reason it is remaining is itself a result about the task.

## The problem

How densely can unit balls be packed in `R^n`? Solved in dimensions 1, 2, 3, 8 and 24; open
everywhere else, with large gaps — in dimension 12 the best packing known reaches a centre density
of 0.03704 and the best proof stops at 0.06279.

Cohn and Elkies (Ann. of Math. 157 (2003), Theorem 3.1, read in the source) turn the upper half of
that gap into analysis: if `f(x) <= 0` for `|x| >= 1` and `fhat(y) >= 0` everywhere, then the centre
density is at most `f(0) / (2^n fhat(0))`. Producing a function that makes this say something strong
is the research problem, and it is the one Viazovska solved in dimension 8.

## Why it is exactly checkable

The Fourier eigenbasis for radial functions is `L_k^{(n/2-1)}(2*pi*|x|^2) exp(-pi*|x|^2)` with
eigenvalue `(-1)^k`, so a function written in that basis has an exactly known transform: the same
coefficients with alternating signs.

**Validated numerically to machine precision** (relative error 5e-17 to 8e-16) for dimensions 4, 8
and 12 at orders k = 0..3, by comparing against the radial Hankel transform.

Written in `|x|^2` those polynomials carry powers of `2*pi` and nothing is rational. Written in
`w = 2*pi*|x|^2` they are rational, and `|x| >= r` becomes `w >= R` with `R = 2*pi*r^2` chosen by the
submitter. Choosing `R` rational makes both hypotheses statements about rational polynomials on
rational half-lines, and a univariate polynomial is non-negative on `[0, infinity)` exactly when it
is `sigma0(w) + w*sigma1(w)` with both parts sums of squares. That characterisation is complete, so
the check is a proof and not a test. `pi` enters only the number finally reported.

## Anchors (primary source, read directly)

Cohn & Elkies, *New upper bounds on sphere packings I*, Annals of Mathematics 157 (2003), Table 3,
p. 711. Columns verbatim: "Dimension | Best Packing Known | Rogers' Bound | New Upper Bound", all
centre density.

| dim | best packing | Rogers | Cohn–Elkies | ceiling on the score |
|---|---|---|---|---|
| 8 | 0.0625 | 0.06326 | 0.06251 | 1.013 |
| 12 | 0.03704 | 0.06559 | 0.06279 | 10.2 |
| 16 | 0.0625 | 0.11774 | 0.10738 | 5.33 |
| 20 | 0.13154 | 0.32454 | 0.27855 | 4.20 |

Dimension 8 is the rung with a known answer: Viazovska proved the optimum is exactly 1/16 and that
the linear programming bound is tight there, so the ceiling is 1.013 and the score is how much of
the last 0.001 a submission certifies. The other three have four to ten times that room, all of it
inside territory nobody has proved anything about.

## Built and validated

- `verification/lp_algebra.py` — exact rational Laguerre, polynomial arithmetic, shift, and the
  half-line SOS identity. Laguerre coefficients agree with `scipy.special.genlaguerre` for
  dimensions 4, 8, 12, 13 at orders 0..5; `poly_shift` verified against direct evaluation; the
  half-line check accepts `(w-1)^2`, `w`, and rejects `w - 1`.
- `verification/evaluator.py` — parses an exact rational submission, rejects floats, rebuilds both
  polynomials, verifies both certificates, reports the bound, and flags a bound below the best
  packing known rather than scoring it.
- `verification/extract.py` — exact SOS extraction on the half-line via a rational Gram matrix with
  structural interiority (`G = a^T a + margin*I`), affine repair by degree group, and exact LDL.

## The open piece, and why it is the interesting part

The natural reference — discretise both half-lines on a grid, solve the resulting linear program in
the Laguerre coefficients, round — **does not produce a certificate, and worse, it produces false
bounds.** Measured:

| dim | degree 10 grid LP | degree 16 grid LP | best packing known |
|---|---|---|---|
| 8 | 0.06412 | 0.06237 | 0.0625 |
| 12 | 0.06797 | 0.00330 | 0.03704 |
| 16 | 0.12651 | 0.00066 | 0.0625 |

The degree-16 numbers are impossible: 0.06237 in dimension 8 is below what the E8 lattice actually
achieves, and 0.00066 in dimension 16 is off by a factor of ninety. The polynomial satisfies every
grid constraint and dips between the points. Exact extraction refuses all of them, at every degree
and both rounding denominators tried — so the exact certificate catches precisely what the
numerical method gets wrong, which is the premise of the task demonstrated on the task itself.

A reference therefore needs the SOS-constrained formulation (a semidefinite program, not a linear
one), which is the same thing a good submission needs. That is the remaining work. It is not a
detail to paper over: shipping this task with a reference whose bound is not exactly certified would
make the oracle unsound, and unsound is worse than absent here, because the task's whole claim is
that a submitted number is a proof.

## Note for whoever picks this up

Build new task packages **outside** `benchmarks/` until they are complete. `sle.registry`
discovers any directory there, and a package without `frontier_eval/metadata.yaml` makes
`list_tasks` raise, which turned into 37 failures and 60 errors across the suite from tests that
have nothing to do with the new task.
