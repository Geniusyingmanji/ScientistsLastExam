# CalorimeterDesign-v2 — graded sampling-calorimeter design curves

## Scientific question

Can one longitudinal Pb/scintillator design policy improve resolution and
linearity across changing energy menus, layer counts and detector constraints,
and can it do so without becoming brittle to manufacturing and calibration
shifts?

This is a transparent reduced-order optimization benchmark. It is **not** a
GEANT4 simulation, test-beam result or detector engineering validation.

## Interface

Edit `solution.py` and implement:

```python
def design_calorimeter(problem):
    """Return three designs, one for each ordered public cost cap."""
```

`problem` contains only public nominal information:

- `n_layers`, `archive_size == 3`, `energies_gev`, and
  `calibration_energy_gev`;
- Pb/scintillator radiation lengths, Pb density, critical energy,
  shower-profile and resolution constants;
- per-layer passive and active thickness bounds;
- minimum absorber depth, maximum lead areal mass, maximum total length;
- three increasing `option_cost_caps` and all cost coefficients;
- light yield, electronics noise and constant term;
- the valid uniform-baseline depth and its cost fraction.

Return a mapping with exactly the required numeric arrays:

```python
{
    "passive_thicknesses_mm": passive,  # shape (3, n_layers)
    "active_thicknesses_mm": active,    # shape (3, n_layers)
}
```

Row `k` is evaluated against cost cap `problem["option_cost_caps"][k]`.
Every value must be finite and within its public bounds. Every row must satisfy
all public depth, mass, length and cost constraints. The three rows must not be
duplicates within `1e-4` mm.

## Public nominal model

Depth `t` is measured in radiation lengths. For incident energy `E`, the
normalized longitudinal shower density is

```text
p(t | E) = b^a t^(a-1) exp(-b t) / Gamma(a)
a(E) = 1 + b [ln(E / E_c) - 0.5]
b = problem["shower_profile_b"]
```

Thus the shower maximum is `(a - 1) / b`, and the deposited fraction in an
interval `[t0, t1]` is the regularized-gamma CDF difference. Starting at the
front face, each Pb layer advances depth by `d_Pb / X0_Pb`; its following
scintillator advances depth by `d_scint / X0_scint`. The nominal active signal
fraction is the sum of the shower fractions deposited in all scintillator
intervals.

Response is calibrated at `calibration_energy_gev`:

```text
R(E) = signal_fraction(E) / signal_fraction(E_calibration)
```

Let `w_i(E)` be the uncalibrated shower fraction in active layer `i`. The
shower-weighted passive sampling thickness is

```text
d_eff(E) = sum_i w_i(E) d_Pb,i / X0_Pb / sum_i w_i(E)
```

The relative resolution is the quadrature sum

```text
sampling       = sampling_scale * sqrt(d_eff / signal_fraction) / sqrt(E)
photostatistic = 1 / sqrt(E * signal_fraction * light_yield)
electronics    = electronics_noise_active_gev / (E * signal_fraction)
constant       = constant_term
leakage        = leakage_fluctuation_scale * (1 - containment)
```

For each energy menu, the nominal utility combines RMS resolution, RMS
linearity error, worst absolute nonlinearity and worst containment:

```text
loss = 0.62 * rms_resolution / 0.08
     + 0.18 * rms(R(E) - 1) / 0.08
     + 0.08 * max(abs(R(E) - 1)) / 0.15
     + 0.12 * (1 - min_containment) / 0.08
utility = exp(-loss)
```

Lead areal mass and cost are

```text
lead_mass_kg_m2 = sum(d_Pb_mm) * 1e-3 * lead_density_kg_m3
areal_cost = lead_cost_per_kg * lead_mass_kg_m2
            + active_cost_per_liter * sum(d_scint_mm)
            + readout_areal_cost_per_layer * n_layers
```

The cost coefficients are cost units per kg of Pb, per litre of active
material, and per readout layer per square metre, respectively. Since
`1 mm * 1 m^2 = 1 litre`, `sum(d_scint_mm)` is numerically the active volume in
litres per square metre and `areal_cost` is in cost units per square metre.

## Evaluation

Six interleaved detector regimes vary layer count, energy menu, light yield,
noise, material limits, length and costs. Four regimes determine the visible
score. Two held-out regimes are evaluator-only transfer diagnostics.

Within every regime and cost cap, the weak valid uniform design defines zero.
A separately fixed-seed, same-model graded witness defines one. These witnesses
are replayable normalization anchors, not global-optimality or state-of-the-art
claims; better feasible designs are clipped to one. The visible score is the
mean of the three option scores and then the four development-regime scores.

Five sealed shifts separately test:

- passive/active overbuild;
- anticorrelated layer-thickness tolerances;
- longitudinal calibration nonuniformity;
- dead support material, light loss and electronics drift;
- a combined fabrication/calibration shift.

Shifted robustness, held-out transfer, detailed resolution/linearity/
containment, cost use and per-instance records never enter online selection.
If a shifted artifact violates the original construction envelope, its shifted
utility is zero; the nominal artifact remains valid. Malformed, non-finite,
out-of-bound, duplicate or over-budget nominal artifacts fail closed.

## Scope and references

The gamma profile and resolution decomposition are motivated by classical
calorimetry parameterizations, but this benchmark omits lateral showers,
material interfaces, non-compensation, saturation, cross-talk, detailed
electronics, structural mechanics and event-level detector simulation.
Engineering conclusions require GEANT4 and test-beam replication.

- Fabjan & Gianotti, *Calorimetry for particle physics*, Rev. Mod. Phys. 75,
  1243–1286 (2003), DOI: `10.1103/RevModPhys.75.1243`.
- Grindhammer, Rudowicz & Peters, *The fast simulation of electromagnetic and
  hadronic showers*, Nucl. Instrum. Methods A 290, 469–488 (1990), DOI:
  `10.1016/0168-9002(90)90566-O`.
- Longo & Sestili, *Monte Carlo calculation of photon-initiated
  electromagnetic showers in lead glass*, Nucl. Instrum. Methods 128,
  283–307 (1975), DOI: `10.1016/0029-554X(75)90679-5`.
- Del Peso & Ros, *On the energy resolution of electromagnetic sampling
  calorimeters*, Nucl. Instrum. Methods A 276, 456–467 (1989), DOI:
  `10.1016/0168-9002(89)90571-8`.
- Prabhaharan & Bugge, *Optimization of electromagnetic sampling
  calorimeters*, Nucl. Instrum. Methods A 314, 21–25 (1992), DOI:
  `10.1016/0168-9002(92)90495-P`.

## Checking your submission's shape before spending a call

`sle.contract_lint` is importable inside the sandbox. Calling it costs no oracle
budget and reveals nothing about the science — every check is about form, and none touches a
score, a hidden world or a reference value.

```python
from sle.contract_lint import mapping, finite_array, in_range, explain

ok, why = mapping(submission, required=["a", "b"])
if not ok:
    ...  # `why` names the missing or unexpected keys
```

Available: `finite_array`, `binary_array`, `mapping`, `in_range`, `probabilities`,
`sequence_of_str`, and `explain` to join failures into one message. Each returns `(ok, reason)`
with a specific reason — "expected shape (12000, 1), got (3, 3)" rather than "invalid submission".

This exists because a rejected submission and a hard scientific problem both score zero, and this
task is one where submissions have been rejected often enough that the distinction matters.

## Rules

- Only edit `solution.py`; keep the entrypoint signature.
- NumPy/SciPy only, CPU, no network.
- Do not read `verification/` or `frontier_eval/`.

## Keys of `problem`

Every key the evaluator passes in, so none has to be guessed. Twelve of these were previously
undocumented, and a proposal that reached for one of them by an invented name — `light_yield_per_gev`
for `light_yield_pe_per_active_gev` — raised at runtime and scored nothing. Values shown are from
one development instance; only the key names and types are part of the contract.

| key | type | example |
|---|---|---|
| `active_cost_per_liter` | float | 14.0 |
| `active_thickness_bounds_mm` | list[2] | [1.0, 8.0] |
| `archive_size` | int | 3 |
| `baseline_absorber_depth_x0` | float | 21.0 |
| `baseline_cost_fraction` | float | 0.9 |
| `calibration_energy_gev` | float | 10.0 |
| `constant_term` | float | 0.004 |
| `critical_energy_gev` | float | 0.00743 |
| `design_fields` | list[2] | ['passive_thicknesses_mm', 'active_thicknesses_mm'] |
| `electronics_noise_active_gev` | float | 0.00045 |
| `energies_gev` | list[5] | [2.0, 5.0, 10.0, ...] |
| `lead_cost_per_kg` | float | 2.0 |
| `lead_density_kg_m3` | float | 11340.0 |
| `leakage_fluctuation_scale` | float | 0.18 |
| `light_yield_pe_per_active_gev` | float | 12500.0 |
| `maximum_lead_mass_kg_m2` | float | 1718.28 |
| `maximum_total_length_mm` | float | 320.0 |
| `minimum_absorber_depth_x0` | float | 19.5 |
| `model` | str | transparent_longitudinal_gamma_sampling_calorimeter |
| `n_layers` | int | 32 |
| `option_cost_caps` | list[3] | [4427.6, 5174.3, 6169.9] |
| `passive_thickness_bounds_mm` | list[2] | [0.8, 6.0] |
| `radiation_length_pb_mm` | float | 5.612 |
| `radiation_length_scintillator_mm` | float | 424.0 |
| `readout_areal_cost_per_layer` | float | 20.0 |
| `sampling_scale` | float | 0.018 |
| `shower_profile_b` | float | 0.5 |

There are no other keys. Reading one that is not listed here is a bug in the candidate, not a
hidden part of the task.
