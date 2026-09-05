# SpherePackingCertificate — measured values

All numbers here are reproducible from `verification/`.

## Anchors (published, not measured here)

Cohn & Elkies, *New upper bounds on sphere packings I*, Ann. of Math. **157** (2003), Table 3,
p. 711, read from the paper. Columns verbatim: "Dimension | Best Packing Known | Rogers' Bound |
New Upper Bound", all centre density.

| dim | best packing | Rogers | Cohn–Elkies |
|---|---|---|---|
| 8 | 0.0625 | 0.06326 | 0.06251 |
| 12 | 0.03704 | 0.06559 | 0.06279 |
| 16 | 0.0625 | 0.11774 | 0.10738 |
| 20 | 0.13154 | 0.32454 | 0.27855 |

Dimension 8's optimum is exactly 1/16 (Viazovska), and the linear programming bound is tight there.

## The machinery, and how it was checked

The task rests on one identity: `L_k^{(n/2-1)}(2*pi*|x|^2) exp(-pi*|x|^2)` is a Fourier
eigenfunction with eigenvalue `(-1)^k`. Checked against a numerical radial Hankel transform:

| dimension | k = 0 | k = 1 | k = 2 | k = 3 |
|---|---|---|---|---|
| 4 | 1.9e-16 | 2.2e-16 | 6.6e-16 | 8.4e-16 |
| 8 | 1.5e-16 | 5.0e-17 | 1.7e-16 | 6.0e-16 |
| 12 | 6.0e-16 | 4.5e-16 | 2.8e-16 | 3.6e-16 |

(relative error). The exact Laguerre coefficients agree with `scipy.special.genlaguerre` for
dimensions 4, 8, 12, 13 at orders 0–5. The half-line certificate check accepts `(w-1)^2` and `w`
and rejects `w - 1`.

## Baseline and reference

| | dim 8 | dim 12 | dim 16 | dim 20 | mean |
|---|---|---|---|---|---|
| two-term baseline | 0.125317 | 0.209135 | 0.623022 | 2.905500 | |
| baseline score | 0.000 | 0.000 | 0.000 | 0.000 | **0.000000** |
| reference bound | 0.118610 | 0.173572 | 0.415882 | 1.686479 | |
| reference score | 0.1068 | 0.2430 | 0.4017 | 0.4640 | **0.303889** |

The baseline's bound is closed form — `((n+2)/(2*pi))^(n/2) (n+2) / 2^(n+1)` — and the evaluator
reproduces it to six digits in every dimension from the submitted certificate, which is an
end-to-end check of the whole pipeline against an independent derivation.

Neither the baseline nor the reference reaches Rogers' bound, let alone Cohn–Elkies. That is the
honest state of exact rational certification here and it is why the scale is anchored where it is.

## Three approaches measured and discarded

**The grid linear program returns false bounds.** This is the textbook numerical method: discretise
both half-lines, solve the linear program in the Laguerre coefficients, round.

| dim | degree 10 | degree 16 | best packing known |
|---|---|---|---|
| 8 | 0.06412 | **0.06237** | 0.0625 |
| 12 | 0.06797 | **0.00330** | 0.03704 |
| 16 | 0.12651 | **0.00066** | 0.0625 |

The bold entries are impossible: 0.06237 in dimension 8 is below what the E8 lattice achieves, and
0.00066 in dimension 16 is off by a factor of ninety. The polynomial satisfies every grid constraint
and dips between the points. Exact extraction refuses all of them, at every degree and both rounding
denominators tried. This is the clearest possible demonstration of why the task requires a
certificate rather than a number.

**Direct search over Laguerre coefficients finds nothing.** Four thousand random draws produced not
one candidate that passed even a numerical screen. The feasible set is a thin sliver and coefficient
space is the wrong place to look for it.

**A semidefinite formulation over Gram factors did not yield an extractable certificate.**
Parametrising the transform side by its own Gram matrices and putting the tail in a penalty, six
restarts of a derivative-free method per configuration, no configuration produced one. The reason is
structural: at the optimum *both* hypotheses are tight, and a rational point needs slack on the side
being extracted.

## What works, and where the headroom is

Make the tail hypothesis structural. Writing `-f(R+s) = q0(s)^2 + s q1(s)^2` means `f <= 0` on
`[R, infinity)` holds by construction with its certificate already in hand; that fixes `f`, hence
the transform, and leaves one extraction instead of two coupled ones. Every draw then starts inside
half the feasible set instead of outside all of it.

The reference does this with a seeded, bounded search — `q0` and `q1` with at most three terms and
small rational coefficients, the radius drawn rather than optimised, a single global rounding
denominator. All four of those are on the table:

1. **Degree.** Three terms is nothing; Cohn and Elkies use much higher degree with forced double
   roots at chosen points, solved by Newton iteration.
2. **The radius is drawn, not optimised.** It is one variable and it moves the bound a lot.
3. **Rounding is uniform.** Per-entry denominators, or lattice reduction, would buy slack where it
   is needed rather than everywhere.
4. **The extraction is a rounded interior Gram point.** Extraction on a target with a double root
   fails, and near-optimal certificates have double roots — so the interesting question is how close
   to the boundary an exact certificate can be pushed, which nobody appears to have published.

## Robustness

Fifteen degenerate and adversarial submissions — floats for coefficients, floats for weights,
negative weights, a certificate that does not reconstruct its target, a negative threshold, a zero
threshold, a zero denominator, an empty coefficient list, a 5000-digit rational, a submission over
the degree cap, a boolean posing as an integer, a missing certificate, a raising callable, `None`
and `{}` — all score 0.000000 with `valid = 0`, and none raises out of the evaluator.

A sixteenth case is the one that matters most: the legitimate two-term certificate scores 0.000000
with `valid = 1`. Invalid and valid-but-worthless are different states and the report keeps them
apart.
