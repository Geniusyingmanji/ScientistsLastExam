# TrussWeightMinimization — general truss sizing under physical shifts

## Scientific background

Sizing a truss means choosing a cross-sectional area for every member while minimizing mass or
weight. A useful design must remain within tensile and compressive stress limits, control nodal
displacement, and prevent compressed slender members from Euler buckling. For a member of length
`L`, area `A`, Young's modulus `E`, direction `(c,s)`, and axial displacement extension `delta`,

```text
stress = E * delta / L
axial_force = stress * A
K_member = (A E / L) * outer([c,s,-c,-s], [c,s,-c,-s])
P_euler = pi^2 E I / L^2,       I = inertia_coefficient * A^2.
```

The evaluator supplies multiple planar structures, materials, geometries and load cases. Both
left-node translational degrees of freedom are fixed in the current family, but implementations
must use the supplied `fixed_dofs`. Units are internally consistent inches, pounds and psi.

## Your task

Implement one structure-general sizing policy:

```python
def design_truss(nodes, members, fixed_dofs, load_cases, youngs_modulus, density,
                 tension_allowable, compression_allowable, displacement_limit,
                 area_min, area_max, inertia_coefficient):
    """Return one intended cross-sectional area per member."""
```

- `nodes`: `(n_nodes, 2)` Cartesian coordinates.
- `members`: `(n_members, 2)` zero-based endpoint indices.
- `fixed_dofs`: fixed indices in the flattened `[x0,y0,x1,y1,...]` displacement vector.
- `load_cases`: `(n_cases, n_nodes, 2)` external nodal loads.
- all remaining arguments are scalar material, serviceability and section-family parameters.

Every returned area must be finite and lie in `[area_min, area_max]`. Values are rejected, not
clipped or repaired. Every nominal load case must satisfy asymmetric tension/compression limits,
the absolute displacement limit on every free degree of freedom, and pin-ended Euler buckling.

## Evaluation

`combined_score` is development-structure weight reduction above an all-maximum-area feasible
baseline, normalized by independently calibrated multistart nominal witnesses. The same policy
is called on interleaved held-out geometries and materials. The trusted evaluator also applies:

- 12% load amplification;
- 8% Young's-modulus and allowable-strength degradation;
- 5% manufactured-area undersizing; and
- a combined load/material/area shift.

Held-out transfer, shifted feasibility, maximum utilization, and robust weight quality are kept
evaluator-only. They never control search selection. Reference designs are strong feasible local
witnesses, not certified global optima; a lighter feasible result is allowed and scores 1 after
clipping.

## Rules

- Only edit `solution.py`; keep the complete `design_truss` signature.
- Deterministic CPU code using the Python standard library, NumPy and SciPy only.
- Do not hard-code one topology or member count.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.

References: Schmit & Farshi, *AIAA Journal* 12(5), 692–694 (1974),
doi:10.2514/3.49321; Zhou, *Structural Optimization* 11, 129–136 (1996),
doi:10.1007/BF01376857.
