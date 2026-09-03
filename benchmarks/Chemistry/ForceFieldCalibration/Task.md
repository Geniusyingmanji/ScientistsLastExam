# ForceFieldCalibration — discriminate pair-potential hypotheses by active force queries

## Scientific setting

Fitting a flexible force field to one collection of energies is not enough to identify an
interaction law.  Several pair potentials can agree near equilibrium but diverge in their
repulsive wall, attractive tail and thermodynamic consequences.  A useful calibration policy must
therefore preserve competing explanations while evidence is ambiguous, select informative
configurations, quantify parameter uncertainty and refuse the declared library when it is wrong.

Each hidden world exposes a deterministic reduced-order molecular laboratory.  A query chooses
one or more three-particle configurations and receives noisy total energies and Cartesian forces.
The supported hypotheses are the public pair-potential families

```text
Mie 12-6: U(r) = 4*epsilon*((sigma/r)^12 - (sigma/r)^6)
Morse:    U(r) = D_e*(exp(-2*a*(r-r_e)) - 2*exp(-a*(r-r_e)))
```

and total pair energy is the sum over the three pair distances.  The hidden world may instead use
a Buckingham exponential-6 pair law, add an Axilrod--Teller three-body term, or make the pair
energy depend on temperature.  Those worlds are outside the supported library and require
refusal.  Queries at several temperatures help detect state dependence; forces themselves are
temperature-independent in supported worlds.

## Your task

Implement:

```python
def calibrate_forcefield(problem, query):
    """Actively query configurations and return a hypothesis-bound conclusion."""
```

`problem` contains:

- `model_families`, their parameter names/bounds and the analytic energy equations above;
- nominal energy/force noise scales shared by every public problem (the realized hidden-world
  noise may be shifted, so uncertainty procedures must not treat the nominal scale as truth);
- public distance, coordinate, temperature, query-batch and total-configuration limits; the first
  screening batch is restricted to one exactly equilateral, near-equilibrium configuration at
  the designated screening temperature, so later
  repulsive/tail tests must be chosen without silently erasing hypotheses after ambiguous evidence;
- `query_budget_units` and the required final parameter interval confidence level;
- a public virial-temperature grid, second-virial output bounds, Boyle-temperature bounds and the
  decision threshold for the Boyle temperature.

Call:

```python
query(configurations, temperature_k, hypothesis_state)
```

where `configurations` has shape `(n, 3, 3)` and each configuration has all pair distances inside
the public bounds.  `temperature_k` is one allowed temperature.  Each queried configuration costs
one budget unit.  A call returns:

- immutable `observation_id` and per-configuration `configuration_ids`;
- the accepted coordinates and temperature;
- noisy `energies_ev`, shape `(n,)`;
- noisy `forces_ev_per_a`, shape `(n,3,3)`.

Before seeing that batch, `hypothesis_state` must contain exactly:

- `weights`: probabilities for `"mie"`, `"morse"` and `"unsupported"` summing to one;
- `retained`: a non-empty unique list drawn from those three names.

Every retained hypothesis must carry at least the public `minimum_retained_weight` (0.01), and
every omitted hypothesis must have exactly zero weight.  This prevents nominally retaining a
hypothesis with an infinitesimal "ghost" probability.

This creates a preregistered hypothesis trajectory.  A family assigned zero weight or removed from
`retained` cannot be silently restored later; the evaluator records true-family retention,
premature elimination and the information gained by each selected batch.  Catching a budget or
protocol error does not make it valid.

Return exactly:

- `hypothesis_weights`: final probabilities for `mie`, `morse`, `unsupported`;
- `retained_hypotheses`: non-empty unique retained family names;
- `selected_model`: `"mie"`, `"morse"` or `"unsupported"`;
- `parameters`: all parameter values of the selected supported family, or `{}` on refusal;
- `parameter_intervals`: `[lower, upper]` for every selected parameter, or `{}` on refusal;
- `second_virial_cm3_mol_by_temperature`: a value for every public virial-grid temperature,
  keyed by the exact string form of that temperature, or `{}` on refusal;
- `boyle_temperature_k` and boolean `boyle_temperature_above_threshold`, or `None` on refusal;
- `confidence` in `[0,1]`, boolean `abstain`, and unique `evidence_ids` drawn only from returned
  observation and configuration IDs.

For a supported conclusion, `abstain=False`, `selected_model` must be Mie or Morse, and its
intervals must contain the submitted point estimates.  For a library-inadequacy conclusion,
return `selected_model="unsupported"`, `abstain=True`, empty parameter/virial maps and both Boyle
fields as `None`. In either case, `selected_model` must have maximum final hypothesis weight.

## Evaluation

- `combined_score` is the development mean joint of evidence lineage, active acquisition,
  hypothesis retention/discrimination, model choice, parameter and interval recovery, sealed
  energy/force prediction, submitted second-virial curve/Boyle-temperature inference and
  confidence. The virial curve is checked both against truth and for self-consistency with the
  submitted potential parameters.
- `robustness_score` re-evaluates the committed model in sealed short-range, long-range and
  temperature regimes; held-out worlds remain evaluator-only.
- supported coverage, unsupported refusal, false discovery, interval coverage, information gain,
  premature elimination, query cost, reference-policy and oracle-clean controls are reported on
  separate axes rather than collapsed into a claim of discovery.
- every all-world-refusal policy is at or below the explicit split-specific abstention baseline
  and therefore receives normalized headline score zero, regardless of its declared confidence.

The truth-blind reference policy is only a task-calibration witness.  This deterministic
three-particle simulator is not molecular dynamics, an interatomic potential for a material, a
thermodynamic measurement or evidence of autonomous scientific discovery.

## Rules

- Only edit `solution.py`; keep `calibrate_forcefield(problem, query)`.
- Deterministic CPU code using the Python standard library, NumPy and SciPy only.
- Do not assume hidden-world order, parameters, query noise, model family or evaluator seeds. The
  public `problem` is identical across worlds; only callback observations carry world evidence.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.

References: Ercolessi and Adams, DOI `10.1209/0295-5075/26/8/005`; Wang, Martinez and
Pande, DOI `10.1021/jz500737m`; Shell, DOI `10.1063/1.2992060`; Frederiksen et al., DOI
`10.1103/PhysRevLett.93.165501`; Henderson, DOI `10.1016/0375-9601(74)90847-0`;
Axilrod and Teller, DOI `10.1063/1.1723844`.

## Inputs the candidate receives

Every key the task passes to the candidate, taken from the baseline's reads and from the
evaluator's own construction of the input mapping. Names are part of the contract: a candidate
that reaches for one of these quantities under a different name raises at runtime and scores
nothing, and that zero cannot be told apart from a zero earned on the science.

| key | |
|---|---|
| `boyle_temperature_bounds_k` | passed in, unused by the baseline |
| `boyle_temperature_threshold_k` | passed in, unused by the baseline |
| `coordinate_abs_bound_a` | passed in, unused by the baseline |
| `distance_bounds_a` | read by the baseline |
| `first_query_distance_bounds_a` | passed in, unused by the baseline |
| `first_query_max_configurations` | passed in, unused by the baseline |
| `first_query_max_distance_ratio` | passed in, unused by the baseline |
| `first_query_temperature_k` | read by the baseline |
| `hypothesis_names` | passed in, unused by the baseline |
| `max_batch_configurations` | passed in, unused by the baseline |
| `max_query_calls` | passed in, unused by the baseline |
| `minimum_retained_weight` | passed in, unused by the baseline |
| `model_families` | passed in, unused by the baseline |
| `nominal_energy_noise_sigma_ev` | passed in, unused by the baseline |
| `nominal_force_noise_sigma_ev_per_a` | passed in, unused by the baseline |
| `parameter_interval_confidence` | passed in, unused by the baseline |
| `query_budget_units` | passed in, unused by the baseline |
| `schema_version` | passed in, unused by the baseline |
| `second_virial_bounds_cm3_mol` | passed in, unused by the baseline |
| `temperatures_k` | passed in, unused by the baseline |
| `virial_temperature_grid_k` | passed in, unused by the baseline |

`sle.contract_lint` is importable inside the sandbox and costs no oracle call.
