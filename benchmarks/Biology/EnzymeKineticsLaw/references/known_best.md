# EnzymeKineticsLaw - reference results

Every number here is produced by running code in this directory. Nothing is copied from a table.

## Reproducing

```
python3 -c "
import importlib.util, sys
sys.path.insert(0, 'verification')
def load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
ev  = load('ev',  'verification/evaluator.py')
ref = load('ref', 'verification/reference_kinetics.py')
print(ev.evaluate(ref.discover_kinetics)['combined_score'])
"
```

## Reference - `verification/reference_kinetics.py`

Truth-blind: it reads only the public problem and the budgeted assay.

| metric | development | held out |
|---|---|---|
| mechanism score (normalized) | **0.9904** | 0.9847 |
| law identification rate | 1.00 | 1.00 |
| sealed-grid prediction | 0.9904 | - |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |
| discovery coverage | 1.00 | 1.00 |
| extrapolation score | 0.977 | 0.972 |
| confidence calibration | 0.9151 | - |
| mean assay calls | 24.0 of 28 | 24.0 of 28 |

Its design is three substrate titrations of eight geometrically spaced points, at inhibitor 0,
0.35 and 0.85 of the declared maximum; BIC over the six laws rather than lowest residual; and two
separate refusal tests, one for no substrate dependence and one for model inadequacy.

## Baseline - `solution.py`

One substrate titration at zero inhibitor, always reporting Michaelis-Menten.

| metric | value |
|---|---|
| combined score | **0.0000** |
| false discovery rate | 1.00 |
| discovery coverage | 1.00 |

It is a *confidently wrong* baseline rather than an empty one: it claims a mechanism on every
world including the three that have none. Blanket abstention also scores 0.0000, with false
discovery 0.00 and coverage 0.00 - the same scalar reached from the opposite direction, which is
why the axes are reported separately.

## Difficulty ladder

Ablations of the reference: the fitting code and the refusal tests are held fixed and only the
experiment design changes.

| design | score | law id | false discovery | correct refusal | held out |
|---|---|---|---|---|---|
| 3 inhibitor levels, both refusal tests | 0.9904 | 1.00 | 0.00 | 1.00 | 0.9847 |
| 2 inhibitor levels | 0.9860 | 1.00 | 0.00 | 1.00 | 0.9828 |
| 1 inhibitor level (substrate only) | 0.3150 | 0.50 | 0.33 | 0.67 | 0.1817 |
| 3 levels, never declining | 0.4904 | 1.00 | 1.00 | 0.00 | 0.3847 |
| 1 level, never declining | 0.0000 | 0.50 | 1.00 | 0.00 | 0.0000 |

Varying the inhibitor is worth about +0.67 and knowing when to decline about +0.50.

The reference scoring 0.99 is not a saturation warning here: it is what a correct experiment plus
a correct model-selection rule earns, and the ladder shows the score collapses to 0.315 when the
design is wrong. The open question is where a model draw lands on that ladder, and until one is
run this task stays a candidate.

## Separation the refusal tests rely on

Best-fitting law residual, in units of the world's noise sigma, on the reference's design:

| world | residual / sigma |
|---|---|
| in-library (all eleven) | 0.79 - 1.11 |
| out of family, two-site | 7.8 - 8.3 |
| out of family, cooperative and inhibited | 8.5 - 12.7 |

The model-inadequacy threshold sits at 2.4 sigma, between the two.

For the dead enzyme the statistic is the velocity range rather than the residual, measured
against the expected range of pure noise, which grows like `sqrt(2 ln n)`:

| world | range / sigma |
|---|---|
| dead enzyme | 3.6 - 4.5 |
| weakest real law (substrate inhibition) | 21.9 |

An earlier version compared high-substrate against low-substrate velocity instead. A
substrate-inhibited enzyme rises and then falls, so its endpoints nearly coincide, and that
statistic put a real law at 4.7 sigma against a 4.0 sigma threshold - a 17% margin between
catalysis and a dead enzyme. The range sees the peak and puts the same world at 37 sigma.

## Robustness

- Nine malformed candidate shapes - raising, empty, `None`, a string, an unknown law, non-finite
  parameters, missing parameters, a negative concentration, and overspending the budget - all
  score zero with `valid = 0`, and none raises out of the evaluator.
- Two consecutive evaluations of the reference are key-identical.
- Declining every world scores exactly 0.0 by construction of the normalisation.
