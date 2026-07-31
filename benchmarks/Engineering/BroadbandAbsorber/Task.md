# BroadbandAbsorber — robust multi-resonator acoustic absorption

## Scientific background

A rigidly backed Helmholtz cell absorbs sound when its neck inertance and loss balance the
compliance of its cavity. One narrow resonance does not cover a broad band, so a practical
subwavelength panel distributes differently tuned cells over its surface. Geometry that looks
good in a low-frequency lumped proxy can transfer poorly once frequency-dependent neck losses,
finite cavity depth, oblique incidence, air properties and manufacturing errors are evaluated.

This benchmark partitions the panel into equal square cells. For angular frequency `omega`,
neck radius `a`, physical neck length `l`, cavity depth `d`, cell area `A`, air density `rho`,
sound speed `c` and dynamic viscosity `mu`, the nominal model uses

```text
sigma = pi*a^2/A
l_eff = l + 1.70*a
q = a*sqrt(-j*omega*rho/mu)
F = 1 - 2*J1(q)/(q*J0(q))
rho_eff = rho/F

Z_neck = j*omega*rho_eff*l_eff + 0.5*rho*c*(omega*a/c)^2
Z_cavity = -j*rho*c*cot(omega*d/c)
Z_cell = Z_neck/sigma + Z_cavity
Z_panel = 1 / mean_i(1/Z_cell_i)
alpha = 1 - abs((Z_panel-rho*c)/(Z_panel+rho*c))^2.
```

The Bessel-function dynamic density follows Stinson's circular-tube solution. The radiation
term is the small-aperture resistance and the cavity is a lossless rigidly terminated tube.
The public cheap proxy replaces `rho_eff` with `rho`, uses Poiseuille resistance
`8*mu*l_eff/a^2`, and replaces the cavity by `-j*rho*c^2/(omega*d)`.

## Your task

Implement one policy that handles varying frequency bands, cell counts and depth limits:

```python
def design_absorber(problem):
    """Return an (n_resonators, 3) finite array."""
```

Columns are exactly

```text
[cavity_depth_m, neck_length_m, neck_radius_m].
```

The public `problem` mapping contains the resonator count, frequency band, logarithmic sample
count, cell side, air properties, geometry bounds, maximum total depth and absorption threshold.
Every row must satisfy its bounds and

```text
cavity_depth_m + neck_length_m <= maximum_total_depth_m.
```

Values outside the contract are rejected rather than clipped.

## Evaluation

For each logarithmically sampled band, the exact nominal spectrum is summarized by

```text
utility = 0.55*mean(alpha)
        + 0.30*quantile(alpha, 0.20)
        + 0.15*mean(alpha >= 0.50).
```

`combined_score` is the mean development utility improvement above an identical-cell weak
baseline, normalized by independently calibrated log-spaced-resonance witnesses. The same
policy is called on interleaved held-out cell counts, frequency bands and thickness limits.
The trusted evaluator separately retains:

- public-proxy versus distributed-model utility;
- mean, twentieth-percentile and threshold-coverage absorption;
- held-out nominal transfer; and
- worst-case utility over oblique incidence, warm/light and cold/dense air, two deterministic
  manufacturing patterns, and a combined operating/manufacturing shift. A realized geometry
  with a nonpositive dimension, an aperture wider than its cell, or total depth beyond the
  public panel envelope receives zero utility for that shift without invalidating its nominal
  artifact.

Nominal and robust references are separately optimized fixed-seed witnesses in a transparent
four-parameter family. They make the normalization reproducible but do not certify a global
optimum. Better valid designs are allowed and clip at score one. Every benchmark instance gets
a fresh candidate process and private temporary filesystem; held-out and shifted metrics do not
enter search feedback.

## Scope and rules

- Only edit `solution.py`; keep `design_absorber(problem)`.
- Use deterministic Python/NumPy/SciPy CPU code only.
- Handle the supplied problem rather than hard-coding one geometry.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.

This is a locally reacting reduced-order panel model. It omits thermal boundary-layer losses,
cell coupling, elastic panels, grazing flow, nonlinear high-amplitude response and fabrication
details. Engineering claims require thermoviscous finite-element and impedance-tube replication.

References: Stinson, *Journal of the Acoustical Society of America* 89(2), 550–558 (1991),
doi:10.1121/1.400379; Jiménez et al., *Applied Physics Letters* 109, 121902 (2016),
doi:10.1063/1.4962328; Li & Assouar, *Applied Physics Letters* 108, 063502 (2016),
doi:10.1063/1.4941338.
