# AutocorrelationSequence — beat the published autoconvolution-ratio bounds

## Scientific setting

The autocorrelation constant `C = inf_f max_t (f*f)(t) / (integral f)^2`, over non-negative
functions `f` supported on `[-1/4, 1/4]` (`(f*f)(t) = integral f(t-x)f(x)dx`); the *signed*
variant `C'` drops the non-negativity requirement. Both are live research targets with
published upper-bound certificates -- `C <= 1.5028503020710076` and, more recently,
`C' <= 1.4545548626983325` (Together AI, 2026, improving a 2010 bound of 1.4581).

Discretizing `f` into `N` equal-width step heights turns this into a finite object: the
discrete ratio `2*N*max(convolve(a,a)) / (sum(a))^2` is a Riemann-sum approximation of the
continuous definition, and it is exactly what this task's oracle computes.

## Your task

Implement:

```python
def construct_sequence(signed: bool) -> list[float]:
    """Return N step heights. If signed is False: non-negative, N >= 100 (targets C).
    If signed is True: any finite reals, N >= 10, sum nonzero (targets C')."""
```

You will be called with `signed=False` and `signed=True`. Anything else -- too few
intervals, a negative value when `signed=False`, a non-finite value, a zero sum -- scores
that call zero. Never an infrastructure failure.

## Evaluation

`score = (2.0 - your_ratio) / (2.0 - sota_ref)`, clipped below at 0 and **unbounded above**
(the constant, uniform sequence always gives ratio exactly 2.0, a scale-invariant fact used
here as the baseline):

| variant | baseline ratio (uniform sequence) | published upper bound |
|---|---|---|
| unsigned (`C`) | 2.0 | 1.5028503020710076 |
| signed (`C'`) | 2.0 | 1.4545548626983325 |

`combined_score` is the mean over both variants. Matching the published bound scores 1.0;
a smaller ratio scores above 1.0 -- a real, checkable new bound, since the oracle computes
the ratio directly from your literal submitted step heights, not a recalled number.

## Available tools and resources

NumPy and the standard library are available. A standard, effective technique: start from
a tapered (triangular or similar) window instead of a flat one, then repeatedly perturb one
entry by a shrinking random offset, keeping the move only when it strictly lowers the
ratio; repeat with several random restarts. This clears the uniform baseline by a wide
margin but does not reach either published bound -- a smarter search (simulated annealing,
or the Fourier-analytic optimization behind the cited certificates) can do better. Candidate
execution is networkless and cannot look anything up.

## Rules and scope

- Only edit `solution.py`; keep `construct_sequence(signed)`.
- Return a list of floats (nonnegative if `signed=False`) of the required minimum length.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

References: A. Cloninger, S. Steinerberger, "On Suprema of Autoconvolutions with an
Application to Sidon sets," *Proc. Amer. Math. Soc.* (2017), arXiv:1403.7988 (lower bound on
`C`); M. Matolcsi, C. Vinuesa, "Improved bounds on the supremum of autoconvolutions,"
*J. Math. Anal. Appl.* (2010), arXiv:0907.1379 (prior upper bound on `C'`); Together AI,
"New State-of-the-Art on the Third Autocorrelation Inequality" (2026), the current `C'`
upper-bound certificate.
