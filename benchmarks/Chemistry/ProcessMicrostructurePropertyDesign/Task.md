# ProcessMicrostructurePropertyDesign

## Scientific question

Can a policy propose a *manufacturable processing archive* whose blend composition, anneal,
cooling and draw schedules improve a three-way Pareto frontier in specific modulus, transport
barrier and process energy, while transferring across sealed material and process-model shifts?

The output is a process recipe, not a microstructure image. The evaluator evolves the recipe
through a frozen reduced-order phase-field/coarsening model and then homogenizes its properties.
This is a deterministic synthetic mechanism benchmark. The reduced quantities are not validated
for any named commercial polymer or alloy. A high score is evidence only that a search policy
improved this frozen process--structure--property oracle, not that it discovered a real material.

## Relationship to neighbouring repository tasks

- `PhaseDiagramDiscovery` discovers equilibrium phase topology; here the unknown is a
  manufacturable processing archive and the order is process, microstructure, then property.
- `AlloyHardnessOptimization` chooses alloy candidates from a finite evidence table; here all five
  continuous process coordinates are constructed by the candidate.
- `ElectrolyteConductivityDesign` optimizes formulation-level conductivity evidence; this task
  jointly scores modulus, barrier transport and processing energy after simulated morphology.
- `MolecularLeadOptimization` searches molecular structures; this task holds constituent identity
  fixed and changes composition, thermal history, cooling and draw.
- `DistillationColumnDesign` optimizes separation equipment; this task models material
  microstructure formation and homogenized solid properties, not a process flowsheet.

## What to implement

```python
def design_process_archive(problem):
    ...
    return {"processes": [...]}
```

Return 4--20 processes that are distinct at the published manufacturing resolutions. Each
process must contain exactly:

```python
{
    "blend_fraction_b": 0.50,
    "anneal_temperature": 0.62,
    "anneal_time": 6.0,
    "cooling_rate": 0.8,
    "draw_ratio": 2.2,
}
```

All values are finite reduced process coordinates. They must obey the supplied `bounds`:

| process field | current bound | interpretation |
|---|---:|---|
| `blend_fraction_b` | `[0.15, 0.85]` | feed fraction of constituent B |
| `anneal_temperature` | `[0.45, 0.95]` | reduced annealing temperature |
| `anneal_time` | `[0.5, 12.0]` | reduced residence time |
| `cooling_rate` | `[0.20, 4.0]` | reduced controlled cooling rate |
| `draw_ratio` | `[1.0, 4.0]` | post-anneal uniaxial draw ratio |

An array, image, latent vector, target property, or predicted microstructure is not a process and
is rejected. Values are rounded to the nearest published manufacturing bin before evaluation;
two schedules in the same bin are duplicates and are rejected.

## Public problem mapping

Every key passed to `design_process_archive` is listed here:

| key | meaning |
|---|---|
| `process_fields` | ordered names `blend_fraction_b`, `anneal_temperature`, `anneal_time`, `cooling_rate`, `draw_ratio` |
| `bounds` | legal interval for every process coordinate |
| `archive_size_bounds` | minimum and maximum number of distinct schedules |
| `manufacturing_resolutions` | evaluator quantization step for every process coordinate |
| `grid_cells` | spatial cells in the frozen one-dimensional reduced model |
| `constituent_properties` | public nominal `reduced_modulus` and `reduced_permeability` pairs |
| `critical_temperature_estimate` | public nominal spinodal threshold estimate |
| `reference_search` | declared 1024-point Latin-hypercube construction, two 11-point-per-axis coordinate-exchange passes, low-fidelity proxy coefficients, objective normalization and 20-row archive size used by the reproducible reference policy |
| `phase_field_model` | description of spectral conserved growth and coarsening closure |
| `homogenization_model` | description of the frozen Voigt--Reuss property closure |
| `objectives` | rows with objective `name` and optimization `sense` |
| `scope_warning` | explicit non-real-discovery interpretation |

The two nested inputs most easily confused with per-constituent records have these exact shapes.
The two entries in each property list are constituent A then B; they are not dictionaries:

```python
modulus_a, modulus_b = problem["constituent_properties"]["reduced_modulus"]
permeability_a, permeability_b = problem["constituent_properties"]["reduced_permeability"]

proxy = problem["reference_search"]["proxy_parameters"]
normalization = problem["reference_search"]["objective_normalization"]
```

A representative mapping is:

```python
{
    "constituent_properties": {
        "reduced_modulus": [2.2, 5.4],
        "reduced_permeability": [0.62, 1.55],
    },
    "reference_search": {
        "pool_size": 1024,
        "archive_size": 20,
        "coordinate_refinement_passes": 2,
        "coordinate_refinement_points_per_axis": 11,
        "latin_hypercube_multipliers": [1, 73, 127, 181, 239],
        "latin_hypercube_offsets": [0, 19, 43, 71, 101],
        "proxy_parameters": {"crystallization_rate_constant": 700.0, ...},
        "objective_normalization": {
            "specific_modulus": {"offset": 1.2, "scale": 4.4},
            "barrier_index": {"offset": 0.7, "scale": 5.5},
            "process_energy_maximum": 7.5,
            "clip": {"minimum": 0.0, "maximum": 1.0},
        },
    },
}
```

Every `proxy_parameters` coefficient used by the public reference is supplied in that mapping;
consume the mapping rather than recreating coefficients from prose. Numerical property values can
change between worlds, but these nested keys and list ordering do not.

## Frozen mechanism oracle

For each schedule, a deterministic initial composition perturbation is evolved in spectral space.
The linearized conserved phase-field term amplifies unstable wavelengths; a high-wave-number
penalty and cooling-dependent coarsening suppress fine structure; bounded nonlinear saturation
keeps the phase field physical and its mean composition is restored after clipping. The evaluator
does not expose or score an image.

The resulting local field enters a Voigt--Reuss interpolation. Crystallization is mobility-limited:
`Xc = Xeq * (1 - exp(-k * t_eff * exp(-Ec / (T + T0))))`, with world mobility multiplying `k`.
The frozen reduced constants `Ec=7` and `k=700` keep a low-temperature long anneal from standing
in for a temperature-resolved kinetic search; cooling enters `Xeq` with coefficient `0.30`. Draw
orientation applies an explicit `0.35` modulus gain and a competing `0.20` permeability penalty.
Crystallinity, interface density and draw therefore modify a reduced specific modulus and
permeability-derived barrier index. Anneal time and temperature, drawing, and slow cooling
contribute to reduced process energy, whose `7.5` normalization covers the reachable bounded
energy envelope. Every scored coefficient and every reference-search setting has one source in
the machine-readable panel. The cited literature motivates only the phase-field, crystallization,
homogenization, transport and process-energy modelling families; all reduced coefficients, their
combination, the worlds and the search settings are benchmark-chosen rather than literature
calibrated. This is a frozen mechanistic surrogate with declared shortcuts, not a neural surrogate
and not a first-principles prediction.

## Pareto scoring and continuing improvement

Each feasible process becomes one point with three maximize-oriented coordinates:

1. normalized `specific_modulus`;
2. normalized `barrier_index`;
3. energy saving derived from minimizing `process_energy`.

The evaluator computes exact three-dimensional hypervolume relative to the zero corner. Additional
non-dominated schedules can therefore add continuous marginal volume instead of only passing a
threshold. `combined_score` is development hypervolume normalized so the shipped conservative
four-process archive scores `0.0` and the independent public-problem-only 20-process witness scores
`1.0`. That witness performs greedy proxy-hypervolume selection over a declared deterministic
1024-point Latin hypercube, followed by two deterministic 11-point-per-axis coordinate-exchange
passes, using only the problem mapping. It neither imports nor queries the scored phase-field
model. The score is uncapped: a better archive can exceed the witness.

The executable deterministic ladder is baseline `0.0`; a 441-point blend--temperature shortcut
`0.24854152762865947`; three 343-point coordinate-subspace shortcuts `0.6919779457497287`,
`0.2987325943208072`, and `0.4519928224629508`; reference `1.0`; and an evaluator-aware
coordinate-exchange red team `1.0050830170752605`. A public-only 2048-point pool with the same
refinement scores `1.00037415439912`, showing that scalar pool-size inflation is on the reference
platform rather than an easy improvement. Reference-archive ablations score
`0.5240992860282923` without draw, `0.7647896745827635` at shortest time,
`0.7708825121464876` at fastest cooling, and `0.6727115591109907` at one low temperature. These
tests establish local separation and uncapped headroom, not model-level or long-horizon hardness.

Reported separately are `development_hypervolume_score`,
`development_shifted_hypervolume_score`, feasibility, raw hypervolume, mean specific modulus,
mean barrier index, mean process energy and mean phase contrast. `heldout_hypervolume_score` and
`heldout_shifted_hypervolume_score` repeat the test on held-out materials. Each per-instance row
contains three `raw_shifted_hypervolumes`: reduced mobility/critical-temperature shift, stronger
gradient/interface penalty, and constituent-property shift. None of those sealed metrics enters
the public development score. `frontier_record_emitted` is true exactly when the evaluator emits
a transfer-eligible record and false otherwise; it does not assert that a ledger admitted the record.

A result emits a lifetime-credit frontier record only when every held-out artifact is legal and
the development-shifted, held-out, and held-out-shifted normalized scores each retain at least 50%
of the public development score. This frozen record-emission gate does not change `combined_score`; it
prevents a non-transferring archive from entering the cross-wave ledger.

## Rules and scientific scope

- Edit only `solution.py`; keep `design_process_archive(problem)`.
- Return only `{"processes": [...]}` with 4--20 manufacturing-distinct schedules inside all bounds.
- Use the supplied problem mapping; do not hard-code a material identity or access a split label.
- Deterministic CPU code only; standard library/NumPy/SciPy, no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Real material claims require calibrated constituent data, higher-dimensional morphology,
  processing constraints, experimental manufacture, microscopy and independent property tests.

References: Cahn and Hilliard, *J. Chem. Phys.* (1958), conserved free-energy evolution, DOI
`10.1063/1.1744102`; Avrami, *J. Chem. Phys.* (1939), transformation kinetics, DOI
`10.1063/1.1750380`; Chen, *Annual Review of Materials Research* (2002), phase-field models, DOI
`10.1146/annurev.matsci.32.112001.132041`; Hill, *Proc. Phys. Soc. A* (1952), Voigt--Reuss
averaging, DOI `10.1088/0370-1298/65/5/307`; Nielsen, *J. Macromol. Sci. A* (1967), composite
permeability, DOI `10.1080/10601326708053745`; Ng et al., *Polymer* (2000), draw-dependent
polymer properties, DOI `10.1016/S0032-3861(99)00760-0`; Gutowski et al., *Environmental Science
& Technology* (2009), manufacturing energy, DOI `10.1021/es8016655`; Brough et al., *Integrating
Materials and Manufacturing Innovation* (2017), materials knowledge systems, DOI
`10.1007/s40192-017-0089-0`.
