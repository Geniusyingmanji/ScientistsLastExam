# SurvivorshipAuditDesign — population effects with costly nonresponse follow-up

**Status: executable episode pilot; difficulty unmeasured; not admitted to the default benchmark.**

Estimate a randomized treatment's average effect in a specified deployment population.
Outcomes are normally observed only for people who return. Treatment directly affects
return, and response and selection differ between four population strata. Consequently,
neither a change in return rates nor a difference between returners' mean outcomes
identifies the population effect. You may pay to follow a uniform random sample of
nonreturners. These follow-ups have complete ascertainment.

The scientific artifact consists of a population estimate, its interval, subgroup
estimates and intervals, and a positive, negative or negligible effect conclusion.
Fresh complete-outcome trials are reserved for independent confirmation after commitment.
This is a synthetic causal-design experiment, not evidence of a discovery about real people.

## Episode interface and lifecycle

For a program-controlled episode, implement:

```python
def solve(problem, experiment):
    observation = experiment("trial", {
        "stratum": 0, "treatment": 1, "n": 256, "audit_n": 128
    })
    # Make more experiments within budget, then return a claim.
    return {"abstain": True, "confidence": 0.0}
```

The same tools can be used by a model that chooses its next action after each observation.
These interaction modes must be reported separately. The session runner enforces charges,
commits the final claim immutably, performs the reserved confirmation, and stores private
metrics. Confirmation is unavailable during exploration; a committed claim cannot be edited
after seeing it. The trusted environment module is not itself a sandbox or a budget ledger.

### Every public problem key

| Key | Meaning |
|---|---|
| `task_id` | `CausalDiscovery/SurvivorshipAuditDesign` |
| `version` | Scientific episode contract version, `episode-pilot-v1` |
| `budget_units` | 12000 exploration units |
| `strata` | Integer stratum labels `[0,1,2,3]` |
| `target_population` | `deployment` |
| `target_weights` | Deployment proportions `[0.10,0.20,0.30,0.40]`, in stratum order |
| `treatment_levels` | Randomized assignments `[0,1]` |
| `equivalence_margin` | 0.20 outcome units |
| `interval_confidence` | 0.95 nominal marginal coverage |
| `action_schemas` | Required argument names, public types, limits and cost expression below |
| `sampling` | Fresh randomized cohorts and uniform sampling without replacement of nonreturners |
| `selection_assumptions` | Outcome-dependent selection with direct treatment and stratum effects; complete follow-up |
| `estimand` | Weighted population average treatment effect |
| `claim_schema` | Required claim fields, values and dimensions below |
| `confirmation_protocol` | Reserved fresh trial size, complete ascertainment, cost and release policy |
| `metrics` | Independent result axes and basic internal consistency requirements |

### `trial` action

Exactly four arguments are required. Booleans and floating-point values are not integers.

| Argument | Constraint |
|---|---|
| `stratum` | Integer 0 through 3 |
| `treatment` | Integer 0 or 1 |
| `n` | Integer 32 through 512; enrollments in a fresh cohort |
| `audit_n` | Integer 0 through `n`; reserved random follow-up slots |

The cost is **`n + 4 * audit_n`**. Each enrollment costs one unit; each reserved follow-up
slot costs four additional units. All reserved slots are charged even if fewer people are
missing; there are no refunds dependent on hidden selection. The session rejects an action
that would exceed the remaining budget before requesting observations. Malformed arguments
do not access scientific state or consume a random cohort.

Each response contains exactly:

| Key | Meaning |
|---|---|
| `stratum`, `treatment` | Requested stratum and randomized arm |
| `n_enrolled` | Requested `n` |
| `n_returned`, `n_missing` | Complementary cohort counts |
| `audit_requested` | Requested `audit_n` |
| `n_audited` | `min(audit_n, n_missing)` |
| `audit_inclusion_probability` | `n_audited / n_missing`, or `null` if nobody is missing |
| `survivor_outcomes` | List of all routinely returned outcomes |
| `audited_outcomes` | List from the uniform random sample of nonreturners |

Outcome units are arbitrary and may be negative. Latent prognostic variables are not
returned. Subjects in different calls are independent new people. There is no longitudinal
linkage or observational treatment assignment. Population stratum weights are specified,
so changing enrollment allocation does not change the target population.

## Claim contract

An abstention has exactly `abstain: true` and a finite numeric `confidence` in `[0,1]`.
This is a legal scientific output, not an invalid submission. It earns no recovery or
estimation credit and has no effect estimate or interval to score.

A nonabstaining claim contains exactly:

```json
{
  "abstain": false,
  "confidence": 0.95,
  "effect_class": "positive",
  "population_effect": 0.8,
  "population_interval": [0.5, 1.1],
  "stratum_effects": [0.8, 0.8, 0.8, 0.8],
  "stratum_intervals": [[0.3, 1.3], [0.3, 1.3], [0.3, 1.3], [0.3, 1.3]]
}
```

All estimates and endpoints must be finite JSON numbers; interval endpoints must be ordered.
Each subgroup list has length four. Here `confidence=0.95` declares nominal coverage,
not an extra probability of a mechanism or a field scored by an LLM. Subgroup intervals
are marginal, not simultaneous. Unknown fields, missing fields, nonfinite values and wrong
types are malformed. A wrong scientific conclusion remains a valid artifact and is graded.

The population estimand is

`sum_k target_weights[k] * (E[Y | do(T=1), stratum=k] - E[Y | do(T=0), stratum=k])`.

The class is positive above +0.20, negative below −0.20, or negligible within [−0.20,+0.20].
A supported assertion additionally needs its entire population interval in the corresponding
region. Its point estimates must lie in their intervals; its population point must equal the
weighted subgroup points within an absolute tolerance of `1e-6`. These are result checks,
not hidden restrictions on which scientifically wrong artifacts are accepted.

A negligible average does not mean all subgroup effects vanish. A negligible conclusion
is also not an abstention: population equivalence is a testable claim.

## Process and independent result checks

The reserved confirmation has 4096 new complete outcomes in **each of eight stratum–arm
cells**. Its stream is independent of exploration calls and cannot be selected by changing
the claim. These 32768 measurements are operator costs outside the agent's exploration
budget and must be recorded as such. The confirmation artifact contains:

- `protocol`: `complete-outcome-stratified-rct-v1`;
- `cells`: eight records with `stratum`, `treatment`, `n`, `mean_outcome`, `sample_variance`;
- `stratum_effects`, `stratum_standard_errors`: four measured differences and standard errors;
- `population_effect`, `population_standard_error`: their weighted measured contrast and uncertainty.

These are independent observations, not exact hidden effects. Replaying the same frozen
episode produces the same confirmation artifact. An operator-supplied substituted or
corrupted artifact is an evaluator error, not a scientific zero.

Trusted result metrics remain separate; this pilot intentionally publishes no `combined_score`:

- `mechanism_recovery`: a coherent, interval-supported population class is correct; numerator
  and denominator are reported. This is a coarse causal effect class, not recovery of a full DAG.
- `population_absolute_error`; diagnostic `effect_estimation_score = max(0, 1 - error/0.5)`;
  `stratum_effect_rmse`; interval coverage, widths and denominators. The 0.5 scale is a pilot
  reporting convention, not an established domain threshold or normalization for admission.
- `false_discovery_rate`: incorrect claimed nonzero classes divided by claimed nonzero classes.
  Wrong sign and a nonzero assertion in a negligible world count. `null_false_positive_rate`
  uses all negligible worlds as its denominator. A zero denominator is `null`, never zero.
- `abstention_rate` and `discovery_coverage` report refusal and attempted findings over all worlds.
  All pilot worlds are identifiable with random audits, so `correct_refusal_rate` for inherently
  nonidentifiable cases is unmeasured with denominator zero. It must not be filled with a null-world rate.
- `confirmation_success`: the committed class is supported by the confirmation's 95% normal
  interval and the independent point estimate lies inside the committed population interval.
  This is a specified replication diagnostic; it does not imply familywise 95% coverage.
  Confirmation prediction error is separately reported.
- `population_stratum_consistency_error`, `claim_self_consistent`, and `interval_supports_claim`
  check explicit artifact consistency. Trace integrity, budget compliance and commit timing are
  checked by the session runner; a long trace earns no scientific credit by itself.

## Relationship to nearby tasks and current limitations

`SurvivorshipConfoundedDesign` classifies an effect sign under a no-direct-treatment-to-selection
restriction. This pilot removes that restriction, permits heterogeneous effects, adds paid
random audits, and requires quantitative claims and new-data confirmation. `InterventionalSCM`
recovers a multivariate graph with different observation assumptions. `ProspectiveMetaAnalysis`
chooses studies and handles publication bias; this task instead follows individuals who did
not return from a randomized trial.

The synthetic generator has paired diagnostic worlds with identical return patterns and
different population effects. A return-rate-only strategy therefore cannot identify the effect
class in all paired worlds, regardless of its return-rate precision. A two-phase design does
identify the effect. The supplied reference uses a fixed balanced allocation with expansion
weights and an approximate two-phase sampling variance; it is a working witness, not an
oracle-informed solution or a proof of expert-level difficulty.

An initial 90-world construction panel gave mean population absolute errors of 0.0303 for
random audits, 0.2745 for survivor-only means, 0.7183 for a return-rate rule, and 1.0055 for
a constant no-query rule. The audited reference's coarse class recovery was 0.9889, so that
axis remains easy for a competent statistical method. **No frontier model has been measured
on this new task.** Candidate status remains in force; no external-domain approval, hard
classification or default-suite admission is implied by these checks.

Equal-budget controls also spend 11776 units, using three unaudited cohorts of 512, 512 and
448 people per cell. Their mean absolute errors are 0.3026 (survivor-only) and 0.7159
(return-rate rule), compared with 0.0303 for the audited design. More unaudited enrollments
reduce sampling variance but do not remove selection bias. Diagnostic worlds are paired,
so these 90 worlds are not 90 independent model draws. Run
`python benchmarks/ComputerScience/SurvivorshipAuditDesign/verification/diagnose.py`
from the repository root to reproduce all controls and their explicit denominators.

Future difficulty work must measure adaptive allocations, uncertainty calibration and unseen
selection/response families. The current independent confirmation uses the same causal
generator family with new subjects; it is not a mechanism-family holdout or external validation.

Random follow-up of nonresponders and inverse inclusion weighting follow the sampling designs
of [Hansen and Hurwitz (1946)](https://doi.org/10.1080/01621459.1946.10501894) and
[Horvitz and Thompson (1952)](https://doi.org/10.1080/01621459.1952.10483446).
