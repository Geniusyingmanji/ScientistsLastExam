# Phase-equilibria development plan, frozen before diagnostics

Scope: a synthetic isothermal binary diffraction apparatus, freshly prepared for
all queries. Fixed-composition crystalline phases have a lower convex envelope;
linear mass balance sets two-phase fractions. A composition-conserving relaxation
from a prescribed preparation adds finite-time behavior. Gaussian peak profiles
and a fixed holder background produce a dense intensity vector. Measurement noise
is independent additive Gaussian, sigma 0.003; no peak censoring or process noise.
No claim that a finite hold establishes equilibrium is made.

Public controls: composition [0,1], hold_time [0,120], powder_blend or quenched
preparation, loading [0,1], 1..241 requested angles in [10,90] degrees. Axis is
angles_deg, channel intensity, normalization 1. All intensities are measured;
there is no assigned readout even at zero hold or loading.

Questions and ambiguity: a single spectrum can be a compound or an unresolved
mixture. Composition scans test affine mixture behavior. Finite-time spectra can
confound stable phase signatures with precursor remnants; alternate preparation
and longer holds can distinguish particular finite-time accounts. A loading scan
and empty holder can separate fixed apparatus peaks from sample peaks. Nearly
coincident peaks and finite observation times can remain unidentifiable.

Bounded checks, chosen before execution: seeds 71,72,73 across each of the three
operator strata; <=500 kernel/world calls, <=5 ODE integrations and <=5 quadrature
references, <=60 seconds CPU and 120 seconds wall. Verify convex-hull mixture mass
balance at 101 compositions, exact endpoint behavior, independent linear-program
energy minimization, solve_ivp relaxation check, Gaussian-profile quadrature,
angle-resolution invariance, valid extreme controls, public description
invariance, independent noise keys, panel validity, and empirical-baseline shape.
Baseline receives public records only and transfers the nearest preparation /
composition / hold / loading spectrum with angle interpolation. Its no-record
prediction is zero; it does not know phases, rates, or holder response.

Diagnostics and any failed checks are retained outside the repository under the
operator campaign artifact directory. No API trial, difficulty certificate,
structural holdout, or contamination-resistance claim is part of development.
