# ActiveFullWaveformInversion — acquire shots and recover an acoustic velocity model

## Scientific setting

Full-waveform inversion (FWI) estimates subsurface wave speed from complete seismic traces.
The objective is highly non-convex: a model can fit acquired traces while putting interfaces in
the wrong place, and an acoustic model should not be trusted when attenuation or an incorrect source time is
needed. This benchmark therefore combines charged acquisition, structural recovery, sealed-shot
prediction and calibrated refusal.

The public forward family is a two-dimensional constant-density acoustic wave equation on a
regular grid,

```text
u[t+1] = 2 u[t] - u[t-1] + (c dt)^2 Laplacian(u[t]) + source[t].
```

For acquired shots the source is a unit-amplitude 12 Hz Ricker wavelet,
`(1 - 2*a*a) * exp(-a*a)`, with `a = pi*12*(t - 1.5/12)`. Pressure starts at zero
at both initial time levels. The public discretization uses the five-point spatial
Laplacian, with its update set to zero on the outermost row and column. Multiply the
wave update by a damping mask before adding the source: start from one everywhere,
set the outermost rows/columns to 0.86, then the second rows/columns to 0.94 (the
second assignment wins at intersections). Inject the source at row 2 and the supplied
source column; record the updated pressure at row 2 and columns `receiver_x_m/spacing_m`.
The grid spacing and time increment are the supplied `spacing_m` and successive
`time_s` differences. These acquisition physics define the public forward problem;
the velocity anomalies and sealed assessment shots remain hidden.

The evaluator contains supported heterogeneous velocity fields, near-null worlds whose
structure is below the acquisition noise scale, and data with attenuation or source-timing
effects outside the public acoustic family. Structure can occur throughout the full depth
range; setting the deepest portion to background is not a valid general assumption. Out-of-family attenuation may
coexist with velocity anomalies; neither visible structure nor total signal energy alone
establishes that an acoustic interpretation is adequate. Hidden velocity fields, separate noise realizations and sealed
source frequencies are not exposed to the candidate.

## Your task

```python
def invert_velocity_model(
    grid_shape, spacing_m, background_velocity_m_s, velocity_bounds_m_s,
    source_indices, receiver_x_m, time_s, acquire, budget_units,
):
    """Return a mapping with:
      velocity_m_s: array with exactly grid_shape, or [] when abstaining
      confidence:    finite scalar in [0, 1]
      abstain:       bool

    acquire(source_index) returns:
      source_index:  the selected public integer source index
      receiver_x_m:  receiver coordinates in metres
      time_s:        sample times in seconds
      pressure:      noisy traces with shape (n_time, n_receivers)
      noise_std:     stated pointwise noise standard deviation
      budget_cost:   charged units for this call
    """
```

Each distinct shot costs one unit and the total cost may not exceed `budget_units`. Repeating a
shot is allowed but costs again. Velocity must be finite and remain inside
`velocity_bounds_m_s`. A non-abstaining submission must return the complete grid. If
`abstain=True`, `velocity_m_s` must be empty.

## Evaluation

Confidence is evaluated separately as `1 - (confidence - target)^2`. The target is
the actual mechanism-recovery score on a supported, non-abstaining world, and zero
for refusals or unsupported worlds. Thus a poor reconstruction with high confidence
cannot earn perfect confidence calibration. Invalid artifacts do not count as discovery
attempts; coverage counts valid, non-abstaining supported-world submissions.

- `combined_score` is development mechanism recovery normalized so always abstaining is zero.
- Supported worlds use depth-weighted velocity recovery and wave-equation prediction on sealed
  shots and frequencies.
- Near-null and resolvable out-of-family worlds reward calibrated refusal.
- Waveform relative L2 error, travel-time behavior, confidence, false discovery, correct refusal
  and supported-world discovery coverage are retained separately.
- `robustness_score` uses held-out anomaly topologies, noise and velocity contrasts.

Structural recovery measures improvement over the supplied background. Let `r` be the
depth-weighted L2 velocity error divided by the background's error, using depth weights
linearly spaced from 0.7 to 1.3. Its score is
`max(0, (exp(-1.5*r) - exp(-1.5)) / (1 - exp(-1.5)))`.
Exact recovery scores one; the background or a worse reconstruction scores zero.
The supported-world mechanism score is the geometric mean of this structural score
and the sealed-waveform score. Correctly rejecting unsupported worlds cannot by itself
give a positive aggregate score without supported-world recovery.

The grid is deliberately small enough for deterministic CPU evaluation. It is a controlled
acoustic benchmark, not a claim of field-scale seismic imaging.

## Oracle and difficulty

The evaluator uses NumPy for fixed-grid time/receiver waveform alignment and misfit
reduction. The propagation model itself remains the stated local reduced-order finite-difference
model. Evaluator difficulty levels 1–3 progressively increase observation noise and the spatial complexity of the
velocity field; level 1 is the shipped default. Levels 2 and 3 are diagnostic-only
settings, not validated difficulty tiers.

## Rules

- Only edit `solution.py`; keep the complete function signature above.
- Deterministic Python/NumPy/SciPy code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Do not assume hidden-world order, anomaly count, noise level or response family.
- Use `sle.contract_lint` for free local shape checks before returning a reconstruction.

References: Virieux & Operto (2009), DOI `10.1190/1.3238367`; Symes (2020), arXiv
`2003.14181`.

## 关系与区别 / Relationship to nearby tasks

GravityInversion fits a potential field and RadialVelocityPlanets infers orbital signals. This task pays for acoustic shots and reconstructs a velocity field, with unresolved near-null, source-timing and attenuating worlds requiring refusal.

## Admission and reference scope

This package remains **candidate**. The metadata difficulty is a target, not a
certified result. The runnable reference uses public inputs only. Reference methods,
calibration measurements, shortcut probes and ablation diagnostics are recorded in
the maintainer-facing `references/known_best.md`, which is not served to candidates.
They do not replace clean Linux sandbox replay, independent domain review,
Frontier-Eng overlap review or a frozen frontier-model calibration draw.

## Frontier-Eng overlap comparison (2026-09-06)

无. Nearest catalog entries: CarAerodynamicsSensing; holographic_multiplane_focusing. Budgeted acoustic shots recover a subsurface velocity grid and test model adequacy; FE selects car pressure sensors or designs optical phase masks. Neither recovers acoustic velocity from acquired waveforms.

See `.research/pr20_frontier_eng_overlap_2026-09-06.md` for the pinned 47-task paper and the complete
available repository catalog (78 table rows, 84 entries after expanding EngDesign). The maintainer
confirmed that catalog scope on 2026-09-08; no 95-entry revision exists in any inspected source.
Domain acceptance of this package is still pending.
