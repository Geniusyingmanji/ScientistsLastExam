# ActiveFullWaveformInversion — acquire shots and recover an acoustic velocity model

## Scientific setting

Full-waveform inversion (FWI) estimates subsurface wave speed from complete seismic traces.
The objective is highly non-convex: a model can fit acquired traces while putting interfaces in
the wrong place, and an acoustic model should not be trusted when attenuation or anisotropy is
needed. This benchmark therefore combines charged acquisition, structural recovery, sealed-shot
prediction and calibrated refusal.

The public forward family is a two-dimensional constant-density acoustic wave equation on a
regular grid,

```text
u[t+1] = 2 u[t] - u[t-1] + (c dt)^2 Laplacian(u[t]) + source[t].
```

The evaluator contains supported velocity anomalies, a no-anomaly null world, and data with
attenuation/phase effects outside the public acoustic family. Hidden worlds, noise and sealed
source frequencies are not visible to the candidate.

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

- `combined_score` is development mechanism recovery normalized so always abstaining is zero.
- Supported worlds use depth-weighted velocity recovery and wave-equation prediction on sealed
  shots and frequencies.
- Null and resolvable out-of-family worlds reward calibrated refusal.
- Waveform relative L2 error, travel-time behavior, confidence, false discovery, correct refusal
  and supported-world discovery coverage are retained separately.
- `robustness_score` uses held-out anomaly topologies, noise and velocity contrasts.

The grid is deliberately small enough for deterministic CPU evaluation. It is a controlled
acoustic benchmark, not a claim of field-scale seismic imaging.

## Oracle and difficulty

The evaluator uses `xarray` for coordinate-labeled time/receiver waveform alignment and misfit
reduction. The propagation model itself remains the stated local reduced-order finite-difference
model. Evaluator difficulty levels 1–3 progressively increase observation noise and the number of
simultaneous anomalies; level 1 is the shipped default.

## Rules

- Only edit `solution.py`; keep the complete function signature above.
- Deterministic Python/NumPy/SciPy code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Do not assume hidden-world order, anomaly count, noise level or response family.
- Use `sle.contract_lint` for free local shape checks before returning a reconstruction.

References: Virieux & Operto (2009), DOI `10.1190/1.3238367`; Symes (2020), arXiv
`2003.14181`.

## 关系与区别 / Relationship to nearby tasks

GravityInversion fits a potential field, DeformationMechanismInference chooses an elastic source family, and RadialVelocityPlanets infers orbital signals. This task pays for acoustic shots and reconstructs a velocity field, with no-anomaly and attenuating worlds requiring refusal.

## Admission and reference scope

This package remains **candidate**. The metadata difficulty is a target, not a certified result. The runnable reference uses public inputs only. Local shortcut and ablation diagnostics are recorded in `references/known_best.md`; they do not replace clean Linux sandbox replay, independent domain review, Frontier-Eng overlap review or a frozen frontier-model calibration draw.

### Current reference and remaining difficulty

Bounded two-stage smoothed/full-waveform least squares over a 3x5 velocity correction grid. The reference now optimizes signed spatial velocity corrections instead of drawing a fixed negative lens. A finer grid, source design and more complete inversion remain open. The optimization reference defines 1 by construction; a discovery reference is evaluated against the fixed recovery ceiling. Neither fact certifies difficulty.
