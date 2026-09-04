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
| mechanism score (normalized) | **0.733** | 0.587 |
| localisation rate | 0.83 | 0.80 |
| severity score | 0.46 | — |
| healthy false alarm rate | 0.00 | 0.00 |
| false discovery rate | 0.10 | — |
| correct refusal rate | 1.00 | 1.00 |
| discovery coverage | 1.00 | — |
| days measured | 9 of 9 | 9 of 9 |

Its design: take the healthy ratios from the commissioning campaign, which measured the real
structure, rather than from the published model, which is a few per cent away from it; buy the nine
highest-excitation days; average the frequency ratios `f_k / f_1`, which cancel the temperature
factor exactly; enumerate the declared damage family by re-solving the eigenproblem for every
internal element on a severity grid; call a shift below the detection threshold healthy, the best
family member the answer when its residual is small relative to the shift, and anything else a
support change.

**The reference is deliberately not at the ceiling.** Its severity score is 0.46 against a
tolerance of four per cent. Three things are left on the table: the days are averaged with equal
weight although their noise differs threefold, so an inverse-variance average would be strictly
better; the decision is a pair of thresholds rather than a comparison of how well each hypothesis
explains the data under a stated noise model; and the search is over a grid in a quantity the
residual is smooth in. The frontier draw below took all three.

## Model draws — Claude Opus 5

Three seeds, three proposals each, `greedy_rewrite`, normal feedback, budget 3.

**First draw, against the under-built reference**
(`experiments/opus5_modal_damage_attribution_calibration_2026-09-04.json`, reference 0.665):

| seed | proposal 1 | proposal 2 | proposal 3 | best |
|---|---|---|---|---|
| 0 | **0.821** | 0.696 | 0.821 | 0.821 |
| 1 | 0.447 | 0.698 | 0.823 | 0.823 |
| 2 | **0.821** | 0.812 | 0.821 | 0.821 |

Two of three first proposals cleared the reference, so the admission bar failed. Its solution said
why, in its own docstring: it updated the published model against the commissioning campaign,
worked in log-ratio space with inverse-variance weights, and decided between healthy, damaged and
out-of-family by likelihood ratio with a complexity penalty rather than by thresholds.

**The response was to fix the reference, not the world.** Model updating against measurements is
standard practice in structural health monitoring, so a reference that skips it is under-built —
and this repository's own lesson is that a weak reference makes the admission bar meaningless. The
reference now takes its healthy ratios from the campaign; the severity tolerance was tightened from
0.12 to 0.04 at the same time, because a repair decision turns on a few per cent of section loss.

**Second draw, against the corrected reference**
(`experiments/opus5_modal_damage_attribution_calibration_2026-09-04_v2.json`, reference 0.733):

| seed | proposal 1 | proposal 2 | proposal 3 | best |
|---|---|---|---|---|
| 0 | 0.622 | 0.613 | 0.748 | **0.748** |
| 1 | 0.725 | 0.724 | 0.724 | 0.725 |
| 2 | 0.725 | 0.726 | 0.731 | 0.731 |

**The admission bar holds: no first proposal reaches the reference's 0.733.** The best of nine is
0.748 against a ceiling of 1.0, so the task is not saturated at the frontier, and the remaining
quarter of the scale is the severity axis and the inverse-variance weighting the reference does not
do. Seed 0 is the trajectory worth reading: 0.622 to 0.613 to 0.748, a rejected middle proposal and
then a real gain.

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
| commissioning baseline + ratios + family search + relative-residual refusal (reference) | 0.733 | 0.83 | 0.46 | 0.00 | 0.10 | 1.00 | 1.00 | 0.587 |
| same, healthy ratios from the published model instead of the campaign | 0.544 | 0.83 | 0.28 | 0.00 | 0.10 | 1.00 | 0.88 | 0.515 |
| same, absolute frequencies instead of ratios | 0.418 | 0.33 | 0.11 | 0.00 | 0.00 | 1.00 | 0.50 | 0.214 |
| same, never declining | 0.483 | 0.83 | 0.46 | 0.00 | 0.30 | 0.00 | 1.00 | 0.301 |
| same, coldest days instead of highest excitation | 0.613 | 0.67 | 0.30 | 0.00 | 0.10 | 1.00 | 0.88 | 0.391 |
| same, one day instead of nine | 0.250 | 0.50 | 0.17 | 0.00 | 0.20 | 1.00 | 0.62 | 0.239 |
| same, severity grid of 0.05 instead of 0.01 | 0.721 | 0.83 | 0.42 | 0.00 | 0.10 | 1.00 | 1.00 | 0.691 |
| temperature-extrapolated absolute frequencies, never declining (baseline) | 0.000 | 0.33 | 0.00 | 1.00 | 0.80 | 0.00 | 1.00 | 0.000 |
| declining everything | 0.000 | — | — | 0.00 | 0.00 | 1.00 | 0.00 | 0.000 |
| never claiming damage | 0.000 | — | — | 0.00 | 0.00 | 0.00 | 1.00 | 0.000 |

The ladder is not a difficulty measurement; that is the frontier draw below. What it shows is where
the score lives: the campaign baseline is worth 0.19, the ratio insight 0.32, the refusal 0.25, the
budget 0.48, and the day choice 0.12.

## Shortcut probe

The question this repository learned to ask after a submitted task turned out to be solvable by a
two-parameter grid search: **how far does a low-dimensional strategy get without the science?**

2812 strategies of the form "average the shift over the highest-excitation days, declare healthy
below a threshold, decline above a second threshold, otherwise name the mode with the largest
deviation as the element and set the severity from the shift" were evaluated:

| family | strategies | best score |
|---|---|---|
| without the ratio insight, on temperature-extrapolated absolute frequencies | 1406 | **0.382** |
| with the ratio insight, but no family search | 1406 | 0.259 |
| reference | — | 0.733 |
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
