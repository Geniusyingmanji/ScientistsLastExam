# RankineCycleOpt — discover transferable single-reheat cycle Pareto archives

## Scientific background

A steam cycle has no single universally best operating point. Raising boiler pressure and
steam temperature can improve thermal efficiency, while reheat pressure changes turbine work
and exhaust moisture. Material limits, condenser conditions, turbomachinery efficiency and
pressure losses determine whether the same design remains useful after an environmental or
equipment shift. This task therefore asks for a Pareto archive rather than one boundary point.

The trusted model uses the IAPWS Industrial Formulation 1997 (IF97) Region 1 liquid, Region 2
vapor and Region 4 saturation equations. Boiler pressure is capped at 15 MPa so no state needs
the unimplemented dense-fluid Region 3. The single-reheat cycle follows these state equations:

```text
1  condenser exit: saturated liquid at condenser pressure
2s isentropic pump: s2s = s1 at boiler pressure
2  actual pump: h2 = h1 + (h2s-h1)/eta_pump
3  main turbine inlet: (Pboiler after line loss, Tmain)
4s isentropic HP exit: s4s = s3 at reheat pressure
4  actual HP exit: h4 = h3 - eta_HP*(h3-h4s)
5  reheat outlet: (reheat pressure after line loss, Treheat)
6s isentropic LP exit: s6s = s5 at condenser pressure
6  actual LP exit: h6 = h5 - eta_LP*(h5-h6s)

w_net = (h3-h4) + (h5-h6) - (h2-h1)
q_in  = (h3-h2) + (h5-h4)
eta_th = w_net/q_in
```

Two-phase turbine exits use the IF97 saturated liquid/vapor enthalpy and entropy mixture
relations. Both HP and LP outlet quality are hard constraints, not soft score penalties.

## Your task

Implement one problem-general archive policy:

```python
def design_rankine_archive(problem):
    """Return between 4 and 16 candidate designs as an (n, 4) array."""
```

Each row has these columns, in this exact order:

```text
[boiler_pressure_MPa,
 main_steam_temperature_C,
 reheat_pressure_fraction_of_main_inlet,
 reheat_temperature_C]
```

The public `problem` mapping supplies all bounds, the operating condition, archive-size limits
and objective scaling. Use it rather than hard-coding one condition. The policy is called on
four development and two interleaved held-out operating regimes.

## Evaluation

For each archive, the evaluator solves every cycle and computes the Pareto hypervolume of
thermal efficiency and specific net work. A conservative, physically feasible archive is the
zero reference. Fixed-seed 2048-point scrambled-Sobol plus full-cycle selection archives are
strong feasible upper normalization witnesses, not global-optimality proofs. Better archives
are accepted and clip at one.

`combined_score` is development nominal hypervolume. Structural validity and nominal
feasibility are visible during search. The trusted sidecar separately retains:

- held-out nominal hypervolume;
- HP/LP exit quality, thermal efficiency, specific net work and energy-balance residual;
- hypervolume and feasibility after condenser-pressure, turbine/pump-efficiency,
  pressure-loss and material-limit shifts; and
- a combined aging-and-weather shift.

The oracle is an equilibrium steady-state cycle model. It omits boiler combustion, heat-rate
maps, feedwater regeneration, component off-design maps, transient stress, water chemistry,
capital cost and emissions. A high score is simulator-specific thermodynamic optimization,
not a plant-performance or autonomous-discovery claim.

## Rules

- Only edit `solution.py`; keep `design_rankine_archive(problem)`.
- Return 4--16 unique finite rows and respect every public bound.
- Deterministic CPU code using the Python standard library, NumPy and SciPy only.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.
- Non-finite, malformed, duplicated-only, out-of-bound and insufficiently feasible archives
  fail closed.

References: IAPWS, *Revised Release on the IAPWS Industrial Formulation 1997 for the
Thermodynamic Properties of Water and Steam* (R7-97(2012)); IAPWS-IF97 release PDF SHA256
`c92f887e989cbf074af1fa982083dc54195d57691eab4fbc950ef6098d4cf1f4`.
