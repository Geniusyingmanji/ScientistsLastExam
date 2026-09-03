# ForcedSignalAttribution - reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_fingerprinting.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_fingerprinting.py`

Truth-blind: it reads only the public problem and the charged control runs.

| metric | development | held out |
|---|---|---|
| mechanism score (normalized) | **0.722** | 0.632 |
| detection rate (forced worlds) | 1.00 | 0.67 |
| amplitude score | 0.52 | - |
| interval coverage | 0.75 | - |
| false detection (unforced worlds) | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |
| control years | 600 of 600 | 800 of 800 |

Its design: control segments the length of the record until the budget is spent; EOFs of the
pooled control years, truncated at 90% of the variance and at most eight modes, as the whitening;
total least squares of the whitened observations on the whitened fingerprint with the noise ratio
`1 / forced_ensemble_size`; the null spread of that statistic from overlapping record-length
windows of the pooled control years, step five; and a refusal when the fit's residual, normalised
by the fingerprint-noise inflation it must carry, exceeds the 95th percentile of the control
windows' residuals.

**The reference is deliberately not at the ceiling.** Its amplitude score is 0.52 and one of its
four intervals misses. On the held-out split it fails to detect the weakest forcing. A truncation
chosen for the fingerprint, a null distribution that respects the window overlap, and a sharper
consistency test are the headroom a better searcher is supposed to claim. This is the admission
bar recorded in the card: a first model proposal that reaches the reference means the task needs
hardening before it is anything more than an on-ramp.

Over twenty extra unforced development-sized worlds the reference detects in 0; over twenty extra
forced worlds at `beta = 1` it detects in 17 with a mean estimate of 1.02.

## Baseline - `solution.py`

Regional-mean series regressed on the fingerprint's regional mean by ordinary least squares with a
white-noise interval; never declines; spends no control years.

| metric | value |
|---|---|
| combined score | **0.025** |
| amplitude score | 0.08 |
| false discovery rate | 0.17 (held out 0.40) |
| correct refusal rate | 0.00 |

Over twenty extra unforced worlds it detects in 7: the red-noise trap in numbers.

## Difficulty ladder

| strategy | score | detection | amplitude | coverage | false detection (unforced) | refusal | held out |
|---|---|---|---|---|---|---|---|
| TLS + control-window null + noise-aware residual test (reference) | 0.722 | 1.00 | 0.52 | 0.75 | 0.00 | 1.00 | 0.632 |
| same, ordinary least squares instead of TLS | 0.476 | 1.00 | 0.16 | 0.00 | 0.00 | 1.00 | 0.400 |
| same, never declining | 0.293 | 1.00 | 0.52 | 0.75 | 0.00 | 0.00 | 0.032 |
| same, white-noise standard error instead of the control null | 0.491 | 1.00 | 0.52 | 0.25 | 0.33 | 1.00 | 0.227 |
| same, two record-lengths of control years | 0.472 | 1.00 | 0.41 | 0.75 | 0.33 | 1.00 | 0.238 |
| declining everything | 0.000 | - | - | - | 0.00 | 1.00 | 0.000 |

The ladder is not a difficulty measurement; difficulty is measured by a frontier-model draw, which
has not been run yet. What the ladder shows is where the score lives: the fit (total least
squares, +0.25), the refusal (+0.43), and the null distribution and the budget that feeds it
(+0.23 and +0.25).

## Robustness

- Eleven malformed candidate shapes - raising, `None`, a string, a claim without `detected`, an
  inverted interval, a NaN amplitude, a three-element interval, overspending the budget, a
  five-year segment, a float segment length and a NaN confidence - all score zero with
  `valid = 0`, and none raises out of the evaluator.
- Two consecutive evaluations of the reference are key-identical.
- Declining every world scores exactly 0.0 by construction of the normalisation.
