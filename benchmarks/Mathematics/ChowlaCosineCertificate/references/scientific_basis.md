# Scientific basis and interpretation

This is a **candidate optimization task**, not hidden-mechanism discovery. Given
a set of `n_terms` distinct positive frequencies bounded by `max_frequency`, the
candidate minimizes a rational number r while certifying

\[
r+\sum_{a\in A}\cos(ax)
=\sum_j w_j|q_j(e^{ix})|^2,\qquad w_j\in\mathbb Q_{\ge0},\quad q_j\in\mathbb Q[z].
\]

For real rational coefficients, expand each squared modulus as
`sum_{e,f} w*c_e*c_f*z^(e-f)`. The target constant is r, each coefficient at
`+a` and `-a` is 1/2, and **every other Laurent coefficient is zero**. Exact
dictionary equality proves the identity on the whole unit circle. Nonnegative
weights then prove the global lower bound. An unsupported harmonic, even beyond
all selected frequencies, invalidates the submission. This is a sufficient
certificate class under degree and resource bounds; rational completeness is
not asserted.

## Constructive anchor and score

Choose m integer marks B whose positive pairwise differences are all distinct.
Then `|sum_{b in B} z^b|^2 = m + 2*sum_{a in A} cos(ax)`, giving
`n=m(m-1)/2` and `r_reference=m/2` with one factor of weight 1/2.
The reference generator starts at zero and repeatedly adds the smallest feasible
mark; it checks that the ruler fits the frequency range. Repeated differences
would introduce multiplicities and cannot be collapsed into a unit-coefficient
cosine set. No published optimal-ruler claim is needed.

The trivial construction uses A=1,...,n and factors `|1+z^a|^2/2`, so r=n.
A valid world's score is `max(0,(n-r)/(n-r_reference))`; an invalid world contributes
zero to the same fixed-denominator average. A score above one is retained.
`reference_excess=max(0,score-1)` is a normalized diagnostic, not a world-record
claim. This scale is **not mathematically unbounded at fixed n**: because r>0,
the score is less than `n/(n-r_reference)`. Score one means the reproducible Sidon
benchmark, **not global SoTA**. The measured stronger local search already exceeds
one slightly; see `known_best.md`.

## Numerical search and exact correction

The reference search proposes deterministic single-frequency swaps and ranks
them by a sampled minimum. A sampled minimum is only a search objective: it
cannot prove a global lower bound. A real spectral factor is approximated from
the FFT cepstrum of the sampled shifted polynomial, truncated to the permitted
degree, and rounded to dyadic rationals. Neither FFT positivity nor a numerical
factorization is trusted by the evaluator.

For any resulting rational q, let c_l be its exact autocorrelation and set
`e_l=1_A(l)/2-c_l`. For each positive lag with nonzero error, add
`|e_l|*|1+sign(e_l)*z^l|^2`. This corrects both signed lag coefficients and adds
`2|e_l|` at zero. Thus the exact corrected bound is
`c_0+2*sum_{l>0}|e_l|`. Errors at unselected frequencies are corrected too.
The trusted evaluator independently checks the entire submitted identity;
the constructor imports no evaluator and contains no second accept/reject oracle.

## Exact-arithmetic resource contract

All integer fields require actual integers, excluding booleans and floats.
Each rational is an integer or a JSON two-integer list `[numerator,denominator]`.
The denominator must be strictly positive, and the raw integers are checked
against `max_rational_bits` before Fraction construction. Sparse terms have
unique nonnegative exponents no larger than `max_frequency`, with nonzero
coefficients. Weights may be zero but still consume the stated work budget.

Before rational arithmetic, the checker caps factor count, total sparse terms,
and the sum of squared polynomial term counts. It then incrementally bounds the
LCM of **all raw submitted denominators** (bound, weights, and coefficients) by
the public `max_denominator_lcm_bits=512`. This additional key prevents many
individually small unrelated denominators from causing denominator explosion.
Raw unreduced denominators count conservatively. Each triple-product denominator
divides the cube of this common denominator; with 128-bit scalar numerators and
at most 100000 products, intermediate rational growth remains bounded.
The defaults otherwise remain `max_factors=D+1`, `max_total_terms=4D+4`,
`max_pair_products=100000`, and `max_rational_bits=128`. Returned local search
certificates need only 49 common-denominator bits at most.

The public `reference_bound` is an exact pair. Frozen instance specifications
are immutable tuples; every call receives fresh plain input data, including the
nested reference pair. Invalid metric rows retain the same keys; `bound=null`
signals that no rational bound was certified, and numeric invalid placeholders
are zero. All aggregate averages keep every world in the denominator.

## Sources, collision, and limits

Benjamin Bedert, [*Polynomial bounds for the Chowla Cosine Problem*,
arXiv:2509.05260v3](https://arxiv.org/abs/2509.05260v3), revised 24 July 2026,
proves that every n-frequency set has minimum at most `-n^(1/5-o(1))`.
The previously quoted exponent 1/7 is outdated for this version. This is a lower
bound on the unavoidable negative magnitude; our finite constructions supply
upper bounds for particular sets. It is not a scoring anchor.

[Epoch AI's public Chowla problem](https://epoch.ai/frontiermath/open-problems/chowla-cosine)
asks for constructions for every positive c and size threshold n, with global
bound `-c*sqrt(|A|)`. Its page describes numerical sampling in its verifier.
The problem-family collision is explicit: this package is a finite, fixed-size,
frequency-bounded, exact-certificate optimization analogue of public Chowla
research, not a new mathematical problem or a hidden problem. Public solutions,
Sidon constructions, and cosine-certificate techniques are contamination risks.
No external implementation or answer set was copied. Sources checked 2026-09-06.

A finite improvement here does not refute the asymptotic Chowla conjecture,
solve Epoch's quantified target, prove global optimality, establish difficulty
for strong models, or certify task admission. The three sizes are development
instances. Strong-model calibration and Linux sandbox verification remain absent.
