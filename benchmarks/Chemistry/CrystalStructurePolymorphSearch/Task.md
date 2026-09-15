# CrystalStructurePolymorphSearch — predict low-enthalpy periodic structures from composition

## Scientific setting

Crystal-structure prediction is a global optimization problem over cell shape, volume, and atomic
coordinates. Local relaxation only identifies the basin containing a proposed seed; it does not
say whether a lower basin exists. Scientifically useful searches must also retain distinct
low-energy polymorphs instead of returning the same minimum repeatedly.

This task is a deterministic surrogate track. Each world gives a binary composition and a frozen
periodic 12-6 Lennard-Jones potential. You propose orthorhombic unit cells and fractional atomic
coordinates. A charged callback locally relaxes the coordinates, cell volume, and cell shape under
external pressure. You must return three relaxed candidates that jointly balance low enthalpy and
structural diversity.

## Your task

Implement:

```python
def search_crystals(problem, relax_structure):
    result = relax_structure({
        "cell_lengths": [2.2, 2.2, 2.2],
        "fractional_coordinates": [[0.0, 0.0, 0.0], ...],
    })
    return {"candidate_ids": [id1, id2, id3]}
```

A seed contains exactly `atom_count` rows in the published `species` order. Coordinates are
fractional and wrapped periodically. Cell lengths, volume, aspect ratio, and minimum seed
separation must satisfy their public bounds.

Each successful callback call costs one of `relaxation_budget_calls == 24` units and returns:

| key | meaning |
|---|---|
| `candidate_id` | opaque ID that may be returned in the final archive |
| `enthalpy_per_atom` | relaxed shifted-LJ energy plus `P*V`, divided by atom count |
| `relaxed_structure` | relaxed `cell_lengths` and `fractional_coordinates` |
| `budget_cost`, `remaining_budget` | charged units and units left |

Invalid calls and overruns fail the world even when caught. The final mapping must contain exactly
`candidate_ids`, holding three distinct IDs from the current callback session.

## Periodic model and evaluation

For species `a,b`, pair distance `r`, and cutoff `r_c = 2.5 sigma_ab`, the frozen pair energy is

```text
u_ab(r) = 4 epsilon_ab [(sigma_ab/r)^12 - (sigma_ab/r)^6] - u_ab(r_c)
```

for `r < r_c`, and zero beyond the cutoff. The oracle sums the central cell against the 124 images
in the surrounding `5 by 5 by 5` supercell with the usual one-half factor. Together with the public
minimum cell length this completely covers the largest cutoff. It then minimizes `E + P V`. This is a model potential,
not a claim about any named chemical element.

Archive utility is `-H_best + 0.15 D`, where `D` is the mean RMS distance between sorted,
species-pair-aware fingerprints of returned structures within `energy_window_per_atom` of the
best. `combined_score` is development utility normalized so the shipped three-seed baseline is
zero and a 24-call multistart witness is one. The upper side is not clipped. Source-held transfer,
raw enthalpy, polymorph count, and diversity remain evaluator-only.

## Inputs the candidate receives

Every `problem` key is public:

| key | meaning |
|---|---|
| `formula` | symbolic binary composition |
| `species` | ordered `A`/`B` label for every atom |
| `atom_count` | number of atoms in the periodic cell |
| `pair_epsilon` | symmetric 2 by 2 reduced-energy matrix |
| `pair_sigma` | symmetric 2 by 2 reduced-length matrix |
| `external_pressure_reduced` | pressure in reduced units |
| `cell_volume_bounds` | permitted seed-cell volume interval |
| `cell_length_bounds` | permitted seed-cell length interval |
| `cell_aspect_ratio_limit` | maximum longest/shortest seed-cell ratio |
| `minimum_seed_separation` | minimum periodic Cartesian seed distance |
| `local_relaxation_model` | name of the frozen surrogate |
| `relaxation_budget_calls` | charged callback budget |
| `required_polymorph_count` | required final archive size |
| `energy_window_per_atom` | energy window used for diversity credit |

## Relationship to nearby tasks

`LennardJonesCluster` optimizes isolated, identical-atom clusters against catalogued minima; it has
no periodic cell, composition, pressure, or polymorph archive. `PhaseDiagramDiscovery` infers phase
ranges from synthetic powder patterns, while `QuinaryConvexHull` identifies stable compositions
from formation energies. This task instead searches periodic atomic structures at fixed composition.
The audited Frontier-Eng catalogue contains no crystal-structure or polymorph search task.

## Current validation status

This is an uncalibrated candidate. On the frozen five-world suite, the current reference's
24 seed structures with an energy-only final archive score 0.992291 rather than 1.0;
removing diversity-aware archive selection therefore costs only 0.007709. Equal-budget
cubic multistart and incumbent perturbation controls exceed the current witness, and
reusing development-instance records also defeats the shortcut guard. These results do
not establish expert-level difficulty. See `references/known_best.md` for the fixed
comparison protocol and limitations; that file is not an allowed candidate input.

## Rules and scientific scope

- Only edit `solution.py`; keep `search_crystals(problem, relax_structure)`.
- Deterministic CPU code only. NumPy, SciPy, and the standard library are available.
- No network or process creation; do not read `verification/` or `frontier_eval/`.
- The frozen binary LJ potential is a reproducible search landscape, not DFT and not an experimental
  stability claim. Real materials require an appropriate electronic-structure method, phonons or
  free energies, convergence checks, and experimental validation.

References: Abraham and Probert, *Physical Review B* 73, 224104 (2006), DOI
`10.1103/PhysRevB.73.224104`; Oganov and Glass, *Computer Physics Communications* 175 (2006), DOI
`10.1016/j.cpc.2006.07.020`.
