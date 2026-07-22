# OceanCurrentInversion — actively deploy drifters and discover a current model

## Scientific setting

Lagrangian drifters observe an ocean current only along their trajectories. Recovering a
spatially and temporally varying Eulerian field therefore depends on where and when drifters
are released, and a good trajectory fit need not establish that a proposed current mechanism
is supported outside the sampled paths.

The domain is a 200 km by 200 km closed rectangular basin. Each supported current is a sparse
sum of public, incompressible streamfunction modes. A mode specification is
`(m, n, temporal_code, period_s)`. For its coefficient `c` in m/s and basin length
`L = 200000 m`,

```text
psi(x,y,t) = c L/pi sin(m pi x/L) sin(n pi y/L) f(t)
u = d psi/dy = c n sin(m pi x/L) cos(n pi y/L) f(t)
v = -d psi/dx = -c m cos(m pi x/L) sin(n pi y/L) f(t)
```

Here `f(t)` is one for `steady`, `cos(2 pi t/period_s)` for `cos`, and
`sin(2 pi t/period_s)` for `sin`. This construction is divergence free and has no normal flow
through the boundary. The evaluator may instead contain no current or a current outside the
public 30-mode library. A scientifically defensible policy must then abstain rather than force
an unsupported mode explanation.

## Your task

```python
def discover_currents(domain_m, mode_specifications, observe, budget_units):
    """Return a dictionary with:
      coefficients_m_s: finite length-30 coefficient array
      support:           exact zero/one length-30 support array
      confidence:        scalar in [0,1]
      abstain:           bool

    observe(initial_positions_m, release_time_s, sample_times_s) returns:
      initial_positions_m: known release positions
      release_time_s:      absolute release time
      time_s:              relative sample times
      trajectories_m:      noisy positions, shape (n_drifters,n_times,2)
      position_noise_std_m: stated coordinate-noise standard deviation
      budget_cost:          charged experimental units
    """
```

Each observation may deploy 1–6 drifters at least 5 km inside the public domain. Release time
lies in `[0, 6 days]`; provide 7–21 strictly increasing relative sample times beginning at zero
and ending no later than 1.5 days. A call costs

```text
1 + n_drifters + ceil(n_sample_times / 8)
```

and the total budget is 12 units. Thus spatial coverage, temporal resolution and distinct
release phases compete for the same budget. Initial positions are exact by construction;
subsequent coordinates contain Gaussian measurement noise. The full evaluation is
deterministic and reproducible, while separately charged calls use distinct realizations.

If `abstain=False`, at least one support entry must be active. Active coefficient magnitudes
must lie in `[0.005, 0.35]` m/s; unsupported coefficients are ignored. If `abstain=True`, the
support must be empty. Any invalid or over-budget observation attempt makes the world invalid;
catching its exception cannot restore validity.

## Evaluation

- `combined_score` measures sparse mode support, velocity-mode agreement and vorticity-mode
  agreement on development worlds, normalized so abstaining on every world scores zero.
- Sealed Eulerian field interpolation/extrapolation and independent drifter rollouts are
  reported separately from mechanism recovery.
- `robustness_score` evaluates unseen mode combinations with larger positioning noise.
- Null and out-of-library currents measure correct refusal, false discovery and confidence.
- The evaluator does not reward a single hidden raster field or one fixed trajectory set.

High predictive agreement is not treated as proof that the selected mode mechanism is true.
The task is a controlled simulator benchmark for active survey and model discrimination, not
evidence of an oceanographic discovery.

## Rules

- Only edit `solution.py`; keep the `discover_currents` signature.
- Use deterministic CPU code from the Python standard library, NumPy and SciPy only.
- Do not assume hidden world order, active mode count, noise level or current family.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.

References: LaCasce (2008), DOI `10.1016/j.pocean.2008.02.002`; Shadden, Lekien &
Marsden (2005), DOI `10.1016/j.physd.2005.10.007`.
