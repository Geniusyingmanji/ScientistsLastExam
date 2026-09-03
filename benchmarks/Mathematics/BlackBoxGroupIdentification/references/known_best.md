# BlackBoxGroupIdentification - reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_cayley_closure.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_cayley_closure.py`

Truth-blind: it reads only the public problem (including the catalogue constructions) and the
charged oracle.

| metric | development | held out |
|---|---|---|
| mechanism score (normalized) | **0.857** | 1.000 |
| identification rate | 1.00 | 1.00 |
| false discovery rate | 0.10 | 0.00 |
| correct refusal rate | 0.75 | 1.00 |
| refusal reason right | 0.75 | 1.00 |
| queries | 90 of 96-192 | 107 of 144-288 |

Its design: the powers of one random element until they cycle, which yields the identity;
left-multiplication closure over generators drawn at random from the unreached labels; the whole
table reconstructed from generator words; up to 24 prediction checks with what remains of the
budget, any disagreement declaring the operation not a group; and identification by element-order
profile plus centre size against tables built from the catalogue constructions, declining as
outside the catalogue when nothing matches.

**The reference is deliberately not at the ceiling.** It names the unlisted group `C4:C4` as the
catalogue entry `C2xQ8`: the two share their order profile and centre size and differ in the
number of distinct squares. Adding that invariant (or the derived subgroup order) takes the same
pipeline to 1.000. This is the admission bar recorded in the card: a first model proposal that
reaches the reference means the task needs hardening before it is anything more than an on-ramp.

## Baseline - `solution.py`

Sampled element orders until the budget runs out, nearest catalogue entry by order profile, never
declines.

| metric | value |
|---|---|
| combined score | **0.0000** |
| identification rate | 0.50 |
| false discovery rate | 0.70 |

Confidently wrong rather than empty: every non-group and every unlisted group is given a name.

## Difficulty ladder

| strategy | score | identification | false discovery | refusal | reason right | held out |
|---|---|---|---|---|---|---|
| identity + Cayley closure + reconstruction + prediction checks + order profile & centre | 0.857 | 1.00 | 0.10 | 0.75 | 0.75 | 1.000 |
| same, invariants extended by the derived subgroup order and the number of squares | 1.000 | 1.00 | 0.00 | 1.00 | 1.00 | 1.000 |
| same, naming the nearest catalogue entry instead of declining | 0.714 | 1.00 | 0.20 | 0.50 | 0.50 | 0.600 |
| sampled order profile, nearest entry, never declining | 0.000 | 0.50 | 0.70 | 0.00 | 0.00 | 0.200 |
| declining everything, either reason | 0.000 | 0.00 | 0.00 | 1.00 | 0.50 | 0.000 |

The ladder is not a difficulty measurement; difficulty is measured by a frontier-model draw, which
has not been run yet. Prediction checks did not change the reference's score on these worlds: the
reconstructed table of a non-group already fails the Latin-square check on its columns, so the
refusal is earned by reconstruction itself and the checks are insurance.

## Robustness

- Eleven malformed candidate shapes - raising, `None`, a string, an identifier not in the
  catalogue, an identifier from another order's catalogue, a decline without a reason, an invalid
  reason, a NaN confidence, overspending the budget, an out-of-range label and a boolean label -
  all score zero with `valid = 0`, and none raises out of the evaluator.
- Two consecutive evaluations of the reference are key-identical.
- Declining every world with either reason scores exactly 0.0 by construction of the normalisation.
- `tests/test_black_box_group_identification.py` rebuilds every catalogue and outside construction,
  checks each is a group of the stated order, and checks the scoring invariants are pairwise
  distinct within an order and between outside groups and the catalogue.
