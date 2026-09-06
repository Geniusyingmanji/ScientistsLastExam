# WallClosureDiscovery — find the closure, or say the data cannot pin one

## Scientific setting

A turbulence closure turns the unknown Reynolds stress into a function of the mean flow. Fitting
one to data is among the most worked-on problems in engineering fluid mechanics, and its standing
criticism is not that the fits are bad. It is that they are **validated where they were trained**
(Duraisamy, Iaccarino & Xiao, *Annu. Rev. Fluid Mech.* **51** (2019) 357).

So this task does not only ask for a law. It asks whether a searcher knows when the flows it has
seen cannot support one.

## The world

In wall units the total shear in a fully developed channel is exactly linear, so a mixing length
`l+(y+)` fixes the mean profile through

```
l+^2 (dU+/dy+)^2 + dU+/dy+ - tau+ = 0,     tau+ = 1 - y+/Re_tau
```

and one quadrature. That is the whole solver — no model beyond the closure being tested.

Each profile you are given carries what a real profile measurement carries: an unknown wall
position and an unknown friction-velocity calibration, both constant across the profile. They do
not average away, and a fit that ignores them puts them into the parameter it is estimating.
Measured on this world: a fit that ignores the nuisances returns `kappa = 0.501` against a truth of
`0.410`, twenty-two per cent high.

## Three regimes, one answerable

| regime | what happened | correct answer |
|---|---|---|
| `recoverable` | one closure, and the sampled Reynolds numbers span enough to pin both parameters | submit the formula |
| `degenerate_parameters` | one closure, but the span is too narrow to separate `kappa` from `A+`; a whole interval fits, and its members disagree where it counts | abstain |
| `inconsistent` | no single closure generated the profiles | abstain |

The two refusal cases fail in **opposite directions**, and that is the point. Measured across the
development set: `inconsistent` shows reduced chi-square 0.71–2.30 while `degenerate_parameters`
shows **0.11–0.20** — the lowest of the three, *better* than the answerable cases. A searcher that
abstains when its residuals look bad catches `inconsistent` and walks straight into the other one.
What separates `degenerate_parameters` is the **width** of the answer, not its quality: the
admissible `kappa` interval is 0.025–0.045 on answerable cases and 0.050–0.105 on those.

The Reynolds spans overlap on purpose. With two fixed spans the three regimes separate cleanly and
a pair of thresholds scores one; real cases are not sorted for you.

## What is scored

**Three axes, reported separately and never averaged**, each with its denominator:

| axis | meaning |
|---|---|
| `mechanism_score` | on answerable cases, does the formula reproduce **held-out** Reynolds numbers you never observed? |
| `false_discovery_rate` | of the laws submitted, how many fail held-out? |
| `correct_refusal_rate` | on unanswerable cases, does the searcher abstain? |

plus `discovery_coverage`, how often it declined to abstain. Without it, "abstained on everything"
and "the science is too hard" look identical in the report and call for opposite responses.

`combined_score` is the product of recovery, `(1 - false discovery rate)` and refusal. Blanket
abstention scores zero because it recovers nothing; never abstaining scores zero because its refusal
rate is zero. Both degenerate strategies land on zero and the report tells them apart.

A formula counts as recovering the law when it reproduces the held-out profiles to within 6 % of the
centreline velocity — four to five times the observation noise, and calibrated so that the
answerable regime clears it with a factor of 1.4 in hand and the degenerate regime misses it by the
same factor.

## Contract

Implement `build_closure(problem, observe)`. It returns

```python
{"abstain": bool, "mixing_length": <expression or None>, "confidence": float}
```

The expression is a nested list over `y` (wall distance in wall units) and `re` (friction Reynolds
number), with `add sub mul div` and `neg exp tanh sqrt square`, and constants written
`["const", numerator, denominator]` as exact integers. Floats are rejected. The van Driest closure
is eleven nodes; the cap is forty, which is what keeps this a search for a law rather than for a
flexible interpolant.

`observe(re_tau)` returns a binned mean profile at one of `problem["sampled_re_tau"]` and is charged
against `problem["observation_budget"]`. `problem` carries these keys, all public:

| key | meaning |
|---|---|
| `case_id` | which case this is |
| `sampled_re_tau` | the friction Reynolds numbers you may observe |
| `heldout_re_tau` | the ones the formula is scored on, which you never observe |
| `observation_budget` | how many profile runs you may spend in total |
| `max_formula_nodes`, `max_formula_depth` | caps on the submitted expression |
| `grammar` | the variables and operators the expression may use |
| `closure_meaning` | that the expression is the mixing length `l+(y+)` |
| `heldout_tolerance` | how close the held-out profiles must be to count as recovered |
 Submission shape is checked by `sle.contract_lint` before scoring.

## What this task does not measure, and does not settle

The frozen solver is a mixing-length model, not a simulation. Its own log-law constants — `kappa`
between 0.418 and 0.421, intercept between 5.32 and 5.55 — are the constants **it was given**,
recovered by fitting its own output, which validates the quadrature and nothing about nature. The
highest-Reynolds-number channel DNS measures `kappa = 0.384 ± 0.004` (Lee & Moser, *JFM* **774**
(2015) 395), which differs from the textbook 0.41; that disagreement is live and this task does not
adjudicate it. What is scored here is whether a searcher can tell a determined closure from an
undetermined one under a budget.

## Relation to the rest of this benchmark

`Turbulence/RANSCalibration` is in the same subject and is `parameter_inversion`: the form is given
and the numbers are recovered. Here the *form* is the product and the honest answer is often that
there isn't one. This is the first `formula` task in Engineering, whose other sixteen tasks are all
`engineering_design`. No task in the Frontier-Eng catalogue (47 in the paper appendix, 95 in its
`TASK_DETAILS`) concerns closure discovery or model-form uncertainty.
