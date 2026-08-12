# Radial-velocity planet detection

A star's spectrum shows a periodic Doppler shift. Some of the periods are planets. Say which.

## Why the hard part is not finding peaks

A planet makes a star wobble, and the wobble is a sinusoid in the radial-velocity series. Finding
sinusoids is easy. The founding difficulty of this field is that **most strong periods are not
planets**: a rotating star with spots produces a signal at its rotation period and at harmonics of
it, and nightly observing produces one-day aliases of everything. The literature carries retracted
detections traced to each of these.

So the failure this task is built to expose is not a missed planet. It is a claimed one.

## Your function

```python
def detect_planets(observation) -> dict:
    ...
```

`observation` gives `times`, `velocities`, `uncertainties` and the fractional `period_tolerance`.
Return

```python
{"planets": [{"period": P}, ...]}     # at most six
{"abstain": True}                      # when the period is not identifiable
```

## Oracle

Periodograms and false-alarm probabilities come from **astropy**'s `LombScargle`, the standard
tool for unevenly sampled astronomical series. It is available to you as well.

## Three axes, reported separately

- **mechanism** — fraction of injected planets recovered, period within tolerance. This is what
  `combined_score` carries.
- **false discovery rate** — of everything claimed, how much was not a planet. Every star here
  carries a rotation signal, and some systems have no planet at all.
- **calibrated refusal** — some systems have a planet whose one-day cadence alias fits the data
  equally well. Nothing in the series separates the two periods, and abstaining is the only
  correct answer. Abstaining on a determined system scores zero for it.

The axes are printed side by side and must not be averaged. The shipped reference recovers a
respectable share of the planets **while most of what it claims is not a planet** — a single
number would report the first and hide the second.

## Rules

- Only edit `solution.py`; keep `detect_planets(observation)`.
- Deterministic CPU code. The standard library, NumPy, SciPy and astropy are available.
- At most six claims. `frontier_science.contract_lint` is importable for shape checks.
- Do not read `verification/` or `frontier_eval/`.

## Difficulty

Systems are generated from a seeded draw. Harder levels weaken the planets against the activity
signal and shorten the baseline. The regime was chosen by measurement: with strong planets in
quiet stars both the baseline and the reference recover everything and the mechanism axis stops
discriminating.
