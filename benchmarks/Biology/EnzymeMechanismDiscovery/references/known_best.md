# EnzymeMechanismDiscovery construction record

Status: **protocol_only, frontier_eligible=false; no frontier-model difficulty calibration**. These results
test a functioning episode and whether dynamic evidence matters. They do not
qualify this small family for the default expert benchmark.

## Reference

`verification/reference.py:solve(problem, experiment)` is a runnable, truth-blind
witness. It accesses public equations, parameter ranges and charged observations
only. Four initial time courses fit a relaxed continuous model; two further
assays are selected by disagreement with module alternatives; the final model is
refitted with explicitly present/absent modules. No world truth, seed or private
oracle import appears in the witness.

On the 24 construction worlds (seeds 0 through 23), it recovered 24/24 effective
compositions; all 72 fresh confirmation trajectories passed the declared
0.06 mM tolerance. Mean score was 0.999318 and mean confirmation RMSE was
0.001467 mM, using 104 units per world. The continuous reference is intentionally
competent: artificially degrading it would not establish difficulty.

## Baseline

The no-query baseline guesses the empty composition and midpoint core kinetic
parameters. It recovered 1/24 compositions, passed 1/72 confirmation trajectories
and scored about 3.63e-8 on average. It is legal but not mathematically fixed to
zero: it can guess a simple world correctly. All-abstain is exactly zero and its
false-discovery denominator is zero, reported as null.

## Ablation ladder

All figures below are construction controls, not model results. The dynamic
controls use exactly the same 104 units. Static assays cost 3 units each, so 34
of them spend 102 units under the same comparison cap.

| Method | Units | Exact mechanism | Confirmation passes | Mean score |
|---|---:|---:|---:|---:|
| Adaptive dynamic witness | 104 | 24/24 | 72/72 | 0.999318 |
| Fixed dynamic design, same fitter | 104 | 24/24 | 72/72 | 0.999069 |
| Replicated initial-rate design | 102 | 13/24 | 9/72 | 0.086377 |
| No-query midpoint guess | 0 | 1/24 | 1/72 | 3.63e-8 |
| Always abstain | 0 | 0/24 | 0/0, not measured | 0 |

**Adaptive selection has not shown a meaningful advantage over the fixed
dynamic design.** Both recover everything in this panel. The supported result
is that initial-rate data cannot identify the dynamic modules, while a
well-designed fixed time-course panel can. This is an environment pilot, not
evidence of scientific frontier headroom.

## Shortcut probes

The exact paired-world tests hold the full initial-rate likelihood constant
while changing enzyme decay and intermediate turnover, then verify that dynamic
trajectories differ. A second pair agrees at zero initial product but separates
under product perturbation. These show a scientific reason that the old assay
design fails, rather than making that design fail by adding arbitrary noise.

The eight known compositions are still small enough for generic nonlinear
fitting. A finite formula-selection program has become a compositional dynamic
fit, but there is no claim that this defeats present frontier models. Broader
parameter/world panels and model proposals must be evaluated before promotion.

Before accepting this as a harder replacement, we also reduced the experimental
allocation without changing the noise, physics, tolerances or score. The smaller
policies start from two time courses, then use one or two selected/fixed pulses.
The original policy uses four initial courses and two pulses. Every cell below
contains 24 worlds, and adaptive/fixed methods spend equal units within a cell.

| Budget cap | Actual cost | Design | Mean score | Mean RMSE (mM) | Exact mechanism | Confirmation |
|---|---:|---|---:|---:|---:|---:|
| 60 | 52 | Fixed | 0.988127 | 0.004604 | 24/24 | 72/72 |
| 60 | 52 | Adaptive | 0.994361 | 0.003053 | 24/24 | 72/72 |
| 80 | 72 | Fixed | 0.994595 | 0.003040 | 24/24 | 72/72 |
| 80 | 72 | Adaptive | 0.998969 | 0.001723 | 24/24 | 72/72 |
| 104 | 104 | Fixed | 0.999069 | 0.001681 | 24/24 | 72/72 |
| 104 | 104 | Adaptive | 0.999318 | 0.001467 | 24/24 | 72/72 |

This bounded study **failed to establish useful scientific discrimination**.
The fixture stays protocol-only at its original 216-unit cap. No arbitrary score
rescaling, weaker reference or extra noise was used to manufacture difficulty.
The retired static task remains retired; this pilot cannot replace it in frontier
aggregates. A genuinely broader scientifically reviewed family is still needed.
Reproduce the study with:

```sh
python -m benchmarks.Biology.EnzymeMechanismDiscovery.verification.audit_budgets \
  --worlds 24 --output /tmp/enzyme-budget-study.json
```

## Frontier draws

None. Construction control programs were written by the builder and are not
independent model proposals. Their performance must never be counted as an
unseen-model test, blind evaluation, domain review or new scientific discovery.

## Construction errors and corrections

- Early adaptive controls had some cheaper non-pulse choices. They were changed
  to equal-cost pulse alternatives before the published matched-cost panel.
- Initial static controls used 24 units. They were expanded to 102 units of
  replicated initial rates so their failure is not attributed to an unfair
  fourfold resource deficit.
- Independent code review found that `math.isfinite` could overflow on a huge
  but valid JSON integer. Numeric bounds are now checked first, and malformed
  claim/assay regressions include an integer of magnitude `10**1000`.

## Robustness and remaining evidence

The focused test suite checks conservation through discontinuous pulses,
nonnegative concentration trajectories, an independently integrated four-state
ODE, observationally confounded pairs, all eight module compositions, matched
control costs, input/budget failures, hidden-seed separation, immutable claims,
confirmation independence and tamper rejection, and rate denominator semantics.

`construction-controls.json` records aggregate controls and hashes of the exact
model, environment, reference and audit sources. Reproduce with:

```sh
python -m benchmarks.Biology.EnzymeMechanismDiscovery.verification.audit_controls \
  --worlds 24 --output /tmp/enzyme-construction-controls.json
python -m pytest -q tests/test_enzyme_mechanism_discovery.py
```

Remaining admission requirements include independent domain review, empirical
model calibration on frozen proposals, fresh private world panels, larger
shortcut search, and a scientific reason for any further family expansion.
The current pilot contains no out-of-family worlds, no asserted calibrated
refusal performance, no wet-lab validation and no cross-simulator confirmation.
