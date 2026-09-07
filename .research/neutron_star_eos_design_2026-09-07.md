# Neutron-star equation of state — candidate task 7, crux validated

2026-09-07. Candidate cell: Physics (or Astrophysics) x `formula`, discovery form. `formula` holds 6
(`WallClosureDiscovery`, `SequenceLawRecovery`, `ActiveLawDiscovery`, `EnzymeKineticsLaw`,
`AMOCTippingRefusal`, `ComplexBoseLaw`).

## Why this problem

The pressure-density relation of matter above nuclear saturation is unknown, and it is what NICER
and the gravitational-wave detectors were built to measure. The 2026 literature names the two
obstacles explicitly: degeneracy between equations of state, and the precision of the inversion.

What makes it a *discovery* task rather than another inversion is the shape of its refusal boundary.

## The boundary is structural, not statistical

A star of central density `rho_c` probes the equation of state only up to `rho_c`. The mass-radius
curve turns over at a maximum mass, and no stable star exists above the corresponding central
density. So the equation of state above that density is unconstrained by mass-radius data **of any
precision and any quantity** - it is not noise-limited, it is unreachable.

That is a sharper statement than the refusals already in this benchmark. `WallClosureDiscovery`
refuses because the Reynolds span is too narrow, `MethaneSourceAttribution` because the record
cannot separate two sources, `AMOCTippingRefusal` because a fold is not identifiable from the
observed branch, `GravityInversion` because a kernel has a null space. All four are limits of the
data at hand. Here the limit is a consequence of the forward map: the TOV equations map an equation
of state to a curve that simply stops sampling above one density, and no amount of the same
observable moves it.

## Crux: the forward model, validated

`scratchpad/eos/tov.py` integrates the Tolman-Oppenheimer-Volkoff equations for a piecewise
polytrope in geometric units. Two errors on the way, both mine and both worth recording:

1. **The first calibration put stars at 5 km and 0.6 solar masses.** The structure was right - a
   proper maximum-mass turnover appeared - but `K` had been guessed rather than derived.
2. **Holding `K` fixed while varying `Gamma` is meaningless**, because `K`'s units depend on
   `Gamma`. A scan that did so collapsed to 0.03 solar masses at `Gamma = 2.5` and looked like a
   physics failure when it was a units failure.

The fix is the standard Read et al. (2009) parameterisation: pin the equation of state at a fiducial
density `rho_1 = 10^14.7 g/cm^3` with a pressure `p_1`, and derive `K = p_1 / rho_1^Gamma`. With
`1 g/cm^3 -> 7.4237e-19 km^-2` and `1 dyn/cm^2 -> 8.2601e-40 km^-2`:

| `log10 p_1` | `Gamma` | `M_max` | `rho_c/rho_nuc` at max | `R(1.4)` |
|---|---|---:|---:|---:|
| 34.3 | 3.2 | 2.138 | 7.60 | 10.72 km |
| 34.6 | 2.4 | 2.012 | 6.49 | 13.45 km |
| **34.6** | **2.8** | **2.277** | **5.85** | **12.78 km** |
| 34.6 | 3.2 | 2.501 | 5.55 | 12.40 km |
| 34.9 | 2.8 | 2.760 | 4.05 | 15.43 km |

The bolded row sits on top of the observed band - the heaviest well-measured pulsars are just over
2 solar masses and NICER puts `R(1.4)` near 12-13 km. The `(p_1, Gamma)` plane spans the allowed
region, soft to stiff, which is what a world generator needs.

**The number that matters for the task**: the central density at maximum mass is 5.5 to 8.9 times
nuclear saturation across the plausible models. Everything above that is the refusal region, and it
is not a tuning choice - it falls out of the forward map.

## Still to settle before building

* More than two parameters. A two-parameter equation of state is recovered by fitting two numbers;
  the product has to be a *shape*, so the world needs three or four segments with free break
  densities, and the score has to be recovery of `p(rho)` over the probed window rather than of the
  parameters.
* Tidal deformability. The Love number requires integrating a second ODE alongside TOV. It probes
  the same density range, so it tightens the constrained window without moving the boundary - which
  is exactly the discrimination the task should reward.
* The degeneracy design: which pairs of equations of state produce mass-radius curves closer than
  the observation errors. That set is what a correct submission must decline to distinguish, and it
  has to be measured, not asserted.
* Whether a frontier model simply knows the Read parameterisation. It is textbook, and if reciting
  it gets most of the score the task is memorisation. The mitigation is likely the same as in
  `ShannonCapacityCertificate`: score the *boundary* as well as the fit, since where the data stops
  constraining is not in any table.
