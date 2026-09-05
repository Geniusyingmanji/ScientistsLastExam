# CriticalPhenomenaLab — discover phase transitions by choosing finite-size experiments

## Scientific problem

A finite sample never displays the sharp singularity of an infinite thermodynamic system. Near a
transition, rounding, statistical noise and finite-size drift can make a smooth crossover resemble a
critical point, or make a weak first-order transition resemble a continuous one. A scientist must
therefore decide which temperatures and system sizes to measure, then test whether the observations
obey a consistent finite-size scaling mechanism.

This task presents a deterministic reduced-order laboratory for equilibrium lattice systems. Some
hidden worlds contain a continuous transition, some a first-order transition, some only a smooth
crossover, and some contain BKT-like behavior outside the public power-law model family. Recover the
supported critical mechanism and refuse claims that the available family cannot justify.

## Candidate function

Implement:

```python
def discover_critical_behavior(
    lattice_sizes, temperature_bounds, experiment, budget_units
):
    """Return a transition claim or a calibrated refusal."""
```

The public inputs are:

- `lattice_sizes`: allowed linear sizes `(12, 16, 24, 32, 48, 64)`;
- `temperature_bounds`: inclusive `(0.8, 3.8)` interval;
- `experiment`: the laboratory callback described below;
- `budget_units`: the complete per-world budget, currently 42 units.

Call the laboratory as:

```python
observation = experiment(lattice_size, temperature, samples)
```

`lattice_size` must be one of the supplied sizes. `temperature` must be finite and inside the
supplied bounds. `samples` must be an integer from 128 through 1024. A query costs
`ceil(samples / 256) * ceil(lattice_size / 24)` units. An invalid query or any attempt to exceed the
budget invalidates that world even when candidate code catches the callback exception.

Every observation contains all of these keys:

| key | meaning |
|---|---|
| `query_id` | immutable identifier that may be cited as evidence |
| `lattice_size` | requested linear system size |
| `temperature` | requested temperature |
| `samples` | requested effective sample count |
| `abs_magnetization` | mean absolute order parameter |
| `binder_cumulant` | fourth-order order-parameter cumulant |
| `susceptibility` | order-parameter fluctuation response |
| `specific_heat` | energy fluctuation response |
| `energy_mean` | mean energy density |
| `energy_histogram_centers` | fixed energy-density bin centers |
| `energy_histogram_density` | normalized observed histogram |
| `standard_errors` | estimated errors for the five scalar observables |
| `budget_cost` | cost of this query |
| `budget_used` | cumulative cost after this query |

Return a dictionary with:

```python
{
    "transition_type": "continuous",   # or "first_order"
    "critical_temperature": 2.1,
    "nu": 1.0,                         # required for continuous claims
    "beta_over_nu": 0.125,             # required for continuous claims
    "finite_size_shift": 0.4,
    "confidence": 0.8,
    "evidence_query_ids": ["...", "..."],
    "abstain": False,
}
```

For a first-order claim, `nu` and `beta_over_nu` may be `None`; its rounding exponent is fixed by
the public two-dimensional setting. For a crossover, unsupported scaling family or insufficient
evidence, return `{"abstain": True, "confidence": ...}`. A non-abstaining claim must cite at least
two query IDs produced in that same world.

## Evaluation

- `combined_score` is development mechanism recovery, normalized so always abstaining is exactly
  zero. It gives continuous credit for transition type, critical temperature and critical exponents.
- `mechanism_score`, false-discovery rate, correct-refusal rate and discovery coverage are reported
  separately. Their denominators are also published.
- `finite_size_prediction_score` checks the submitted parameters against sealed system sizes not
  available to the laboratory. Validation worlds and their prediction score remain evaluator-only.
- Crossover and BKT-like worlds reward calibrated refusal. Claiming a power-law critical mechanism
  in either is a false discovery.

The laboratory is a reduced-order finite-size-scaling emulator with deterministic finite-sampling
noise. It is designed to test critical-phenomena reasoning; it is not evidence for a particular
material or a replacement for high-fidelity Monte Carlo and experiment.

## Rules

- Only edit `solution.py`; preserve `discover_critical_behavior`.
- Deterministic CPU code using Python, NumPy, SciPy and the standard library only.
- Do not assume hidden-world order, transition family, critical parameters or noise realization.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.

## Scientific references

- Binder and Landau, *Finite-size scaling at first-order phase transitions*, Physical Review B 30,
  1477 (1984), DOI `10.1103/PhysRevB.30.1477`.
- van Nieuwenburg, Liu and Huber, *Learning phase transitions by confusion*, Nature Physics 13,
  435–439 (2017), DOI `10.1038/NPHYS4037`.
- Arnold et al., *Mapping Out Phase Diagrams with Generative Classifiers*, Physical Review Letters
  132, 207301 (2024), DOI `10.1103/PhysRevLett.132.207301`.

## Provenance and contamination note

The laboratory is procedural repository-local code and does not bundle an external dataset or
restricted source. The public emulator family and interface are visible to candidates, but hidden
world parameters, split membership and evaluator-only sealed-size checks are not. Results should be
treated as benchmark evidence rather than claims about a particular material; certification still
requires server-held families and independent statistical-physics review.
