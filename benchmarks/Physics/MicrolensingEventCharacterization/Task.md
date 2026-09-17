# MicrolensingEventCharacterization

## Scientific problem

Use a finite photometric follow-up budget to characterize a transient gravitational microlensing
event. Decide whether the light curve is a point lens, a binary lens with a localized anomaly, or
intrinsic variable-source activity; estimate its characteristic duration, amplitude, and defining
feature time. Abstain when the available observations do not distinguish a supported model from a
mixed out-of-family event.

Point-lens, binary-lens, and variable-source worlds are supported and intended to be recoverable
when their fitted parameters lie inside the public bounds. The ambiguous family superposes lensing
and periodic variability and is deliberately outside that model set: candidates should abstain when
no supported single-family fit is distinguishable at the reported measurement precision.

This reduced-order laboratory uses the same band scaling for every event family. It does not
model the achromatic-lensing versus chromatic-variability discriminator. Either filter may provide
photometric samples, but color is not a separate mechanism-identification signal here.

## Candidate interface

Implement `infer_microlensing(problem, observe)`.

### Every key in `problem`

| key | meaning |
|---|---|
| `candidate_times` | allowed observation epochs in days |
| `filters` | exactly `['g', 'r']` |
| `filter_costs` | mapping `{'g': 1, 'r': 1}` |
| `observation_budget_units` | total observation allowance, 24 |
| `minimum_evidence_queries` | minimum distinct query IDs to cite, 6 |
| `model_labels` | allowed non-abstaining labels: `point_lens`, `binary_lens`, `variable_source` |
| `timescale_bounds_days` | inclusive output bounds `[2, 24]`; abstain when the observations do not support a value in this range |
| `timescale_definition` | point/binary: full width at half maximum of the underlying point-lens excess flux; variable: period |
| `feature_time_bounds_days` | inclusive output bounds `[-24, 24]` |
| `amplitude_bounds` | inclusive output bounds `[0, 1]` |
| `r_band_baseline_flux` | normalized unlensed r-band baseline, `1.0` |
| `source_fraction_bounds` | inclusive source-flux fraction bounds used by the lens families, `[0.08, 1.0]` |
| `impact_parameter_bounds` | inclusive point-lens impact-parameter bounds, `[0.15, 1.05]` |
| `anomaly_width_bounds_days` | inclusive Gaussian anomaly-width bounds, `[0.55, 3.25]` days |
| `magnification_model` | prose description of the supported point/binary lens family |
| `variability_model` | prose description of the supported variable-source family |
| `abstain_when` | prose rule for refusing mixed out-of-family events |
| `evidence_requirement` | prose requirement for current-world query citations |

### `observe(time, band)`

`time` must be one of `candidate_times` and `band` must be `g` or `r`. Each call costs the value
in `filter_costs`; duplicate `(time, band)` calls, unknown epochs or bands, and overspending fail
closed. The callback returns exactly `query_id`, `time`, `band`, `flux`, `uncertainty`, and
`budget_used`.

## Return value

Return a mapping with boolean `abstain`, finite `confidence` in `[0, 1]`, and at least six distinct
current-world `evidence_query_ids`. A non-abstaining answer additionally contains `model`, finite
`timescale_days` in `[2, 24]`, finite `amplitude` in `[0, 1]`, and finite `feature_time_days` in
`[-24, 24]`. The feature time is the point-lens peak, binary-anomaly center, or a variable-source
brightness peak, respectively. Malformed output or callback
violations score invalid instead of crashing the evaluator. `sle.contract_lint` is importable and
free to call for shape checks.

## Scoring

Supported worlds score model identification (0.40), characteristic-duration recovery (0.20),
amplitude recovery (0.15), feature-time recovery (0.15), and calibrated confidence (0.10).
Confidence is scored by agreement
with the recovered continuous correctness, rather than as an unpenalized declaration. Ambiguous worlds score only for refusal.
`combined_score` is development mechanism recovery normalized so blanket abstention is exactly zero;
model accuracy, false discovery, refusal, budget, feasibility and held-out transfer are reported
separately. Held-out worlds and per-world truth are not search-visible.

The task-local reference uses 24 r-band observations and compares a bounded point-lens fit, a
joint point-lens-plus-local-anomaly fit, and a continuous-period sinusoidal fit. It reports calibrated
confidence and refuses events whose best supported single-family fit leaves excessive residuals.
Events whose supported fit is outside that declared range are treated as out-of-model and should be
reported as abstentions rather than clipped claims. Calibration values are
recorded in `references/known_best.md`; fixed-parameter threshold policies are remeasured with
the current evaluator before release.

## Relationship to nearby tasks

`Exoplanets/RadialVelocityPlanets` analyzes Doppler time series for orbital periods and activity
aliases; this task uses photometric magnification, binary-lens anomalies and source variability.
`Exoplanets/TransmissionSpectrumSpecies` allocates spectral information to identify atmospheric
molecules; this task allocates time-and-filter photometry to distinguish lensing mechanisms.
`Exoplanets/TransitTimingAttribution` (if merged) attributes transit timing perturbations to orbital
or instrumental mechanisms; it has neither microlensing light curves nor binary-caustic model
selection.

## Rules and references

- Only edit `solution.py`; keep `infer_microlensing(problem, observe)`.
- Use deterministic CPU Python, NumPy and the standard library only.
- Do not read `verification/` or `frontier_eval/`, access the network, or create processes.

The point-lens magnification follows the Paczynski microlensing model, while binary-lens caustic
structure and time-domain follow-up motivate the anomaly and active-observation axes:
Paczynski, *ApJ* 304, 1 (1986), DOI `10.1086/164140`; Gould, *ApJ* 392, 442 (1992), DOI
`10.1086/171443`; and Gaudi, *ARA&A* 50, 411 (2012), DOI `10.1146/annurev-astro-081811-125518`.
