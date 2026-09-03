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
| mechanism score (normalized) | **0.445** | 0.358 |
| edge F1 (coupled networks) | 0.22 | 0.23 |
| false edge rate | 0.47 | - |
| false discovery rate (hidden-unit networks) | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |
| discovery coverage | 0.57 | - |
| experiments | 8 of 8 | 10 of 10 |

Its design: eight drives, each unit joining about half of them with a random sign at 0.7 of the
amplitude bound; for every unit an orthogonal matching pursuit on `tanh` of the other units with
the unit's own drive always in the model and a BIC stop; edges where the coefficient exceeds 0.15;
and a refusal when three or more units leave a sparse-fit residual above three times the noise
floor.

**The reference is deliberately not at the ceiling.** Its coverage is 0.57: it declines three of
the five coupled development networks it should have solved, because its noise-floor test cannot
tell a hard sparse fit from a weakly coupled hidden unit. A design that keeps clean regressions
*and* excites hidden paths, or a sharper refusal test, is the headroom.

**This task was hardened after its first frontier draw.** At fourteen experiments for twelve units
and in-degree three, Claude Opus 5's first proposal scored 0.665 against a reference of 0.631 -
above the admission bar the task was built under. The response was the world, not the reference:
eight experiments, in-degree four, and one weakly coupled hidden unit instead of two. The numbers
in this file are the hardened world; the draw that failed the bar is recorded in the card and in
`experiments/opus5_hidden_coupling_network_calibration_2026-09-03.json`.

## Baseline - `solution.py`

Random drives, dense minimum-norm least squares on the raw states, threshold at 0.1, never declines.

| metric | value |
|---|---|
| combined score | **0.0000** |
| edge F1 | 0.39 |
| false edge rate | 0.77 |
| false discovery rate | 1.00 |

Confidently wrong rather than empty: the underdetermined fit smears every coupling over many
units, and every hidden-unit network is published as a direct graph.

## Difficulty ladder

| strategy | score | edge F1 | false edges | false discovery | refusal | coverage | held out |
|---|---|---|---|---|---|---|---|
| Rademacher design + OMP/BIC on tanh(x) + noise-floor refusal | 0.445 | 0.22 | 0.47 | 0.00 | 1.00 | 0.57 | 0.358 |
| same, never declining | 0.258 | 0.56 | 0.45 | 1.00 | 0.00 | 1.00 | 0.224 |
| same, regressing on x instead of tanh(x) | 0.303 | 0.22 | 0.47 | 0.33 | 0.67 | 0.57 | 0.200 |
| same regression, single-unit drives | 0.227 | 0.72 | 0.25 | 1.00 | 0.00 | 1.00 | 0.000 |
| dense least squares on the raw states, never declining | 0.000 | 0.39 | 0.77 | 1.00 | 0.00 | 1.00 | 0.000 |
| declining everything | 0.000 | - | 0.00 | 0.00 | 1.00 | 0.00 | 0.000 |
| empty graph everywhere | 0.000 | - | 0.00 | 1.00 | 0.00 | 1.00 | 0.000 |

The ladder is not a difficulty measurement; difficulty is measured by a frontier-model draw. What
the ladder shows is where the score lives: single-unit drives give the cleanest regressions (F1
0.72) and never see the hidden unit, so every hidden world is published and the total is worse than
declining; the multi-unit design refuses every hidden world and pays with an F1 of 0.22.

## Robustness

- Twelve malformed candidate shapes - raising, `None`, a string, a two-element edge, a self-loop,
  a fractional sign, an out-of-range endpoint, a duplicated pair, a NaN confidence, overspending
  the budget, an out-of-bound drive and a wrong-length drive - all score zero with `valid = 0`,
  and none raises out of the evaluator.
- Two consecutive evaluations of the reference are key-identical.
- Declining every network scores exactly 0.0 by construction of the normalisation; so does the
  empty graph everywhere.
