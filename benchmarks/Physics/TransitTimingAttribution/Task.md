# TransitTimingAttribution — what causes the transit-time variations?

## Scientific question

A linear transit ephemeris is showing timing residuals. Are they caused by a gravitationally
perturbing planet, stellar activity, a drifting clock, or a signal outside the declared model family?
The agent may buy a limited number of follow-up transit timings and must choose which transit numbers
to observe before reporting a mechanism and a forecast.

This is a reduced-order model-selection laboratory. `planet`, `activity`, and `clock` name the
declared synthetic residual families, and a correct label establishes a match within this laboratory.
It is not a unique causal identification from real stellar observations. The returned periodic
parameter describes the timing-modulation period in transit-number units; it is not the orbital
period or mass of an unseen planet. Sinusoidal TTV approximations and the possibility of spot-induced
timing biases motivate the periodic families. The activity family's extra periodic component is a
phenomenological nuisance surrogate, not a derivation of a starspot light curve. The clock family uses
the quadratic time-error form induced by a constant frequency offset plus linear frequency drift.
Noise, component coefficients, and unsupported alternatives are controlled benchmark design choices.
The task tests acquisition, family discrimination, forecasting, and refusal under these declared assumptions.

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

Development worlds contain three independently seeded panels of planet, activity, clock, and two
distinct out-of-family processes: a stationary extra component and a non-stationary phase
evolution. Initial time-series length, noise, signal coefficients, follow-up range, and forecast
horizon vary across worlds. Valid claims receive mechanism, period, forecast, acquisition-design,
coverage, and false-discovery metrics; correctly abstaining on an unsupported process is rewarded.
A separately seeded shifted set tests transfer.
`development_mechanism_score` and `validation_mechanism_score` report the fraction of supported
worlds with a correctly claimed mechanism. Each has accompanying `mechanism_correct_count` and
`mechanism_total_count` keys with the same split prefix. Abstention on a supported world counts as
incorrect; unsupported worlds are assessed by the refusal and false-discovery metrics.
Planet and activity periods vary continuously around the reconnaissance grids supplied in the
observation; those grids are starting points, not a finite answer list. For a correct periodic-family
claim, mechanism, period, forecast, and acquisition design contribute 0.35, 0.25, 0.20, and 0.20.
For a correct clock claim they contribute 0.50, 0, 0.30, and 0.20. Acquisition design is the summed
local parameter sensitivity at the distinct cited follow-ups, normalized by the best budget-sized
set available in that world. Repeating a transit does not earn design credit twice. Wrong mechanisms
and supported abstentions score zero. Period quality decays exponentially with relative error;
forecast quality decays exponentially with absolute error at four times the timing uncertainty. An
unsupported-world refusal scores one and any unsupported claim scores zero.
Each split score is `max(0, (sum(world_scores) - unsupported_count) / supported_count)`
multiplied by the correct-refusal rate and cubed discovery precision `(1-FDR)^3`. The headline
`combined_score` equals the development split score for candidates valid on every world.
The sealed-split scientific score and held-out diagnostics are evaluator-only confirmation
evidence and do not influence the public objective for those valid candidates.
Thus blanket refusal scores zero and false claims on unsupported signals reduce the headline.
Never refusing also scores zero, even with otherwise accurate supported-model fits.
Rate metrics include counts and denominators. Instance order and split sizes are not a contract;
each world starts a fresh candidate session, and the follow-up budget is five measurements.
All-world validity remains a public feasibility gate: malformed output, invented evidence,
candidate exceptions, or budget overspend on any development or sealed world reject the entire
submission with `valid=0` and `combined_score=0`.

## Relationship to nearby tasks

Unlike `Exoplanets/RadialVelocityPlanets`, this task attributes transit residuals with paid follow-up
choices rather than searching a fixed radial-velocity series. Unlike `ParticlePhysics/LookElsewhereAnomaly`,
the claim identifies a declared synthetic timing family, and refusal concerns out-of-family residual structure,
not global anomaly significance. Shifted timing/noise instances test transfer of that attribution.

## Reference checks

The truth-blind reference repeatedly chooses the follow-up with the greatest weighted disagreement
among retained planet, activity, and clock fits. It continuously refines periodic fits and compares
every claimed supported fit with stationary-extra-component and phase-evolution alternatives. Its
development score is 0.594835. A development-only scan of 3,840 normalized fixed schedules and
evidence-threshold combinations reaches 0.432153, or 72.65% of the reference, below the retained
80% limit. Removing the last two active measurements gives 0.238873; removing the activity family or
out-of-family evidence gives 0.252756 and 0.052701; replacing the forecast with zero gives 0.526721. Exact
protocols and historical contracts are recorded in `references/known_best.md`.

Earlier records used the minimum of development and held-out scores as the public headline.
That feedback defect has been removed. The original reference, ablation, grid and model records
remain explicitly historical in `references/known_best.md`; they are not new measurements under
the development-only contract. The finite grids are not universal shortcut bounds.

## Rules

- Only edit `solution.py`; preserve `attribute_ttv`.
- Use deterministic CPU code with Python, NumPy, SciPy, and the standard library.
- Do not read `verification/` or `frontier_eval/`, use the network, or create processes.
- `sle.contract_lint` is available for checking the submission shape and costs no follow-up budget.

## Scientific grounding and limits

- Agol et al. (2005), DOI `10.1111/j.1365-2966.2005.08922.x`, and Holman and Murray (2005),
  DOI `10.1126/science.1107822`, provide the physical motivation for TTV observations.
- Lithwick, Xie and Wu (2012), *Extracting Planet Mass and Eccentricity From TTV Data*,
  [DOI 10.1088/0004-637X/761/2/122](https://arxiv.org/abs/1207.4192v2), supports analytic sinusoidal
  TTV approximations near first-order resonance. It does not validate arbitrary orbital or mass
  recovery from this laboratory's fitted timing-modulation period.
- Oshagh et al. (2013), *Effect of stellar spots on high-precision transit light-curve*,
  [DOI 10.1051/0004-6361/201321309](https://www.aanda.org/articles/aa/full_html/2013/08/aa21309-13/aa21309-13.html),
  supports spot-induced timing bias; the fixed secondary sinusoid here is a phenomenological choice.
- Allan (1975), *The Measurement of Frequency and Frequency Stability of Precision Oscillators*,
  [NBS Technical Note 669, Fig. 7](https://tf.nist.gov/general/pdf/74.pdf), describes linear frequency
  drift producing quadratic time deviation. The coefficients, noise and query budget here are
  benchmark choices, not measured oscillator or stellar parameters.
