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
| mechanism score (normalized) | **0.286** | 0.400 |
| identification rate | 0.50 | 0.50 |
| false discovery rate | 0.50 | 0.25 |
| correct refusal rate | 0.50 | 0.75 |
| refusal reason right | 0.50 | 0.75 |
| queries | 52 of 40-80 | 84 of 60-120 |

Its design: the powers of one random element until they cycle, which yields the identity and one
element order; an attempted left-multiplication closure over generators drawn from the unreached
labels, abandoned when the remaining budget cannot cover the elements still missing; exact
invariant matching when the closure completes; and otherwise a rank lower bound (the generators
already consumed), the order of the proper subgroup reached, the element orders measured, and a
commutation-based centre estimate, pruning catalogue tables built offline from their constructions.

**The reference is deliberately not at the ceiling.** It identifies the two-generated worlds, where
`2 * order` queries buy the table, and loses the three-generated ones and both unlisted groups,
because by then only a handful of queries remain for the centre - the one invariant that separates
what rank and the order profile leave standing. Pricing the closure before committing to it, and
spending the savings on the pairs that separate the surviving entries, is the headroom.

## Model draws - Claude Opus 5

Three seeds, three proposals each, greedy_rewrite, normal feedback, budget 3.

**First draw, original budget of 6 * order**
(`experiments/opus5_black_box_group_identification_calibration_2026-09-03.json`, reference 0.857):
every seed scored **1.000 on its first proposal**. At that budget the whole Cayley table is
affordable and a real isomorphism test wins every world, so the task measured nothing about
budgeted identification. This is the clearest saturation this repository has recorded.

**Second draw, budget cut to 2.5 * order**
(`experiments/opus5_black_box_group_identification_calibration_2026-09-03_v2.json`, reference
0.286):

| seed | proposal 1 | proposal 2 | proposal 3 | best |
|---|---|---|---|---|
| 0 | 0.143 | 0.000 | 0.286 | 0.286 |
| 1 | **0.429** | 0.214 | 0.286 | 0.429 |
| 2 | 0.000 | 0.000 | 0.429 | 0.429 |

From 1.000 to a best of 0.429 against a ceiling of 1.0. Seed 1's first proposal clears the
reference, so the construction-time bar still fails on one seed of three, and that is recorded
rather than hardened away: the scale is anchored at blanket refusal (0.0) and exact identification
with correct refusal reasons (1.0), and the reference is a runnable witness rather than the
normaliser.

## Baseline - `solution.py`

Sampled element orders until the budget runs out, nearest catalogue entry by order profile, never
declines.

| metric | value |
|---|---|
| combined score | **0.0000** |
| identification rate | 0.00 |
| false discovery rate | 1.00 |

Confidently wrong rather than empty: every non-group and every unlisted group is given a name.

## Difficulty ladder

| strategy | score | identification | false discovery | refusal | reason right | held out |
|---|---|---|---|---|---|---|
| attempted closure, exact match when it finishes, rank + subgroup + centre when it does not | 0.286 | 0.50 | 0.50 | 0.50 | 0.50 | 0.400 |
| sampled order profile, nearest entry, never declining (baseline) | 0.000 | 0.00 | 1.00 | 0.00 | 0.00 | 0.000 |
| declining everything, either reason | 0.000 | 0.00 | 0.00 | 1.00 | 0.50 | 0.000 |

The ladder is not a difficulty measurement; difficulty is measured by the frontier-model draws
above. What the budget cut changed is which route is available: at `6 * order` the table is
affordable and the answer follows from it, and at `2.5 * order` the table is a bet that pays on a
two-generated world and loses on any other.

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
