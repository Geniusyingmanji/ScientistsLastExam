# ModalDamageAttribution — reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_modal_ratios.py \
    --metrics-out /tmp/metrics.json
```

## Reference — `verification/reference_modal_ratios.py`

Truth-blind: it reads only the public problem and the budgeted campaign.

| metric | development | held out |
|---|---|---|
| mechanism score (normalized) | **0.665** | 0.535 |
| localisation rate | 0.83 | 0.80 |
| severity score | 0.61 | — |
| healthy false alarm rate | 0.00 | 0.00 |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |
| discovery coverage | 0.75 | — |
| days measured | 9 of 9 | 9 of 9 |

Its design: buy the nine highest-excitation days; average the frequency ratios `f_k / f_1`, which
cancel the temperature factor exactly; enumerate the declared damage family by re-solving the
eigenproblem for every internal element on a severity grid; call a shift below the detection
threshold healthy, the best family member the answer when its residual is small relative to the
shift, and anything else a support change.

**The reference is deliberately not at the ceiling.** Its coverage is 0.75: it declines two damaged
structures it should have solved, because it measures the shift against the model's own healthy
ratios and the published model carries three per cent of error against the real structure. The
commissioning campaign measured the real structure, so using its ratios as the baseline instead
recovers both — worth **+0.125** and runnable as a one-line change. Its severity grid is coarse
against the scoring tolerance, its days are averaged with equal weight although their noise differs
threefold, and its refusal threshold is a fixed fraction rather than what the measured noise says a
fit should leave behind. Each of those is a scoring axis.

## Baseline — `solution.py`

Spreads its days over the widest temperature range, fits a straight line to the commissioning
frequencies against temperature, extrapolates it, and calls the largest deviation damage. Never
declines.

| metric | value |
|---|---|
| combined score | **0.0000** |
| localisation rate | 0.33 |
| healthy false alarm rate | 1.00 |
| false discovery rate | 0.80 |

Confidently wrong rather than empty: both healthy structures are reported as damaged, because half
its budget lands outside the commissioning band where the linear law is not the law.

## Difficulty ladder

| strategy | score | localisation | severity | healthy false alarm | false discovery | refusal | coverage | held out |
|---|---|---|---|---|---|---|---|---|
| ratios + family search + relative-residual refusal (reference) | 0.665 | 0.83 | 0.61 | 0.00 | 0.00 | 1.00 | 0.75 | 0.535 |
| same, calibrating the healthy ratios on the commissioning data | 0.790 | 0.83 | 0.61 | 0.00 | 0.00 | 1.00 | 0.88 | 0.535 |
| same, absolute frequencies instead of ratios | 0.357 | 0.33 | 0.29 | 0.00 | 0.00 | 1.00 | 0.38 | 0.000 |
| same, never declining | 0.513 | 1.00 | 0.70 | 0.50 | 0.30 | 0.00 | 1.00 | 0.249 |
| same, coldest days instead of highest excitation | 0.684 | 0.83 | 0.66 | 0.00 | 0.10 | 1.00 | 0.88 | 0.271 |
| same, one day instead of nine | 0.327 | 0.67 | 0.54 | 0.00 | 0.10 | 0.50 | 0.50 | 0.264 |
| same, severity fixed at 0.25 instead of searched | 0.423 | 0.50 | 0.29 | 0.00 | 0.00 | 1.00 | 0.50 | 0.238 |
| temperature-extrapolated absolute frequencies, never declining (baseline) | 0.000 | 0.33 | 0.00 | 1.00 | 0.80 | 0.00 | 1.00 | 0.000 |
| declining everything | 0.000 | — | — | 0.00 | 0.00 | 1.00 | 0.00 | 0.000 |
| never claiming damage | 0.000 | — | — | 0.00 | 0.00 | 0.00 | 1.00 | 0.000 |

The ladder is not a difficulty measurement; difficulty is measured by a frontier-model draw, which
has not been run yet. What it shows is where the score lives: the ratio insight is worth +0.31, the
budget +0.34, the severity search +0.24, the refusal +0.15, and the model calibration the reference
does not do +0.125. The coldest-days row is the cautionary one — better on development, half as
good on the held-out split.

## Shortcut probe

The question this repository learned to ask after a submitted task turned out to be solvable by a
two-parameter grid search: **how far does a low-dimensional strategy get without the science?**

1012 strategies of the form "average the shift over the highest-excitation days, declare healthy
below a threshold, decline above a second threshold, otherwise name the mode with the largest
deviation as the element and set the severity from the shift" were evaluated:

| family | strategies | best score |
|---|---|---|
| without the ratio insight, on temperature-extrapolated absolute frequencies | 506 | **0.459** |
| with the ratio insight, but no family search | 506 | 0.321 |
| reference | — | 0.665 |
| ceiling | — | 1.000 |

## Three construction errors, all found by the checkpoints before any model saw the task

- **The budget was free.** At the first noise level, measuring one day scored 0.685 against nine
  days' 0.652 — the budget bought nothing. The noise was raised until nine days beat one by a third
  of the score.
- **The confound was avoidable.** Excitation quality was originally correlated with temperature, so
  the highest-signal days were the warm days where a linear extrapolation happens to be right. A
  threshold rule on absolute frequencies scored 0.55 against a reference of 0.65 without ever using
  the ratios. Excitation is now drawn independently, and the temperature law bends at both ends of
  the commissioning band.
- **One refusal world was undecidable.** A support change with a weak signal left a fit residual
  inside the range the damaged structures occupy, so declining it could not be earned. The support
  changes are now sized by bisection to land inside the damage signal band, and the refusal is
  judged on the residual *relative* to the shift, where a support change is thirteen times less
  explainable by the declared family than a true damage is.

## Robustness

- Sixteen malformed candidate shapes — raising, `None`, a string, a claim without `damaged`, an
  element of 0, 99, 2.5 and `True`, a NaN severity, a severity of 1.5 and of 0.0, a NaN confidence,
  overspending the budget, a day of 9999, a float day and a boolean day — all score zero with
  `valid = 0`, and none raises out of the evaluator.
- Two consecutive evaluations of the reference are key-identical.
- Declining every structure scores exactly 0.0 by construction of the normalisation; so does never
  claiming damage.
