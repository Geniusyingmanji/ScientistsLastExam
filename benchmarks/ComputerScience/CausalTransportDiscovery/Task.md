# CausalTransportDiscovery — dose-response transport with missing support

**Candidate, uncalibrated, excluded from default benchmark admission.** This is
an original synthetic statistical experiment. It does not model a real drug,
establish a clinical precision requirement, or claim frontier-model difficulty.

Recover heterogeneous dose-response curves and predict effects in new target
populations. Source subjects have two perfectly aligned pre-treatment modifiers,
`X=Z`. That source experiment cannot establish whether a response generalizes
when X and Z disagree. Four bridge recruitment sites contain discordant subjects
at unknown prevalences. X is cheap; measuring Z costs money. Decide where to
recruit, what dose to administer and how many biomarkers to measure, then commit
curves and uncertainty before independent confirmation.

Some publicly specified access profiles exclude one discordant cell from all
interventional recruitment. Its effect is not identified by any allowed tool.
Report valid partial-identification bounds instead of guessing a unique curve.
Reading that access restriction is not itself a difficult discovery.

## Public scientific assumptions

X and Z take values −1 and +1. Cell order is `[[-1,-1],[-1,+1],[+1,-1],[+1,+1]]`.
They are baseline characteristics; selecting X is recruitment stratification,
not an intervention on a covariate. Dose `d` is an intervention in `[0,1]`.

Each cell has three continuous Bernstein coefficients in `[−0.35,+0.35]`:

```text
B(d) = [3*d*(1-d)^2, 3*d*d*(1-d), d^3]
tau_cell(d) = B(d) dot theta_cell
P(Y=1 | cell, do(d)) = 0.5 + tau_cell(d)
```

Y is Bernoulli, all enrolled outcomes are observed, and the control mean at
dose zero is known to be 0.5. The nonnegative basis sums to at most one, so all
outcome probabilities lie in `[0.15,0.85]`. Unlike SurvivorshipAuditDesign this
task has complete outcome ascertainment; its missing information concerns
biomarkers and target-population support. It does not covertly reintroduce
nonresponse assumptions.

**Conditional transport invariance is an explicit assumption:** the four cell
response functions are shared across sites. Sites change the cell mixture,
not conditional response. Source support contains only X=Z. Bridge eligibility
is given in the problem. Within each site/X group, subjects are fresh independent
draws. Biomarker assays sample individuals uniformly without replacement,
independently of outcomes; the sampled Z remains paired to its Y.

Target population weights are specified, sum to one and can include cells that
cannot be recruited. Their weights are independent of response coefficients.
Do not use a recruitment site's biomarker proportion as a deployment weight.

## Entry point and every problem key

Implement `solve(problem, experiment)` and return one JSON claim. The generic
episode runner also permits a model to choose each next experiment after its
previous observation. The runner enforces budget and irreversible commitment;
never import `verification/` or infer a private seed from filesystem state.

| Key | Meaning |
|---|---|
| `task_id` | `CausalDiscovery/CausalTransportDiscovery` |
| `contract_version` | `transport-dose-pilot-v1` |
| `budget_units` | 12000 exploration units |
| `cells` | The fixed four-cell ordering above |
| `sites` | `source`, `bridge-a`, `bridge-b`, `bridge-c`, `bridge-d` |
| `source_support` | The two concordant cells |
| `bridge_accessible_cells` | Cells that can appear in bridge interventions and recruitment surveys |
| `target_populations` | Three `{id, cell_weights}` objects for deployment targets |
| `response_model` | Outcome equation, dose and coefficient bounds, control mean, transport assumption, modifier semantics and resolution |
| `sampling` | Recruitment and random biomarker sampling assumptions above |
| `tools` | Exact argument names, bounds, costs and response fields below |
| `claim_schema` | Exact claim structure and marginal interval coverage |
| `confirmation` | Independent new-dose/new-mixture design, operator cost and joint precision criterion |
| `identifiability` | What source-only and inaccessible cells cannot identify |

The `response_model.modifier_resolution` defines heterogeneity that this pilot
attempts to resolve. Form the three coefficient contrasts
`beta_X=sum(X*theta)/4`, `beta_Z=sum(Z*theta)/4`, and
`beta_XZ=sum(X*Z*theta)/4`. Compute each contrast curve's RMS on 101 uniformly
spaced doses including 0 and 1. RMS ≤0.02 is negligible, RMS ≥0.05 is meaningful,
and the region between them is unresolved. Exact nonzero generator coefficients
are separately a construction diagnostic; an arbitrarily small nonzero
coefficient is not automatically a scientifically resolvable mechanism.

## Charged tools

Both tools accept only their listed keys. `x` must be integer −1 or +1; `n` must
be an integer in `[8,256]`. Booleans are not integers. `site` must be a listed
site. No tool returns hidden response coefficients or world identifiers.

`survey` requires `{site, x, n}` and costs **4*n** units. It returns
`{site,x,n,z_values}` for a fresh recruitment sample with measured biomarkers.
This estimates recruitment efficiency. It does not observe outcomes or change
the target population weights.

`trial` requires `{site,x,dose,n,assay_n}`. Dose is finite in `[0,1]` and
`assay_n` is an integer in `[0,n]`. Cost is **n + 3*assay_n** units: enrollment
and complete outcome acquisition cost one unit; each random biomarker test
costs three more. It returns `{site,x,dose,n,assay_probability,records}`, where
`assay_probability=assay_n/n` and every record has `{y,z}`. `y` is 0 or 1;
unmeasured `z` is `null`. Source Z=X is already known from the public support
restriction, so it need not be assayed. Each call draws different subjects.

These are synthetic accounting units, not monetary prices. Costs are determined
only by public action arguments. Invalid actions draw no cohort. The session
refuses overspending before executing an action. The environment adapter alone
is not a sandbox or budget enforcer.

## Frozen claim

The top-level object has exactly `decision`, `curves`, and `modifiers`.
Decision is `discover`, `partial`, or `abstain`. For abstention, use
`{"decision":"abstain","curves":[],"modifiers":null}`.

Other decisions supply four cell-ordered curve objects, each with exactly:

| Field | Contract |
|---|---|
| `estimated` | Boolean: a quantitative curve is asserted |
| `coefficients` | Three finite numbers in `[−0.35,+0.35]`, or `null` for an unestimated curve |
| `intervals` | Three ordered endpoint pairs in `[−0.35,+0.35]`; marginal nominal 95% coefficient intervals |
| `covariance` | A symmetric positive-semidefinite 3×3 coefficient covariance matrix, entries finite in `[−1,1]`; `null` if unestimated |

An unestimated curve must use three full intervals `[−0.35,+0.35]`. This states
the allowed identification region and earns no curve discovery credit.
`discover` requires all four curves estimated. `partial` requires at least one
unestimated curve. A partial claim may still make useful, precise predictions
for reachable cells.

`modifiers` is a unique subset of `X`, `Z`, `X:Z`, or `null` when no complete
modifier assertion is made. Absence from a nonnull set asserts that modifier
is negligible at the declared resolution. Intermediate signals do not require
a unique label. Missing an entire cell prevents identifying the global modifier
set without an additional assumption; that assumption is not provided here.

Covariances describe estimation uncertainty for the coefficients, conditional
on collected design. The confirmation evaluator propagates within-cell
covariance and treats disjoint cell estimates as independent. If an estimator
couples cells, it must provide conservative marginal covariances sufficient for
the reported aggregate uncertainty, or refrain from that precision claim.
Intervals and covariance are falsifiable uncertainty artifacts; merely choosing
small variances does not make an uncertain claim succeed.

`model.py` provides public basis and population prediction helpers. A scientific
wrong answer is accepted as a valid-shaped claim and then evaluated; validation
does not reveal which answer is correct.

## Confirmation and private evaluation

After immutable commitment, the operator samples five new doses in `[0.08,1]`
and three new population mixtures. It obtains 2048 complete Bernoulli outcomes
per cell/dose, including inaccessible exploration cells. This is 40960 reserved
measurements outside exploration. Such complete ascertainment is a simulated
external follow-up, not a tool the candidate can call before commitment.

Confirmation returns `protocol`, `doses`, `population_weights`,
`n_per_cell_and_dose`, and `cell_observed_means`. It contains noisy observations,
not exact means. Its random stream is independent of exploration call history.
The session ends after confirmation; new model fitting cannot revise the claim.

Metrics remain separate, with explicit numerators and denominators:

- `mechanism_recovery`: correct resolved modifier decisions / resolved modifier
  opportunities, only where all cells are structurally accessible.
  `exact_generator_mask_recovery_diagnostic` concerns exact generator terms and
  must not become a scientific headline.
- `false_discovery_rate`: claimed negligible modifiers / claimed resolved
  modifiers. Intermediate-signal claims are counted separately as unresolved;
  omissions have `modifier_omission_rate`. Unsupported global modifier assertions
  and unsupported cell point estimates have their own rates.
- `claimed_curve_coverage`: estimated accessible curves / accessible curves.
  The compatibility key `discovery_coverage` has the same meaning. This measures
  claims made, not verified correctness: a no-query prior also has full coverage.
- `curve_rmse` and `population_prediction_rmse` compare precommitted predictions
  with fresh-design latent response means. `confirmation_observed_rmse` also
  compares to actual new noisy observations. Partial-claim errors only cover
  estimated accessible cells; always report coverage alongside them.
- Coefficient interval coverage, mean width, and mean interval score are separate.
  For nominal 95% interval `[l,u]`, the score is width plus 40 times any distance
  of truth below l or above u; smaller is better. Wide intervals are not free.
- Population intervals propagate reported coefficient covariance with a normal
  1.96 multiplier and add full unresolved-cell contribution bounds. Coverage and
  width are reported. Nominal marginal 95% intervals are not a promise of 95%
  simultaneous coverage across all doses and populations.
- `correct_refusal_rate` checks declining to estimate an inaccessible cell while
  making a partial claim. Public support metadata alone suffices for that decision.
  The bounds-only control demonstrates it; it is not difficult mechanism recovery.
- `joint_success` applies only to worlds with full accessible support. It requires
  target-dose prediction RMSE ≤0.025 probability units, all 15 true target-dose
  effects inside the reported propagated intervals, average interval width ≤0.10,
  and correct decisions on every resolved modifier. These are declared synthetic
  precision requirements: 2.5 percentage-point RMSE and 10 percentage-point mean
  interval width, not thresholds derived from clinical practice. This conjunction
  is reported alongside every component, not as a replacement for them.

Zero-denominator rates are `null`. Full abstention and vacuous prior bounds have
no verified curve/point predictions; their refusal or bound coverage cannot be
reported as task completion. Confirmation is within the same synthetic model
family, with new doses, mixtures and subjects; it is not a new simulator or a
domain discovery.

## Controls, limits and relationship to previous tasks

`verification/reference.py` contains a truth-blind adaptive recruitment policy,
a strong source-plus-full-site-factorial fixed policy, an all-bridge full
factorial, independent randomized recruitment, source-only partial inference,
unjustified source extrapolation, a no-query zero prior, full bounds, and full
abstention. All scientific design policies spend exactly 12000 units. Fixed
and random policies buy no surveys they subsequently ignore. Adaptive advantage
is an empirical question, not an assumption or admission requirement.

Construction review found that the optimized fixed policy can outperform the
adaptive witness and saturated an earlier exact-mask diagnostic. Those findings
are preserved; no baseline is weakened to manufacture headroom. Quantitative
curve prediction, interval calibration, and precision-qualified joint success
must be measured separately. Frontier-model difficulty is still unmeasured.

Run `python benchmarks/ComputerScience/CausalTransportDiscovery/verification/audit_controls.py
--worlds 24 --output /tmp/transport-controls.json` from the repository root.
The saved construction report binds source hashes and denominators. Its paired
worlds are not independent model draws. Family-held-out model calibration and
an independent domain review remain required.

This successor adds missing-support transport, continuous dose response,
biomarker measurement and target prediction to SurvivorshipAuditDesign's fixed
population effect estimation. It does not alter that task's scientific contract.
InterventionalSCM asks for a graph under different observation assumptions;
this task assumes site invariance and tests transport of effect curves.
The broad transport principle follows [Bareinboim and Pearl (2016)](https://doi.org/10.1073/pnas.1510507113);
uncertainty scoring follows [Gneiting and Raftery (2007)](https://doi.org/10.1198/016214506000001437).
The specific generator, prices and thresholds are original benchmark choices.
