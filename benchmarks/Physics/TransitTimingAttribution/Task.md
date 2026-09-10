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

Development worlds contain planet, activity, clock, and two physically distinct unsupported
processes: a stationary extra component and a non-stationary phase evolution. Valid claims receive
mechanism, period, forecast, coverage, and false-discovery metrics; correctly abstaining on an
unsupported process is rewarded. A sealed shifted set tests transfer to new noise and phases.
`development_mechanism_score` and `validation_mechanism_score` report the fraction of supported
worlds with a correctly claimed mechanism. Each has accompanying `mechanism_correct_count` and
`mechanism_total_count` keys with the same split prefix. Abstention on a supported world counts as
incorrect; unsupported worlds are assessed by the refusal and false-discovery metrics.
Planet and activity periods vary continuously around the reconnaissance grids supplied in the
observation; those grids are starting points, not a finite answer list. A correct planet/activity
claim receives 0.45 mechanism credit, 0.30 period-quality credit and 0.25 forecast credit. A correct
clock claim receives 0.65 mechanism credit and 0.35 forecast credit. Wrong mechanisms and supported
abstentions score zero. Period quality decays exponentially with relative error; forecast quality
decays exponentially with absolute error at four times the timing uncertainty. An unsupported-world
refusal scores one and any unsupported claim scores zero.
The headline score is `max(0, (sum(world_scores) - unsupported_count) / supported_count)`
multiplied by the correct-refusal rate and squared discovery precision `(1-FDR)^2`.
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

The truth-blind reference uses three spread observations and a fourth model-disagreement query,
then continuously refines periodic fits. It scores 0.632413 on development and 0.430139 on held-out.
Two follow-ups score 0.259425/0.241203; removing the activity model gives 0.285567/0.268826;
fixing the forecast to zero gives 0.540351/0.359365; disabling refusal gives 0/0. Constant-family
and old call-order probes also give 0/0. Three development-selected fixed-schedule grids remain
below the reference: the full three-diagnostic family (800 policies) reaches 0.574956/0.301806,
the no-BIC family (160) reaches 0.492715/0.206081, and the no-RMS family (160) reaches
0.441114/0.235989. These are measured finite grids, not universal shortcut bounds.

## Rules

- Only edit `solution.py`; preserve `attribute_ttv`.
- Use deterministic CPU code with Python, NumPy, SciPy, and the standard library.
- Do not read `verification/` or `frontier_eval/`, use the network, or create processes.
- `sle.contract_lint` is available for checking the submission shape and costs no follow-up budget.
