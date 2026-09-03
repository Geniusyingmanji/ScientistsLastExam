# NMRSpectrumFitting — recover supported peak mechanisms across spectra

## Scientific background

One-dimensional NMR profiling is not just curve fitting. A useful decomposition must infer an
unknown number of overlapping resonances, separate peak signal from baseline drift and noise,
identify Lorentzian/Gaussian broadening, and refuse when the declared line-shape family is not
supported. A low residual alone can reward spurious peaks or absorb baseline structure.

Each input is a variable-length sampled spectrum. Supported spectra are sums of positive,
symmetric, unit-height Voigt profiles plus smooth baseline drift and noise. A peak is described
by center `c`, Lorentzian half width at half maximum `gamma`, Gaussian standard deviation
`sigma`, and positive height `a`:

```text
a * voigt_profile(x - c, sigma, gamma) / voigt_profile(0, sigma, gamma)
```

Pure Lorentzian and Gaussian peaks set `sigma=0` and `gamma=0`, respectively. Some spectra are
null or contain strong phase-distorted/dispersive components outside this positive symmetric
library. Those cases require abstention rather than an invented peak list.

## Your task

Implement:

```python
def fit_spectrum(x, spectrum):
    """Return a dict with:
      centers:             one center per peak, in supplied axis units
      lorentzian_hwhm:     gamma in [0, 0.25]
      gaussian_sigma:      sigma in [0, 0.18]
      amplitudes:          positive unit-height amplitudes, at most 5
      lineshapes:          "lorentzian", "gaussian", or "voigt" per peak
      confidence:          probability in [0,1] that an in-library decomposition is supported
      abstain:             True for null/model-inadequate spectra; then arrays must be empty
    """
```

At most 16 peaks may be returned. Every nonzero width component must be at least `0.002`, and
each peak needs at least one nonzero component; labels must agree with them. Peak order is
irrelevant. The axis can be ascending or
descending and its range and sample count vary.

## Evaluation

- `combined_score` is development peak-mechanism/refusal quality, normalized so the valid
  always-abstain baseline scores zero and exact simulator peaks plus correct refusals score one.
- Peak matching jointly measures count, center, both broadening components and amplitude after
  optimal order-independent assignment.
- clean-signal reconstruction, confidence calibration, false discoveries and correct refusals
  are reported separately.
- held-out spectra shift noise, baseline, overlap, Voigt mixture, axis range/direction and
  model-inadequacy cases; their metrics are evaluator-only.

No single residual or aggregate “science score” substitutes for those separate diagnostics.
Simulator-truth recovery is task evidence, not a claim of experimental NMR discovery.

## Rules

- Only edit `solution.py`; keep the `fit_spectrum(x, spectrum)` signature.
- Deterministic CPU code using the Python standard library, NumPy and SciPy only.
- Do not assume a fixed axis, sample count, peak count, noise level or hidden-instance order.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.
- `sle.contract_lint` is importable and free to call for shape checks.
