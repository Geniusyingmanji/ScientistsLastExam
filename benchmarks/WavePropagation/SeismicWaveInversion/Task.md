# SeismicWaveInversion-v2 — actively acquire and invert layered reflection waveforms

## Scientific setting

Reflection-waveform inversion is non-convex: a velocity model can align one event or one
frequency while assigning the wrong interval velocities and interface depths.  You therefore
choose receiver offsets and source frequency before returning an interpretable layered model.

The supported public model contains three locally horizontal, lossless acoustic layers with
increasing interval velocities. The two finite layer thicknesses vary quadratically with CMP
midpoint coordinate `q = (midpoint_m - 5000)/5000`. Its parameter vector is

```text
[v1_m_s, v2_m_s, v3_m_s,
 h1_center_m, h1_slope_m, h1_curvature_m,
 h2_center_m, h2_slope_m, h2_curvature_m]
```

with `h1(q) = h1_center + h1_slope*q + h1_curvature*q^2` and likewise for `h2`.
The public bounds
are supplied at runtime.  Density is fixed by the deterministic Gardner-style relation
`rho = 310 v**0.25` in SI units, and the normal-incidence reflection coefficient is
`R_k = (rho_b v_b - rho_a v_a)/(rho_b v_b + rho_a v_a)`. The amplitude of primary
reflection `k` is exactly `R_k * product_{j<k}(1 - R_j**2)`; geometrical spreading,
attenuation, multiples and source uncertainty are not included in this controlled laboratory.

For horizontal offset `x`, exact ray-theoretical primary-reflection time is computed from the
Snell ray parameter `p`.  For layers `i=1..k` above an interface,

```text
x/2 = sum_i h_i p v_i / sqrt(1 - (p v_i)^2)
t/2 = sum_i h_i / (v_i sqrt(1 - (p v_i)^2)).
```

Each primary is a Ricker wavelet
`(1 - 2(pi f tau)^2) exp(-(pi f tau)^2)` at this arrival time.  The laboratory returns noisy
traces on the public grid `0..2 s` at `0.004 s` spacing.  The equations are public; hidden
information consists of velocity worlds, noise realizations and evaluator-only acquisitions.

Not every world supports this model family.  Some contain no reflection response, while others
contain an extra thin low-velocity layer.  A scientifically reliable policy must distinguish
these cases from a valid three-layer explanation rather than always fitting nine parameters.

## Your task

```python
def discover_layered_velocity(
    midpoint_bounds_m,
    offset_bounds_m,
    frequency_bounds_hz,
    parameter_names,
    parameter_bounds,
    acquire,
    budget_units,
):
    """Return a dictionary with:
      parameters: nine finite values, or nine zeros when abstaining
      confidence: scalar in [0,1]
      abstain:    bool

    acquire(midpoints_m, offsets_m, peak_frequency_hz) returns:
      midpoints_m:        selected CMP midpoint positions
      offsets_m:          selected receiver offsets
      peak_frequency_hz: selected Ricker peak frequency
      time_s:             trace sample times
      traces:             array with shape (n_offsets, n_times)
      noise_std:          stated pointwise Gaussian-noise standard deviation
      budget_cost:        charged acquisition units
      budget_used:        cumulative charged units
    """
```

An acquisition contains 4–12 unique CMP–offset pairs with midpoints in `[0,10000]` m, offsets in
`[0,3000]` m and a frequency in `[6,28]` Hz. Its cost is `2 + ceil(n_traces/2)` and total cost
must not exceed 12. Invalid
requests consume the validity of the world even if an exception is caught.

For a non-abstaining claim, all nine parameters must satisfy the runtime bounds and
`v2 >= v1 + 100`, `v3 >= v2 + 100` m/s. Local `h1,h2` must remain in `[120,1200]` m across
the profile. Abstention uses the canonical all-zero vector.

## Evaluation

- `combined_score` jointly measures development-world parameter/mechanism recovery, prediction
  on evaluator-only offsets/frequencies and information in the chosen acquisition.  Always
  abstaining is normalized to zero.
- waveform fit on the observations you requested is recorded separately from prediction on
  unobserved traces and from physical-parameter recovery;
- `robustness_score` uses far-offset prediction, while held-out worlds change layer geometry,
  noise and difficulty;
- null and four-layer low-velocity-zone worlds separately report correct refusal, confidence and
  false discovery;
- experiment count, charged budget, Jacobian rank, conditioning and information score are
  retained separately.  Merely spending all 12 units or obtaining numerical full rank is not
  itself scientific success.

Evaluator-only mechanism, held-out, far-offset, refusal and per-world metrics are never returned
to online proposal or selection code.

## Rules

- Only edit `solution.py`; keep the `discover_layered_velocity` signature.
- Deterministic CPU code using the Python standard library, NumPy and SciPy only.
- Do not assume hidden-world order, parameters, noise realization or model class.
- No network or process creation.  Do not read `verification/` or `frontier_eval/`.

References: Tarantola (1984), DOI `10.1190/1.1441754`; Virieux & Operto (2009), DOI
`10.1190/1.3238367`; Dix (1955), DOI `10.1190/1.1438126`.
