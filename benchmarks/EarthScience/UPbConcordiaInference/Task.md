# UPbConcordiaInference - infer a zircon event history

## 关系与区别 / How this differs from the nearest tasks in this repository

- `Geophysics/GravityInversion` recovers spatial density sources from a field. This task recovers
  geological event ages and decides whether coupled radioactive-decay measurements support a
  declared event-history family.
- `Exoplanets/RadialVelocityPlanets` also separates a supported signal from alternatives, but its
  artifact is a set of orbital periods rather than the intercepts and adequacy of a decay curve.
- `Spectroscopy/SpinSystemInference` is parameter inversion in a named spectral model. Here the
  history itself is a discovery claim, and resolvable multi-event histories require refusal.

The Frontier-Eng catalogue contains no U-Pb geochronology, concordia or geologic event-history
task. This task therefore occupies discovery/evidence rather than engineering optimization.

## Scientific question

A zircon suite contains 24 candidate analytical domains. With 18 laboratory budget units, decide
whether the suite records one concordant crystallization age or a crystallization followed by one
lead-loss event. Estimate the relevant age or ages. If the measurements resolve more than one
lead-loss episode or another history outside that family, decline instead of publishing a false
geological interpretation.

For age `t` in years, the public Wetherill concordia is

```text
207Pb*/235U = exp(lambda_235 t) - 1
206Pb*/238U = exp(lambda_238 t) - 1
```

A single lead-loss history lies on one straight discordia between two points on this curve. The
upper intercept is the crystallization age and the lower intercept is the lead-loss age.

## What you implement

```python
def infer_upb_history(problem, measure):
    ...
```

### `problem`: every key you receive

| key | meaning |
|---|---|
| `grain_descriptors` | 24 records with `grain_id`, `domain_position`, `uranium_ppm`, and `expected_signal_quality` |
| `measurement_budget_units` | total available measurement cost, 18 |
| `decay_constants_per_year` | mapping with `u235` and `u238` decay constants |
| `age_bounds_myr` | allowed interval for `crystallization_age_myr` |
| `lead_loss_age_bounds_myr` | allowed interval for `lead_loss_age_myr` |
| `crystallization_age_tolerance_myr` | absolute error at which the crystallization-age score reaches zero |
| `lead_loss_age_tolerance_myr` | absolute error at which the lead-loss-age score reaches zero |
| `precision_options` | mappings `screen` and `analytical`, each with `cost` and `relative_sigma_at_quality_one` |
| `concordia_model` | definition and ratio directions of the public concordia |
| `supported_histories` | the history labels candidates may publish: `concordant` and `lead_loss` |
| `measurement_model` | measurement uniqueness, precision and signal-quality behavior |
| `forecast_or_validation_description` | physical interpretation that the cited observations must jointly support |
| `abstain_when` | when the supported family is inadequate and refusal is required |

### `measure(grain_id, precision)`

Each grain can be measured once. `precision` is `screen` or `analytical`; their costs and nominal
uncertainties are published in `precision_options`. Overspending or repeating a grain fails that
world closed. A valid call returns every one of these keys:

| key | meaning |
|---|---|
| `query_id` | stable identifier used to cite this observation |
| `grain_id` | measured grain identifier |
| `pb207_u235` | measured `207Pb*/235U` |
| `pb206_u238` | measured `206Pb*/238U` |
| `sigma_pb207_u235` | one-sigma uncertainty of `pb207_u235` |
| `sigma_pb206_u238` | one-sigma uncertainty of `pb206_u238` |
| `correlation` | correlation between the two ratio errors |
| `precision` | precision mode used |
| `budget_cost` | cost of this call |
| `budget_used` | cumulative cost including this call |

### What you return

Return a mapping with these keys:

| key | meaning |
|---|---|
| `history` | `concordant` or `lead_loss`; omit only when abstaining |
| `crystallization_age_myr` | finite age inside `age_bounds_myr`; omit only when abstaining |
| `lead_loss_age_myr` | finite age inside `lead_loss_age_bounds_myr`, required for `lead_loss` and younger than crystallization |
| `confidence` | finite number in `[0, 1]` |
| `evidence_query_ids` | non-empty list of distinct `query_id` values returned in this world |
| `abstain` | boolean; true when the supported history family is inadequate |

Malformed output scores the world as invalid instead of raising from the evaluator.
`sle.contract_lint` is importable and free to call for shape checks; it consumes no laboratory
budget.

## Scoring

Development contains six single lead-loss histories, two concordant suites and two resolvable
multi-event suites. A correct concordant history receives 0.40 plus 0.60 times its crystallization
age score. A correct lead-loss history receives 0.30 plus 0.40 times its crystallization-age score
and 0.30 times its lead-loss-age score. Each age score falls linearly to zero at its published
tolerance. A correct refusal on an unsupported history receives 1; a wrong history or false claim
receives 0.

`combined_score` is mean development mechanism recovery, normalized so a valid method that
declines every suite scores exactly 0. The evaluator separately reports history accuracy,
crystallization- and lead-loss-age scores, false-discovery rate, correct-refusal rate, discovery
coverage and confidence calibration. It publishes denominators for false discovery, refusal and
coverage. A sealed held-out suite reports transfer metrics but is not search-visible.

## Measured difficulty

| method | development | held out |
|---|---:|---:|
| truth-blind weighted concordia/discordia reference | 0.914 | 0.818 |
| same fit with only three analytical measurements | 0.861 | 0.609 |
| contiguous-domain sampling | 0.550 | 0.383 |
| all-screen measurements | 0.494 | 0.487 |
| best of 192 apparent-age threshold shortcuts | 0.345 | 0.379 |
| fixed one-grain baseline | 0.000 | 0.000 |

Two clean-run DeepSeek V4 Flash trajectories reached 0.231 and 0.560 after three proposals; two
DeepSeek V4 Pro trajectories reached 0.203 and 0.262. All four first proposals remained below the
reference. Exact runs and the wider ablation ladder are recorded in `references/known_best.md`.

## Rules

- Only edit `solution.py`; retain `infer_upb_history(problem, measure)`.
- Use only the Python standard library and NumPy.
- Do not use the network, create processes, or read `verification/` or `frontier_eval/`.
