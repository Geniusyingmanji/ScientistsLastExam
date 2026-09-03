# HiddenCouplingNetwork - reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_sparse_regression.py \
    --metrics-out /tmp/metrics.json
```

## Reference - `verification/reference_sparse_regression.py`

Truth-blind: it reads only the public problem and the budgeted laboratory.

| metric | development | held out |
|---|---|---|
| mechanism score (normalized) | **0.631** | 0.589 |
| edge F1 (coupled networks) | 0.48 | 0.49 |
| false edge rate | 0.20 | 0.03 |
| false discovery rate (hidden-unit networks) | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |
| discovery coverage | 0.71 | - |
| experiments | 10 of 10 | 13 of 13 |

Its design: ten drives, each unit joining about half of them with a random sign at 0.7 of the
amplitude bound; for every unit an orthogonal matching pursuit on `tanh` of the other units with
the unit's own drive always in the model and a BIC stop; edges where the coefficient exceeds 0.15;
and a refusal when two or more units leave a sparse-fit residual above four times the noise floor.

**The reference is deliberately not at the ceiling.** It declines two of the five coupled
development networks it should have solved - its noise-floor test cannot tell a hard sparse fit
from a hidden unit - and its multi-unit design regresses worse than single-unit drives do. A
design that keeps clean regressions *and* excites hidden paths, or a sharper refusal test, is the
headroom a better searcher is supposed to claim. This is the admission bar recorded in the card: a
first model proposal that reaches the reference means the task needs hardening before it is
anything more than an on-ramp.

## Baseline - `solution.py`

Random drives, dense minimum-norm least squares on the raw states, threshold at 0.1, never declines.

| metric | value |
|---|---|
| combined score | **0.0000** |
| edge F1 | 0.50 |
| false edge rate | 0.69 |
| false discovery rate | 1.00 |

Confidently wrong rather than empty: the underdetermined fit smears every coupling over many
units, and every hidden-unit network is published as a direct graph.

## Difficulty ladder

| strategy | score | edge F1 | false edges | false discovery | refusal | held out |
|---|---|---|---|---|---|---|
| Rademacher design + OMP/BIC on tanh(x) + noise-floor refusal | 0.631 | 0.48 | 0.20 | 0.00 | 1.00 | 0.589 |
| same, never declining | 0.445 | 0.82 | 0.18 | 1.00 | 0.00 | 0.309 |
| same, regressing on x instead of tanh(x) | 0.393 | 0.35 | 0.10 | 0.33 | 0.67 | 0.389 |
| same regression, single-unit drives | 0.476 | 0.87 | 0.15 | 1.00 | 0.00 | 0.335 |
| declining everything | 0.000 | - | 0.00 | 0.00 | 1.00 | 0.000 |
| empty graph everywhere | 0.000 | - | 0.00 | 1.00 | 0.00 | 0.000 |

The ladder is not a difficulty measurement; difficulty is measured by a frontier-model draw, which
has not been run yet. What the ladder shows is where the score lives: the design trade-off between
clean per-unit regressions (single-unit drives, F1 0.87, no hidden-unit detection) and hidden-path
excitation (multi-unit drives, every hidden unit refused, F1 0.48).

## Robustness

- Twelve malformed candidate shapes - raising, `None`, a string, a two-element edge, a self-loop,
  a fractional sign, an out-of-range endpoint, a duplicated pair, a NaN confidence, overspending
  the budget, an out-of-bound drive and a wrong-length drive - all score zero with `valid = 0`,
  and none raises out of the evaluator.
- Two consecutive evaluations of the reference are key-identical.
- Declining every network scores exactly 0.0 by construction of the normalisation; so does the
  empty graph everywhere.
