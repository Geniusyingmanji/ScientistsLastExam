# DiscrepantMeasurements - reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_synthesis.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_synthesis.py`

Truth-blind: it reads only the published table and the budgeted split test.

| metric | development | held out |
|---|---|---|
| mechanism score (normalized) | **0.8421** | 0.9361 |
| diagnosis rate | 1.00 | 1.00 |
| culprit identification | 1.00 | 1.00 |
| accuracy | 0.906 | - |
| uncertainty calibration | 0.981 | - |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |
| split tests used | 5.0 of 5 | 5.0 of 5 |

All sixteen diagnoses are right. The shortfall from 1.0 is the irreducible distance between a
best value and the truth: eight measurements of finite precision do not locate a constant exactly,
and the accuracy axis is scored against that distance rather than against the diagnosis.

## Baseline - `solution.py`

The inverse-variance weighted mean of the published table, declared consistent. It buys no split
test and never declines.

| metric | value |
|---|---|
| combined score | **0.0000** |
| diagnosis rate | 0.25 |
| false discovery rate | 1.00 |
| discovery coverage | 1.00 |

Confidently wrong rather than empty: it publishes a world average on every body of evidence,
including the two where two methods disagree and no single number is defensible. Declining
everything also scores 0.0000, with false discovery 0.00 and coverage 0.00 - the same scalar
reached from the opposite direction, which is why the axes are reported separately.

## Difficulty ladder

Ablations of the reference. The thresholds and the arithmetic are held fixed; only the choice of
which splits to buy, and whether to decline, changes.

| strategy | score | diagnosis | culprit | false discovery | correct refusal | held out |
|---|---|---|---|---|---|---|
| both ends of the deviation ordering | 0.8421 | 1.00 | 1.00 | 0.00 | 1.00 | 0.9361 |
| the most deviant groups only | 0.7008 | 0.88 | 0.50 | 0.00 | 1.00 | 0.9361 |
| the most typical groups only | 0.5855 | 0.75 | 0.00 | 0.00 | 1.00 | 0.6320 |
| no splits at all - the table only | 0.4251 | 0.62 | 0.00 | 0.00 | 1.00 | 0.6320 |
| both ends, never declining | 0.5088 | 0.75 | 1.00 | 1.00 | 0.00 | 0.6028 |
| declining everything | 0.0000 | 0.00 | 0.00 | 0.00 | 1.00 | 0.0000 |

Buying splits at all is worth +0.42. Buying at both ends rather than only the deviant tail is
worth a further +0.14 and takes culprit identification from 0.50 to 1.00. Declining where it is
right is worth +0.33.

## Model draw - Claude Opus 5, 2026-09-02

`experiments/opus5_discrepant_measurements_calibration_2026-09-02.json`, three seeds, three
proposals each, greedy_rewrite, normal feedback.

| seed | baseline | proposal 1 | proposal 2 | proposal 3 | split tests used |
|---|---|---|---|---|---|
| 0 | 0.0000 | 0.6817 | 0.5267 | 0.6817 | 3.8 of 5 |
| 1 | 0.0000 | 0.6817 | **0.8421** | 0.8421 | 5.0 of 5 |
| 2 | 0.0000 | **0.8421** | 0.8421 | 0.8421 | 5.0 of 5 |

Read carefully, because the two halves of this say different things.

Two of three seeds reach the reference, one of them on the first proposal, and **no proposal
exceeded it**. The reference's 0.8421 is close to the ceiling this scoring admits - the shortfall
from 1.0 is the distance between a best value and the truth, not a missed defect - so reaching
0.8421 is reaching the top. On that reading the task is at its ceiling for the current frontier,
as `EnzymeKineticsLaw` is.

Seed 0 is the part worth keeping. It never gets there across three proposals, and the reason is
legible in the axes: it spends 3.8 of its 5 split tests and its diagnosis rate stops at 0.88. It
is not buying the interrogation the diagnosis needs. Seed 1 shows the opposite - 0.6817 on the
first proposal, 0.8421 on the second, with the split count going 5.0 - which is an iteration
actually paying for itself rather than a first draft that happened to be right.

So this task is a harder on-ramp than `EnzymeKineticsLaw` and it does carry a real
proposal-to-proposal signal, but it is not frontier evidence either. Raising its ceiling means
raising what a *correct* procedure can reach, which the accuracy axis currently caps.

## Why the published table is not enough

Chi-square per degree of freedom, 5th to 95th percentile over 200 seeds per kind:

| world | chi-square / dof | largest deviation, sigma |
|---|---|---|
| consistent | 0.36 - 1.89 | 0.99 - 2.69 |
| underestimated | 2.24 - 11.80 | 2.48 - 6.72 |
| outlier | 1.78 - 5.66 | 2.92 - 6.11 |
| two_populations | 3.90 - 10.22 | 3.01 - 5.56 |

The three defective kinds overlap each other, and the mild end of an outlier world reaches into
the range a sound table occupies. What separates them is bought, not read:

| world | largest split z | median split z | method separation z |
|---|---|---|---|
| consistent | 1.8 | 0.7 | 0.8 |
| underestimated | 4.5 | 1.7 | 2.0 |
| outlier | 4.5 | 0.8 | 1.5 |
| two_populations | 1.8 | 0.7 | 6.5 |

`underestimated` and `outlier` have the same largest split z. Only the median separates them,
which is why more than one group has to be interrogated, and why the split budget is smaller than
the table.

## A modelling error this went through

The first version displaced an outlier group symmetrically about the truth, minus delta/2 on one
half and plus delta/2 on the other. The drift then cancels in the published mean: those worlds had
perfectly sound central values and their only defect was one noisy split. Measured, they sat at
chi-square 0.37-1.75 against a sound table's 0.36-1.89 - indistinguishable, because there was
nothing to distinguish. The halves now carry the correct calibration and the drifted one, so the
published mean is displaced by half the drift, and the displacement and the split signal are the
same fact.

## Robustness

- Eleven malformed candidate shapes - raising, empty, `None`, a string, an unknown diagnosis,
  non-finite values, a non-positive uncertainty, an out-of-range culprit, a missing best value,
  overspending the budget, and an out-of-range group index - all score zero with `valid = 0`, and
  none raises out of the evaluator.
- Two consecutive evaluations of the reference are key-identical.
- Declining every world scores exactly 0.0 by construction of the normalisation.
