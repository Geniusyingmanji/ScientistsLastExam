# DiscrepantMeasurements

## The question

Eight groups have measured the same physical constant. Each publishes a value and a one-sigma
uncertainty. The values do not agree as well as those uncertainties say they should.

What is wrong with this body of evidence, and what is the best value - or is there no best value?

## Four things can be wrong, and the table cannot tell you which

| diagnosis | what it means | the right answer |
|---|---|---|
| `consistent` | nothing is wrong; the scatter matches the quoted errors | the weighted mean, with its usual uncertainty |
| `underestimated` | every group's error bar is too small by a common factor | the same weighted mean, with an inflated uncertainty |
| `outlier` | one group carries an unquoted systematic | name it, drop it, average the rest |
| `two_populations` | two methods disagree by more than either can explain | decline: no single value is defensible |

The last three produce scatter that looks the same from the published table. Measured on this
task's own worlds, chi-square per degree of freedom runs 2.2-11.8 when the errors are understated,
1.8-5.7 when one group is displaced, and 3.9-10.2 when the methods disagree. A sound table runs
0.4-1.9, which the mild end of an outlier world sits inside.

## The split test

You may ask a group to report its value separately on the two halves of its data. A group whose
calibration drifted during its run has halves that disagree; a sound group's halves agree to
their own statistics. This is what separates the four cases:

| diagnosis | split tests |
|---|---|
| `consistent` | every split clean |
| `underestimated` | every split inconsistent - the understatement is inside every group |
| `outlier` | exactly one split inconsistent |
| `two_populations` | every split clean - the disagreement is *between* methods, not inside any group |

You have **five** splits and there are eight groups, so you choose whom to interrogate. Spending
all five on the most deviant groups finds a single displaced group but cannot distinguish it from
a table that understates everywhere, because both make the deviant tail split badly. Spending
them all on typical groups shows whether the understatement is global but can miss the one group
carrying it. The diagnosis needs both ends.

Splitting the same group twice returns the same numbers. The halves are a property of the group's
data, not a fresh experiment.

## What you implement

```python
def synthesize_evidence(problem, split_test):
    ...
    return {"best_value": ..., "uncertainty": ..., "diagnosis": ...,
            "culprit_index": ..., "confidence": ..., "abstain": False}
```

### `problem` - every key you are given

| key | meaning |
|---|---|
| `measurements` | the published table: one entry per group with `group_index`, `value`, `quoted_sigma`, `method` |
| `split_test_budget` | how many splits you may buy on this body of evidence (5) |
| `group_count` | how many groups published (8) |
| `candidate_diagnoses` | the four diagnosis names you may report |
| `diagnosis_meanings` | one line per diagnosis, saying what it asserts |
| `abstain_when` | no single best value is defensible for this body of evidence |

### `split_test(group_index)`

Returns `{"group_index", "first_half_value", "second_half_value", "half_quoted_sigma"}`. The half
sigma is the group's own quoted uncertainty scaled for half the data - when a group understates,
its half sigma understates in exactly the same way, which is what lets the split reveal it.

An index outside `[0, 8)` raises. Spending past the budget raises and the world scores zero.

### What you return

| key | meaning |
|---|---|
| `best_value` | your best estimate; omit when abstaining |
| `uncertainty` | an honest one-sigma on it, strictly positive; omit when abstaining |
| `diagnosis` | one of `candidate_diagnoses`, or null |
| `culprit_index` | required when your diagnosis is `outlier`: which group carries the systematic |
| `confidence` | in `[0, 1]`; clipped |
| `abstain` | `True` to decline to give a single value |

Anything malformed - an unknown diagnosis, a non-positive uncertainty, a non-finite value, a
raise - scores that world zero. It is never an infrastructure failure.

## How you are scored

Each body of evidence contributes a mechanism score:

- **a best value exists**: you must name the right diagnosis - and, for `outlier`, the right group
  - **and** your best value must survive comparison with the truth. A right diagnosis with a value
  that has not been corrected scores low; a wrong diagnosis scores zero however close the value.
- **no best value exists**: declining scores 1, publishing a world average scores 0.

`combined_score` is the mean of those, renormalised so that **declining every world scores exactly
0.0**.

Reported separately, never averaged into one number:

`diagnosis_rate` · `accuracy_score` · `calibration_score` (is the quoted uncertainty honest -
inflating it threefold to make your pull look good is penalised the same as understating it
threefold) · `culprit_rate` · `false_discovery_rate` · `correct_refusal_rate` ·
`discovery_coverage` · `confidence_calibration`

A sealed held-out set of eight further bodies of evidence, with different seeds and different
severities, is scored too and is not visible to a searcher.

## What each competence is worth

Ablating the reference - same thresholds, same arithmetic, only the choice of which splits to buy
and whether to decline:

| strategy | score | diagnosis | culprit found | false discovery | correct refusal |
|---|---|---|---|---|---|
| both ends of the deviation ordering, declines | **0.842** | 1.00 | 1.00 | 0.00 | 1.00 |
| the most deviant groups only | 0.701 | 0.88 | 0.50 | 0.00 | 1.00 |
| the most typical groups only | 0.586 | 0.75 | 0.00 | 0.00 | 1.00 |
| no splits at all - the table only | 0.425 | 0.62 | 0.00 | 0.00 | 1.00 |
| both ends, never declining | 0.509 | 0.75 | 1.00 | 1.00 | 0.00 |
| declining everything | 0.000 | 0.00 | 0.00 | 0.00 | 1.00 |

Buying splits at all is worth +0.42. Buying at *both ends* rather than only the deviant tail is
worth a further +0.14, and takes the culprit rate from 0.50 to 1.00. Declining where it is right
is worth +0.33.

## Rules

- Only edit `solution.py`; keep `synthesize_evidence(problem, split_test)`.
- `sle.contract_lint` is importable and free to call for shape checks. It costs no oracle call.
- Do not read `verification/` or `frontier_eval/`.
