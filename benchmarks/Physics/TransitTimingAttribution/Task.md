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
Malformed output, invented evidence, and budget overspend fail closed.

## Rules

- Only edit `solution.py`; preserve `attribute_ttv`.
- Use deterministic CPU code with Python, NumPy, SciPy, and the standard library.
- Do not read `verification/` or `frontier_eval/`, use the network, or create processes.
- `sle.contract_lint` is available for checking the submission shape and costs no follow-up budget.
