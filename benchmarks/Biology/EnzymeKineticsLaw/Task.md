# EnzymeKineticsLaw

## The question

A purified enzyme is in front of you. Which rate law does it obey, and with what constants -
or does it obey none of the published ones?

You are given a budgeted assay and nothing else. Each call measures one initial velocity at a
substrate and inhibitor concentration you choose. You decide where to spend the budget, then
report a law and its parameters, or decline.

## Why one titration is not enough

Six laws are in the published family. Three of them - `competitive`, `uncompetitive` and
`noncompetitive` inhibition - are **indistinguishable from a substrate titration alone**: held at
one inhibitor concentration, all three are saturating hyperbolae and fit each other's data. They
separate only when substrate is titrated at two or more inhibitor levels, because the apparent
Km and Vmax then move in mode-specific directions:

| law | apparent Km as inhibitor rises | apparent Vmax as inhibitor rises |
|---|---|---|
| `competitive` | rises | unchanged |
| `uncompetitive` | falls | falls |
| `noncompetitive` | unchanged | falls |

Designing that experiment is the content of this task.

## Two worlds carry no law at all

Some enzymes on this task obey nothing in the family, and the right answer is to decline:

- **a dead enzyme** - velocity does not depend on substrate; there is no catalysis to characterise.
- **an enzyme outside the family** - it does turn over substrate, and one of the six will fit it
  tolerably, but the fit is a mechanism that is not there.

The second kind is the sharp one. One of its shapes is a cooperative enzyme that is *also*
competitively inhibited. The family carries cooperativity and competitive inhibition as separate
laws and no member carries both, so nothing in it is correct - but at zero inhibitor this **is**
a Hill curve and fits one to about 0.9 sigma. A candidate that titrates substrate once reports
`hill` with high confidence and books a false discovery. The same candidate, having also titrated
the inhibitor, finds the best law in the family off by 13 sigma and declines correctly.

So on that world the difference between a false discovery and a correct refusal is exactly
whether the inhibitor was varied.

## What you implement

```python
def discover_kinetics(problem, assay):
    ...
    return {"law": ..., "parameters": {...}, "confidence": ..., "abstain": False}
```

### `problem` - every key you are given

| key | meaning |
|---|---|
| `assay_budget_calls` | how many times `assay` may be called on this enzyme (28) |
| `substrate_bounds_um` | `[0.0, 500.0]`; substrate concentrations must lie inside |
| `inhibitor_bounds_um` | `[0.0, 60.0]`; inhibitor concentrations must lie inside |
| `candidate_laws` | the six law names you may report |
| `required_parameters` | per law, the parameter names your `parameters` must carry |
| `velocity_units` | `umol_per_min_per_mg` |
| `noise_sigma_hint` | additive Gaussian, sigma between 0.008 and 0.012 in velocity units |
| `abstain_when` | the enzyme obeys no law in `candidate_laws` |

### `assay(substrate_um, inhibitor_um=0.0)`

Returns one noisy initial velocity. `inhibitor_um` defaults to zero. Concentrations must be
finite and non-negative or the call raises. Calling past the budget raises and the world scores
zero, so count your calls.

Repeating the same query at the same point in a run returns the same number: noise is seeded by
the world and the call index. Averaging replicates works and costs budget, which is a real trade
against a third inhibitor level.

### What you return

| key | meaning |
|---|---|
| `law` | one of `candidate_laws`; omit when abstaining |
| `parameters` | the names `required_parameters[law]` lists, all finite |
| `confidence` | in `[0, 1]`; clipped |
| `abstain` | `True` to decline this enzyme |

The six laws, with `s` substrate and `i` inhibitor:

```
michaelis_menten      v = vmax*s / (km + s)                        vmax, km
hill                  v = vmax*s^n / (km^n + s^n)                  vmax, km, hill_n
substrate_inhibition  v = vmax*s / (km + s + s^2/ki)               vmax, km, ki
competitive           v = vmax*s / (km*(1 + i/ki) + s)             vmax, km, ki
uncompetitive         v = vmax*s / (km + s*(1 + i/ki))             vmax, km, ki
noncompetitive        v = vmax*s / ((km + s)*(1 + i/ki))           vmax, km, ki
```

Anything malformed - a law outside the list, a missing or non-finite parameter, a raise - scores
that enzyme zero. It is never an infrastructure failure.

## How you are scored

Each enzyme contributes a mechanism score:

- **a law is there**: you must name the right one **and** your constants must reproduce
  velocities on a sealed grid you never measured. A right name with wrong constants scores low; a
  wrong name scores zero however well it fits the points you took.
- **no law is there**: declining scores 1, claiming a law scores 0.

`combined_score` is the mean of those, renormalised so that **declining every enzyme scores
exactly 0.0**. Refusal is not free: it is worth something only where it is right.

Reported separately, never averaged into one number, because one scalar cannot say whether a
claimed mechanism was right:

`law_identification_rate` · `prediction_score` · `false_discovery_rate` ·
`correct_refusal_rate` · `discovery_coverage` (was a discovery attempted at all) ·
`extrapolation_score` (does the claimed law still hold eight times outside the range you
measured) · `confidence_calibration`

Two very different failures both score 0.0 and the axes are what tell them apart: declining
everything has false-discovery 0.00 and coverage 0.00, while claiming a law everywhere has
false-discovery 1.00 and coverage 1.00.

A sealed held-out split of eight further enzymes, with different seeds, different noise and both
misspecified shapes, is scored too and is not visible to a searcher.

## What each competence is worth

Ablating the reference - same fitting code, same refusal tests, only the design changed:

| design | score | law id | false discovery | correct refusal |
|---|---|---|---|---|
| 3 inhibitor levels, both refusal tests | **0.990** | 1.00 | 0.00 | 1.00 |
| 2 inhibitor levels | 0.986 | 1.00 | 0.00 | 1.00 |
| 1 inhibitor level (substrate only) | 0.315 | 0.50 | 0.33 | 0.67 |
| 3 levels, never declining | 0.490 | 1.00 | 1.00 | 0.00 |
| 1 level, never declining | 0.000 | 0.50 | 1.00 | 0.00 |

Varying the inhibitor is worth about +0.67, knowing when to decline about +0.50, and the two are
close to independent.
