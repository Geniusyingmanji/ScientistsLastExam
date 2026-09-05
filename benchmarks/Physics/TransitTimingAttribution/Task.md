# TransitTimingAttribution — what causes the transit-time variations?

## Scientific question

A linear transit ephemeris is showing timing residuals. Are they caused by a gravitationally
perturbing planet, stellar activity, a drifting clock, or a signal outside the declared model family?
The agent may buy a limited number of follow-up transit timings and must choose which transit numbers
to observe before reporting a mechanism and a forecast.

This is distinct from `Exoplanets/RadialVelocityPlanets`: that task detects periodic Doppler signals
in radial velocity data. This task uses transit timing residuals, active scheduling, long-baseline
alias breaking, and explicit clock/activity confounds.

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
`period`, finite `next_offset_days` predicted at `forecast_transit_number`, `[0,1]` `confidence`, at least two `evidence_query_ids`, and
`abstain: False`. Evidence IDs must come from the current world.

## Scoring and safety

Development worlds contain planet, activity, clock, and unsupported cases. Valid claims receive
mechanism, period, forecast, coverage, and false-discovery metrics; correctly abstaining on the
unsupported family is rewarded. A sealed shifted set tests transfer to new noise and phases.
Malformed output, invented evidence, and budget overspend fail closed. The emulator is a procedural
reduced-order witness, not a replacement for photodynamical N-body fitting or real telescope scheduling.

## Construction notes

The intended insight is that sparse early transits cannot separate a long-period sinusoid from activity
or a clock trend; targeted late and interleaved transit numbers provide leverage. Useful ablations are
no follow-up, contiguous-only follow-up, no clock term, and never abstaining. Public families and this
signal model require future server-held families and external astronomy review before certification.
