# SeismicInversion — recover layered velocity from refraction first arrivals

## Scientific background

Seismic refraction estimates subsurface wave speeds from the first arrival of direct and
critically refracted head waves. For horizontal layers whose velocity increases with depth,
each observable branch has a velocity-dependent slope and intercept. Recovering the layered
profile from noisy travel-time picks is a classical inverse problem in near-surface geophysics,
crustal seismology and survey design.

This benchmark uses 4–6 horizontal layers. Every finite layer is 400 m thick and the final
layer is a half-space. For offset `x`, the direct branch is `x/v[0]`; the head-wave branch from
layer `k` is

`x/v[k] + 2 * sum_{j<k} 400 * sqrt(1/v[j]**2 - 1/v[k]**2)`.

The observed first arrival is the minimum over branches plus small picking noise. Velocities are
nondecreasing with depth and lie in `[1400, 7000]` m/s.

References: Shearer, *Introduction to Seismology*, 2nd ed. (2009), Chapter 4; Palmer,
*Refraction Seismics* (1986). This is a travel-time refraction inverse problem, not full-waveform
inversion.

## Your task

```python
def invert_seismic(travel_times, source_positions, receiver_positions, n_layers):
    """Return a nondecreasing velocity profile with shape (n_layers,)."""
```

Use `abs(receiver_positions - source_positions)` as source–receiver offset. The same function is
evaluated on several independently generated noisy surveys and layer counts.

## Scoring

The optimization score is normalized improvement in visible-pick RMSE over the supplied
constant-velocity baseline. The evaluator separately records velocity-profile recovery and
prediction on unobserved offsets; these diagnostics are not folded into the optimization score.

## Rules

- Only edit `solution.py`. numpy/scipy only. CPU. Do not read `verification/`.
