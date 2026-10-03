# Molecular forces bounded development plan — frozen before checks

This is an operator-only plan. No model calls and no old evaluator imports.

Public experiment: static configurations of three identical constrained particles,
coordinates in Å, temperature in K. Obtain total effective energy (eV) and nine
Cartesian forces (eV/Å). Each row is independently prepared, no trajectory,
assigned output or state carried between requests. Up to eight rows per request.
Geometry and temperature are exact controls. Measurement noise is independent,
additive Gaussian, energy σ=0.00035 and force σ=0.0007; no clipping.

Private variation: central pair interactions, a pair interaction plus a genuine
three-particle contribution, or temperature-dependent effective pair interactions.
These are generation strata, never golden-answer labels. The effective
potential is conservative at fixed temperature, not a molecular dynamics model
or a thermodynamic free-energy measurement.

Questions include whether a measured force can be accounted for by distance
alone, whether one model predicts asymmetric triangles, and whether the same
geometry changes its measured response with temperature. A restricted single
geometry at one temperature cannot identify an arbitrary potential. A pair
potential and a temperature-scaled copy agree exactly at 450 K but can be tested
at another temperature. Equilateral measurements cannot uniquely distinguish a
pair function from an angular correction; asymmetric geometries provide further
constraints without establishing uniqueness among arbitrary potential functions.

Fixed scientific fixtures before execution: LJ ε=.11 eV, σ=2.9Å; Morse
D=.11 eV, a=1.7/Å, r0=3.1Å; threebody coefficient C=200 eV Å^9;
temperature coefficient=.24 relative to450K. Test all combinations with zero
threebody/temperature coefficients as appropriate. Geometries: equilateral side
2.2,3.1,5.4Å; fixed scalene triangle sides2.4,3.2,4.4Å; collinear
positions(-2.2,0,0),(0,0,0),(2.2,0,0). Temperature180,450,900K.
Development world seeds:71001,71002,71003 only; these must be excluded from a
future GPT cohort. Panel seeds81001–81003. No selection for convenient results.

Checks: independent Cartesian-dot-product energy reference, fourth-order finite
difference gradient at h=1e-3,3e-4,1e-4Å; analytic equilateral threebody energy
and force; analytic LJ well; rotation/translation/permutation symmetry, net force
and torque; legal bounds; fixed-noise replay. Analytic checks/reference formulas
are independent evidence; symmetry and finite differences alone are consistency
checks. Maximum 10000 energy evaluations, 300 World.run calls, no optimizer
fits, 120 CPU seconds and120wall seconds for diagnostic script. Preserve failed
checks. Exact boundary validation is separately tested; reference derivatives
may briefly perturb outside the public query domain to evaluate the smooth kernel.

Baselines: zero/no-observation and nearest measured configuration with Cartesian
coordinates centered but no hidden family knowledge. Fixed six-query design:
three homogeneous-distance scans at180,450,900K and three rotated/scalene scans.
Fresh queries from two fixed panels per seed (8each); compare baseline errors
using fixed public scales. This is an empirical headroom check only, not proof of
difficulty. A strong authored inverse solver is deferred and must be disclosed
as absent, not silently replaced by access to clean targets.

Write raw fixtures, every metric and source hashes to operator artifacts outside
repository. No private fixture seeds or numeric outputs need be added to reports.

Pre-diagnostic accounting clarification: the focused28 schema/analytic tests ran
before the diagnostic script. They are recorded separately. Counting the baseline
World.run kernels as energy evaluations adds2640 calls to the planned reference
checks. The diagnostic energy cap is therefore15000, fixed before running that
script; no fixture or acceptance threshold changes. This is a work-accounting
correction, not a change selected from diagnostic outcomes. The300-run and120s
limits remain unchanged. Keep both this note and original cap for auditability.
