# AdaptiveConservativePDEMethod

## Scientific question

Can one deterministic finite-volume method improve cell-average accuracy across a frozen panel of
smooth and discontinuous scalar conservation laws while balancing nonlinear stability and work
under a hard work budget and the shared discrete-conservation integrity gate?

This task asks for a numerical method, not the solution of one supplied PDE instance. The same
method is replayed on seven repository-visible worlds spanning positive and negative linear
advection, smooth and discontinuous profiles, and Burgers shocks and rarefactions. It is distinct
from parameter fitting or PDE-constrained physical design: the artifact is the discretization
itself.

The oracle is a deterministic one-dimensional benchmark. Success here does not establish order of
convergence, entropy stability for a broader equation class, multidimensional performance, or
fitness for a real simulation code.

## What to implement

```python
def design_finite_volume_method(problem):
    ...
    return {
        "reconstruction": "constant",
        "limiter": "minmod",
        "riemann_solver": "rusanov",
        "time_integrator": "euler",
        "cells": 32,
        "cfl": 0.45,
        "sensor_threshold": 0.5,
        "shock_blend": 1.0,
        "flux_dissipation": 1.15,
    }
```

Return a mapping with exactly these nine fields. The five discrete choices are:

| field | choices |
|---|---|
| `reconstruction` | `constant`, `muscl`, `weno3` |
| `limiter` | `minmod`, `mc`, `van_leer`, `superbee`, `central` |
| `riemann_solver` | `rusanov`, `godunov` |
| `time_integrator` | `euler`, `ssprk2`, `ssprk3` |
| `cells` | `32`, `48`, `64`, `96`, `128`, `192` |

The four continuous coordinates have public closed bounds:

| field | bounds | role |
|---|---:|---|
| `cfl` | `[0.08, 0.95]` | requested Courant factor |
| `sensor_threshold` | `[0.02, 0.95]` | curvature-sensor onset |
| `shock_blend` | `[0.0, 1.0]` | fraction blended toward the selected safe slope at a detected shock |
| `flux_dissipation` | `[1.0, 1.5]` | Rusanov wave-speed multiplier |

For a constant reconstruction the limiter and sensor coordinates are canonically inactive. A
zero shock blend makes the sensor threshold inactive and, for WENO3, also makes its fallback
limiter inactive. MUSCL/minmod has no distinct fallback, so both sensor coordinates are inactive.
For a Godunov flux, `flux_dissipation` is inactive. The evaluator collapses these coordinates
before assigning an artifact identity, so changing unused values cannot create a new method.

## Public problem mapping

Every key supplied to `design_finite_volume_method` is listed here:

| key | meaning |
|---|---|
| `method_fields` | ordered list of the nine exact output fields |
| `discrete_choices` | legal reconstruction, limiter, flux, integrator and grid choices |
| `continuous_bounds` | legal bounds for all four continuous coordinates |
| `equations` | disclosed scalar equation classes |
| `boundary_conditions` | disclosed periodic and fixed far-field boundary classes |
| `adaptivity` | definition of the local curvature-triggered slope reduction |
| `objectives` | accuracy, conservation, stability and work axes |
| `work_unit_definition` | one cell update in one Runge--Kutta stage |
| `max_work_units_per_case` | deterministic per-world resource envelope |
| `scope_warning` | scientific interpretation boundary |

The same mapping is supplied at every world boundary and the candidate must return the same
canonical method. Sandboxed candidate state is reset between worlds. No world ID, split label,
initial condition, final time or result is passed to the method designer.

## Frozen numerical oracle

Cell averages are evolved by a flux-difference finite-volume update. `constant` selects a
piecewise-constant reconstruction, `muscl` selects a piecewise-linear reconstruction, and
`weno3` selects third-order nonlinear face reconstruction. Above `sensor_threshold`, the
normalized curvature sensor blends the proposed face states toward the selected MUSCL fallback
by `shock_blend`. Thus the sensor is a stability mechanism, not a decorative coordinate. The
chosen Rusanov or exact scalar Godunov flux is integrated by Euler, SSPRK2 or SSPRK3 stages.

Periodic cases measure mass drift. Fixed-boundary Burgers cases integrate the numerical boundary
flux with the same Runge--Kutta weights and measure the complete discrete balance residual. Smooth
and discontinuous exact solutions are cell-averaged by frozen closed-form antiderivatives, including
periodic wrap and moving shock or rarefaction intersections with each cell.

Before simulation, a conservative stage-count bound rejects configurations above the public
`max_work_units_per_case`; realized work is checked again. Thus extremely small CFL factors at a
large grid cannot purchase accuracy outside the common envelope.

## Scoring and continuing improvement

Each world reports four separate axes:

1. cell-average L1 accuracy against the frozen exact solution;
2. discrete conservation residual;
3. maximum-principle overshoot and total-variation growth;
4. realized cell-stage work.

A frozen utility reports terms weighted by 0.72, 0.14, 0.10 and 0.04 for accuracy, stability,
conservation and work. Conservation is also a hard evidence gate and is nearly invariant for every
accepted shared-face flux-difference method; it is an integrity diagnostic, not a separately learned
capability. The primary estimand is therefore the accuracy--stability--work tradeoff under a hard
work budget.
Development utility weights smooth and shock regime means by 0.8 and 0.2. `combined_score`
affinely normalizes that utility so the shipped first-order 32-cell Rusanov/Euler method is exactly
`0.0`, while an independently executable adaptive high-order witness is exactly `1.0`. Its exact
configuration is evaluator-only rather than a candidate template. The reference is not asserted
to be optimal and the nonnegative fixed-wave score is
uncapped at its reference: a legal method can exceed 1. Three held-out worlds repeat all four axes
but never enter `combined_score`.

The reference development utility is `0.9705475629` and its held-out utility is `0.9720236480`.
Removing its sensor blend scores `0.978250`; delaying the sensor scores `0.994197`; replacing
the high-order reconstruction by MUSCL scores `0.973684`; using a coarser grid scores `0.990420`;
lower-order time integration scores `0.985257`; and jointly replacing the solver by Rusanov and
setting its dissipation multiplier to 1.5 scores `0.996005`. A 432-method nonadaptive grid probe
reached at most `0.988555`, below the reference. These figures show that every named reference capability
affects this panel; they do not establish global optimality or model difficulty.

The finite public 432-method grid and 48-point neighborhood probes show that this low-dimensional
search cell is readily grid-searchable. This wave is therefore an **on-ramp** for validating the task
runner, frontier ledger and scientific-method interface. It must not be paired as a hard exam task,
and no trusted HY3 calibration is attached yet. Earlier runtime-unbound model diagnostics are
excluded from task evidence. A hard successor would need a richer local method-policy language,
independently frozen heterogeneous equations and resource envelopes, rather than hidden references
or tighter score thresholds.

The evaluator also emits one canonical optimization record tied to the frozen method
canonicalizer, evidence predicate and seven-world panel. Later immutable waves can add equation
classes, meshes or fidelity without rewriting credit earned under this wave.

## 关系与区别

- `Engineering/ConvectionDiffusionOpt` identifies transport and designs heaters; this task emits a
  reusable discretization and never fits physical coefficients or a control layout.
- `Engineering/RANSCalibration` calibrates parameters of a fixed turbulence closure against data;
  here reconstruction, flux, time integration and adaptive switching define the algorithm.
- `Engineering/NeutronDiffusionCriticality` optimizes reactor enrichment while its eigensolver is
  fixed; here solver design is the artifact and no physical design variable is optimized.
- `ComputerScience/MatrixMultiplicationRank` also asks for an algorithm, but verifies an exact
  algebraic identity rather than PDE accuracy, stability, conservation and work across worlds.

## Rules

- Edit only `solution.py`; keep `design_finite_volume_method(problem)`.
- Return one deterministic exact-field method mapping; booleans, nonfinite values, extra fields,
  unknown choices and out-of-envelope methods fail closed.
- Standard-library code is sufficient. Do not use the network, create processes, or read
  `verification/` or `frontier_eval/`.
- Do not infer a hidden split or specialize by call order; candidate sessions are reset at each
  scientific world boundary.

References: van Leer, *Journal of Computational Physics* 32, 101--136 (1979), DOI
`10.1016/0021-9991(79)90145-1`; Shu and Osher, *Journal of Computational Physics* 77, 439--471
(1988), DOI `10.1016/0021-9991(88)90177-5`; Jiang and Shu, *Journal of Computational Physics*
126, 202--228 (1996), DOI `10.1006/jcph.1996.0130`.
