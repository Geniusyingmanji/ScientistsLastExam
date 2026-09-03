# ForcedSignalAttribution

## The question

A regional field is observed for `years` years over `regions` regions. It may contain a forced
response - a fixed spatial pattern growing along a known time profile, scaled by an unknown
amplitude `beta` - on top of internal variability that is red in time and correlated in space. A
climate model gives you two things: a `fingerprint` (the ensemble mean of `forced_ensemble_size`
forced runs, so it carries the model's own variability averaged down), and, on request, unforced
control runs. Control years are your budget.

Is the forced response detectable in the observations, how large is `beta` - and, before either,
can this model be trusted to answer?

## Three traps

- **Red noise trends.** The leading modes of internal variability have year-to-year memory, and a
  record of red noise contains trends that look forced. A test that assumes independent years, or
  that has seen too few control years, detects a forced response where there is none.
- **A noisy fingerprint attenuates the fit.** The fingerprint is an ensemble mean of a few runs, so
  it carries noise of its own. Ordinary regression of observations on a noisy regressor biases the
  amplitude towards zero; the interval then misses the truth on the low side.
- **An untrustworthy model still returns a number.** If the model's forced pattern points the
  wrong way, or its control runs are too quiet, the regression still produces an amplitude and a
  confidence interval. What is left after the fit is the evidence: if the residual does not look
  like the model's own variability, neither the fingerprint nor the interval can be trusted, and
  the honest answer is to decline.

An unforced world with a trustworthy model is **not** the declining case: "no detectable forced
response" is the finding. Declining there is a missed finding; detecting there is a false one.

## Where the budget actually goes

The detection statistic - the observations' projection onto the fingerprint in a space where the
model's variability is white - has a null distribution that only the control runs can tell you.
Long segments show what a record-length of red noise can do; many segments pin the spread down;
and the same segments calibrate the residual test. `control_budget_years` is the whole allowance
for all of that, spent in segments of at least `min_segment_years` years.

## What you implement

```python
def attribute(problem, run_control):
    ...
    return {"detected": True, "scaling_factor": 1.03, "interval": [0.41, 1.65],
            "confidence": 0.7, "abstain": False}
```

### `problem` - every key you are given

| key | meaning |
|---|---|
| `regions` | number of regions (24 in development) |
| `years` | length of the record in years (60 in development) |
| `control_budget_years` | total unforced model years you may request (600 in development) |
| `min_segment_years` | the shortest control segment you may request (20) |
| `forced_ensemble_size` | how many forced runs the fingerprint averages (3) |
| `amplitude_tolerance` | relative amplitude error at which the amplitude score reaches zero (0.5) |
| `observations` | `years x regions` nested list: the record |
| `fingerprint` | `years x regions` nested list: the model's forced response, ensemble-averaged |
| `forcing_time_profile` | `years` floats: the known time profile the forced pattern grows along |
| `measurement_model` | prose: how observations and fingerprint are composed |
| `control_model` | prose: what `run_control` returns |
| `abstain_when` | prose: when the model cannot be trusted to answer |

### `run_control(years)`

Returns one unforced model segment as a `years x regions` nested list and charges `years`
against `control_budget_years`. `years` must be an integer of at least `min_segment_years`.
Requesting past the budget raises and the world scores zero, so keep count. Every call is an
independent realisation of the model's internal variability.

### What you return

| key | meaning |
|---|---|
| `detected` | `True` if you claim the forced response is present |
| `scaling_factor` | your estimate of `beta` |
| `interval` | `[low, high]`: your 90% interval for `beta` |
| `confidence` | in `[0, 1]`; clipped |
| `abstain` | `True` to decline: the residual is inconsistent with the model's variability |

When abstaining the other keys may be omitted. Otherwise `detected` is required, `scaling_factor`
and both interval ends must be finite with `low <= high`. Anything malformed scores that world
zero. It is never an infrastructure failure. `sle.contract_lint` is importable and free to call for
shape checks; it costs no control years.

## How you are scored

Each world contributes a mechanism score:

- **forced, trustworthy model**: 0 unless you detect. If you do, the amplitude score
  `max(0, 1 - |scaling_factor - beta| / (amplitude_tolerance * beta))`, multiplied by 1 if your
  interval covers `beta` and by 0.5 if it does not. Declining scores 0.
- **unforced, trustworthy model**: `detected = False` scores 1; detecting scores 0 and is a false
  discovery; declining scores 0.
- **untrustworthy model** (control runs too quiet, or a fingerprint pointing the wrong way):
  declining scores 1; any claim scores 0, and a detection there is a false discovery.

`combined_score` is the mean over the development worlds, renormalised so that **declining every
world scores exactly 0.0**.

Reported separately, never averaged into one number:

`detection_rate` · `amplitude_score` · `interval_coverage` · `false_discovery_rate` ·
`unforced_false_detection_rate` · `correct_refusal_rate` · `discovery_coverage` ·
`confidence_calibration`

A sealed held-out set of eight larger worlds (30 regions, 80 years, 800 control years) is scored
too and is not visible to a searcher.

## What each competence is worth

Ablating the reference - one choice changed at a time:

| strategy | score | detection | amplitude | coverage | false detection (unforced) | refusal | held out |
|---|---|---|---|---|---|---|---|
| EOF-truncated total least squares + control-window null + noise-aware residual test | **0.722** | 1.00 | 0.52 | 0.75 | 0.00 | 1.00 | 0.632 |
| same, ordinary least squares instead of total least squares | 0.476 | 1.00 | 0.16 | 0.00 | 0.00 | 1.00 | 0.400 |
| same, never declining (no residual test) | 0.293 | 1.00 | 0.52 | 0.75 | 0.00 | 0.00 | 0.032 |
| same, white-noise standard error instead of the control null | 0.491 | 1.00 | 0.52 | 0.25 | 0.33 | 1.00 | 0.227 |
| same, spending only two record-lengths of control years | 0.472 | 1.00 | 0.41 | 0.75 | 0.33 | 1.00 | 0.238 |
| declining everything | 0.000 | 0.00 | - | - | 0.00 | 1.00 | 0.000 |

The reference's amplitude score is 0.52: its intervals are honest but wide, and its point
estimates scatter. That, a truncation chosen for the fingerprint rather than by a variance
fraction, and a null distribution that respects the overlap of its control windows, are the
headroom left on the table.

## Rules

- Only edit `solution.py`; keep `attribute(problem, run_control)`.
- `sle.contract_lint` is importable and free to call for shape checks. It costs no control years.
- Do not read `verification/` or `frontier_eval/`.
