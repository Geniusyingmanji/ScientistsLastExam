# TransitTimingAttribution — what causes the transit-time variations?

## Scientific question

A linear transit ephemeris is showing timing residuals. Are they caused by a gravitationally
perturbing planet, stellar activity, a drifting clock, or a signal outside the declared model family?
The agent may buy a limited number of follow-up transit timings and must choose which transit numbers
to observe before reporting a mechanism and a forecast.

## Entrypoint

```python
def attribute_ttv(observation, measure, budget_units):
    ...
```

`observation` contains `transit_numbers`, `timing_offsets_days`, `timing_uncertainties_days`,
`budget_transits`, `query_ids`, `planet_period_grid`, `activity_period_grid`,
`activity_secondary_period`, `clock_polynomial_degree`, `forecast_transit_number`,
`maximum_followup_transit_number`, and `note`. `measure(transit_number)` costs one unit and returns
`transit_number`, `timing_offset_days`, `uncertainty_days`, `query_id`, and `remaining_budget`.

Return `{"abstain": True}` or a dict with `mechanism` (`planet`, `activity`, or `clock`), positive
`period`, finite `next_offset_days` predicted at `forecast_transit_number`, `[0,1]` `confidence`,
at least two `evidence_query_ids`, and `abstain: False`. Evidence IDs must come from the current
world.

## Scoring and safety

Development worlds contain planet, activity, clock, and unsupported cases. Valid claims receive
mechanism, period, forecast, coverage, and false-discovery metrics; correctly abstaining on the
unsupported family is rewarded. A sealed shifted set tests transfer to new noise and phases.
`development_mechanism_score` and `validation_mechanism_score` report the fraction of supported
worlds with a correctly claimed mechanism. Each has accompanying `mechanism_correct_count` and
`mechanism_total_count` keys with the same split prefix. Abstention on a supported world counts as
incorrect; unsupported worlds are assessed by the refusal and false-discovery metrics.
Wrong mechanism claims receive no period or forecast credit. Each supported-world score is
0.55 for a correct mechanism plus 0.25 times period quality and 0.20 times forecast quality;
abstention scores zero. Period quality is exponential relative-period accuracy for planets and
0.5 for other supported mechanisms; forecast quality is exponential absolute error with scale
four times the timing uncertainty. An unsupported-world refusal scores one, any claim zero.
The headline score is `max(0, (sum(world_scores) - unsupported_count) / supported_count)`
multiplied by the correct-refusal rate on unsupported worlds.
Thus blanket refusal scores zero and false claims on unsupported signals reduce the headline.
Never refusing also scores zero, even with otherwise accurate supported-model fits.
Rate metrics include counts and denominators. Instance order and split sizes are not a contract;
each world starts a fresh candidate session, and the follow-up budget is four measurements.
Malformed output, invented evidence, and budget overspend fail closed.

## Relationship to nearby tasks

Unlike `Exoplanets/RadialVelocityPlanets`, this task attributes transit residuals with paid follow-up
choices rather than searching a fixed radial-velocity series. Unlike `ParticlePhysics/LookElsewhereAnomaly`,
the claim is a physical timing mechanism, and refusal concerns unsupported residual structure,
not global anomaly significance. Shifted timing/noise instances test transfer of that attribution.

## Reference checks

The reference scores 0.900201 on development and 0.901472 on held-out. Removing the activity
model gives 0.549472/0.336474; fixing the forecast to zero gives 0.833582/0.480681; disabling
refusal gives 0/0. Fixed-family and old call-order probes also give 0/0. The measured low-dimensional
families remain below the selected reference: family A (360 points) reaches 0.900219/0.892128,
family B (384 points) reaches 0.900219/0.892128, and family C (210 points) reaches 0.717580/0.888285.
The selected spread-three reference is 0.900201/0.901472; these are finite grid measurements, not
an exhaustive shortcut upper bound.

## Rules

- Only edit `solution.py`; preserve `attribute_ttv`.
- Use deterministic CPU code with Python, NumPy, SciPy, and the standard library.
- Do not read `verification/` or `frontier_eval/`, use the network, or create processes.
- `sle.contract_lint` is available for checking the submission shape and costs no follow-up budget.
