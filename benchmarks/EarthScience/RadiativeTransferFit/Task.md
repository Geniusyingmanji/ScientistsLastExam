# RadiativeTransferFit — actively select thermal channels and retrieve an atmospheric mechanism

## Scientific setting

Thermal-infrared sounding infers atmospheric temperature and absorption from top-of-atmosphere
radiances. Different spectral channels and viewing angles have different vertical weighting,
so the observation plan controls which parameter combinations are identifiable. A low residual
under a clear-sky model is not sufficient when an unmodelled absorber or cloud can explain the
measurements.

This task uses a public 16-layer, plane-parallel, non-scattering local-thermodynamic-equilibrium
emulator. It is not a line-by-line code or a real satellite retrieval. Pressure midpoints, a
reference temperature profile, four piecewise-linear temperature-anomaly basis functions,
24 channel wavenumbers and each channel's layer optical depths are supplied in `public_model`.
For wavenumber `sigma` in m^-1,

```text
B_sigma(T) = 2 h c^2 sigma^3 / (exp(h c sigma / (k T)) - 1)
```

The evaluator begins with black-surface emission and propagates upward through every layer:

```text
transmittance = exp(-optical_depth / view_cosine)
L_out = L_in * transmittance + B_sigma(T_layer) * (1 - transmittance)
```

The supported family has four temperature-anomaly knot values and one global optical-depth
scale. Some worlds contain no anomaly; others contain a grey layer or spectrally localized
absorber outside this public family. A defensible retrieval must refuse the latter rather than
force a clear-sky explanation.

## Your task

```python
def discover_atmosphere(public_model, observe, budget_units):
    """Return a dictionary with:
      temperature_anomaly_knots_K: finite length-4 array
      optical_depth_scale:          finite scalar in [0.65, 1.35]
      support:                      exact zero/one length-5 array
      confidence:                   scalar in [0, 1]
      abstain:                      bool

    observe(channel_indices, view_cosine) returns:
      channel_indices:       queried integer channel indices
      wavenumbers_cm:         their public wavenumbers
      view_cosine:            queried viewing cosine
      radiances:              noisy top-of-atmosphere radiances
      radiance_noise_std:     declared radiance-noise standard deviation
      budget_cost:            charged measurement units
    """
```

Each call may request 1–12 unique channels and a view cosine in `[0.45, 1.0]`. Every requested
channel costs one unit, the total budget is 18 units, and at most four calls are allowed. Thus
channel coverage, repeated measurements and viewing-angle diversity compete for one budget.
Fresh laboratories reproduce an identical query, while separately charged calls receive
distinct deterministic noise realizations.

The first four support entries label the temperature knots. The fifth labels a deviation of
the optical-depth scale from one. Active temperature anomalies must have magnitude in
`[0.5, 12] K`; active optical-depth deviations must have magnitude in `[0.02, 0.35]`.
Inactive knot values must equal zero and an inactive optical-depth scale must equal one. An
abstention must return this canonical empty mechanism. Invalid or over-budget observation
attempts make the entire world invalid even when the candidate catches the callback exception.

## Evaluation

- `combined_score` measures development-world support recovery, parameter error, full-profile
  temperature error and optical-depth-scale error. It is normalized so abstaining everywhere
  scores zero.
- `robustness_score` evaluates unseen parameter combinations under larger radiance noise.
- Full-channel radiance prediction and held-out viewing geometries are evaluated separately
  from mechanism recovery.
- Null, extra-absorber and cloud worlds measure correct refusal, false discovery and confidence.
- Supported-world discovery coverage is reported separately so correct refusal cannot conceal
  refusal of every identifiable atmosphere.

The task is a controlled active-inverse benchmark. Simulator performance alone is not an
atmospheric retrieval result or an autonomous scientific discovery.

## Checking your submission's shape before spending a call

`sle.contract_lint` is importable inside the sandbox. Calling it costs no oracle
budget and reveals nothing about the science — every check is about form, and none touches a
score, a hidden world or a reference value.

```python
from sle.contract_lint import mapping, finite_array, in_range, explain

ok, why = mapping(submission, required=["a", "b"])
if not ok:
    ...  # `why` names the missing or unexpected keys
```

Available: `finite_array`, `binary_array`, `mapping`, `in_range`, `probabilities`,
`sequence_of_str`, and `explain` to join failures into one message. Each returns `(ok, reason)`
with a specific reason — "expected shape (12000, 1), got (3, 3)" rather than "invalid submission".

This exists because a rejected submission and a hard scientific problem both score zero, and this
task is one where submissions have been rejected often enough that the distinction matters.

## Rules

- Only edit `solution.py`; keep the `discover_atmosphere` signature.
- Use deterministic CPU code from the Python standard library, NumPy and SciPy only.
- Do not assume hidden world order, anomaly count, noise level or atmosphere family.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.

References: Rodgers (1976), DOI `10.1029/RG014i004p00609`; Rodgers (2000), DOI
`10.1142/3171`; Clough et al. (2005), DOI `10.1016/j.jqsrt.2004.05.058`.
