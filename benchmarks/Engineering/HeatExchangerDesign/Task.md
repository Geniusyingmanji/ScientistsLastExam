# HeatExchangerDesign — discover a multi-fidelity Pareto design archive

## Scientific background

A useful heat exchanger is not obtained by maximizing area alone.  More tubes, longer tubes
and tighter flow passages can increase heat duty, but also increase capital cost and pumping
power.  The result is a Pareto frontier rather than one universally best geometry.  A design
optimized with a cheap constant-property model can also be promoted incorrectly when
temperature-dependent properties, shell-side corrections, fouling or manufacturing shifts are
evaluated.

This task models a counter-flow shell-and-tube exchanger.  The hot stream flows inside the
tubes and the cold stream crosses the baffled shell.  For the public proxy, use the supplied
reference properties and the following documented model:

```text
Re = rho * velocity * hydraulic_diameter / mu
Pr = cp * mu / k

tube Nu = 3.66                                      for Re <= 2300
          0.023 * Re^0.8 * Pr^0.4                  otherwise
tube f  = 64 / Re                                   for Re < 2300
          0.3164 * Re^-0.25                         otherwise
shell Nu = max(3.66, 0.33 * Re^0.60 * Pr^(1/3))

1/Uo = do/(hi*di) + do*Rf_hot/di
       + do*log(do/di)/(2*k_wall) + Rf_cold + 1/ho
NTU = Uo * area / C_min
epsilon = (1-exp(-NTU*(1-Cr))) / (1-Cr*exp(-NTU*(1-Cr)))
```

Use `epsilon = NTU/(1+NTU)` when `Cr` is one.  The public problem mapping also supplies the
pressure-drop limits and annualized capital/electricity cost coefficients.  The installed
area and shell volume are

```text
do = di + 2*wall_thickness
pitch = pitch_ratio * do
shell_diameter = pitch*sqrt(tube_count/0.78) + do
area = pi*do*tube_length*tube_count
shell_volume = pi*shell_diameter^2*tube_length/4.

tubes_per_pass = tube_count/tube_passes
tube_flow_area = tubes_per_pass*pi*di^2/4
shell_hydraulic_diameter = 4*(pitch^2-pi*do^2/4)/(pi*do)
shell_flow_area = shell_diameter*baffle_spacing*(pitch-do)/pitch

deltaP_tube = f*(tube_length*tube_passes/di)*(rho*v^2/2)
              + (1.5+1.5*(tube_passes-1))*(rho*v^2/2)
shell f = 24/Re                                  for Re < 100
          0.20*Re^-0.15                          otherwise
deltaP_shell = shell_f*(shell_diameter/shell_hydraulic_diameter)
               *(tube_length/baffle_spacing)*(rho*v^2/2)
               + 1.5*(rho*v^2/2)

capital = fixed + area_coefficient*area^0.82
          + shell_volume_coefficient*shell_volume^0.65
          + extra_pass_capital*(tube_passes-1)
pump_power = (m_hot*deltaP_tube/rho_hot
              + m_cold*deltaP_shell/rho_cold)/pump_efficiency
annualized_cost = capital_annualization*capital
                  + pump_power/1000*operating_hours*electricity_price.
```

## Your task

Implement one problem-general archive policy:

```python
def design_exchanger(problem):
    """Return between 4 and 24 candidate designs as an (n, 5) array."""
```

Each row has these columns, in this exact order:

```text
[tube_inner_diameter_m, tube_length_m, tube_count,
 baffle_spacing_m, tube_passes]
```

All public bounds, inlet conditions, reference fluid properties, wall/fouling values,
pressure-drop limits and cost coefficients are contained in `problem`.  `tube_count` and
`tube_passes` must be exact integers; tube count must be divisible by pass count.  The archive
must contain at least four unique rows.  Installed shell diameter may not exceed
`max_shell_diameter_m`, and there must be at least three baffle spaces along the tube length.

## Evaluation

The evaluator calls the same policy on four development and two interleaved held-out fluid and
operating regimes.  For every archive it reports the Pareto hypervolume for heat duty
(maximize) and annualized capital-plus-pumping cost (minimize).  The zero reference is a
physically valid low-intensity archive.  The upper normalization anchors are independently
generated 4096-point scrambled-Sobol plus exact-model selection witnesses; they are strong
feasible fronts, not proofs of global optimality.  Better fronts are accepted and clip at one.

`combined_score` is the normalized development hypervolume from the segmented exact model.
Only `combined_score`, structural validity and development exact feasibility are visible during
search.  The trusted sidecar separately retains:

- public-proxy and exact hypervolume;
- held-out exact hypervolume;
- proxy/exact rank correlation and false-promotion rate;
- exact-front heat duty, cost, area and pumping power; and
- exact hypervolume under fouling/roughness growth, inner-diameter manufacturing error, and
  partial tube blockage plus an operating shift.

The exact oracle uses temperature-dependent property families, Gnielinski/Haaland-style
turbulent tube correlations, shell-side leakage correction and a ten-segment counter-flow
energy balance.  Its coefficients, split membership and physical shifts are evaluator-only.
It is a reproducible correlation-based simulator, not experimental truth; engineering claims
still require CFD/process-simulator and experimental replication.

## Rules

- Only edit `solution.py`; keep the complete `design_exchanger(problem)` signature.
- Deterministic CPU code using the Python standard library, NumPy and SciPy only.
- Do not hard-code one inlet condition or fluid.  Use the supplied problem mapping.
- No network or process creation.  Do not read `verification/` or `frontier_eval/`.
- Non-finite, malformed, duplicated-only, out-of-bound and non-integral archives fail closed.

References: Shah & Sekulić, *Fundamentals of Heat Exchanger Design* (2003),
doi:10.1002/9780470172605; Gnielinski, “G1 Heat Transfer in Pipe Flow,” *VDI Heat
Atlas* (2010), doi:10.1007/978-3-540-77877-6_34; Haaland, *Journal of Fluids
Engineering* 105, 89–90 (1983), doi:10.1115/1.3240948; Sanaye & Hajabdollahi,
*Applied Thermal Engineering* 30, 1937–1945 (2010),
doi:10.1016/j.applthermaleng.2010.04.018.
