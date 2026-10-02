# Archived prediction and baseline headroom audit

`env.predictability_diagnostics` compares candidate and baseline errors already
stored in frozen cohort reports. It imports only Python's standard library. It
does not import a World, execute a predictor or baseline, call a model API, load
the current scorer, or change any original report. This is a descriptive audit,
not a replacement evaluation or composite score.

Save an analysis plan before inspecting numeric results. Its `protocol` must be
`sle-paired-predictability-audit-0.1`, and its `cohorts` list must match the ordered
cohort selections. The planned real-data audit separates `core-c2`,
`expansion-e1`, and `interface-smoke-s1`.

```sh
python -m env.predictability_diagnostics \
  --cohort /private/campaign/core-c2 \
  --cohort /private/campaign/expansion-e1 \
  --cohort /private/campaign/interface-smoke-s1 \
  --analysis-plan /private/calibration/predictability-headroom/analysis-plan.json \
  --output /private/calibration/predictability-headroom/new-run
```

The output directory must be new and outside all selected source cohorts. Each
input manifest/report is hashed before analysis and checked again afterward.
`private-detail.json` records the analyzer source hash, plan/hash, input hashes,
episode identities, and scalar panel validity/error details. No target matrices
or predictor code are copied. `public-summary.json` contains an explicit
allowlist of anonymous episode/kind rows, world/kind summaries, failure counts,
and methodological assumptions. It contains no seeds, specs, targets, private
strata, transcript, source paths or hashes. Both artifacts are initially private;
review the allowlisted summary before using it in a public report.

For each episode, pair only unique panel indices within the same kind
(`conditions` or `interventions`). Never pair by list position. Candidate rows
must explicitly have `valid: true`; a baseline may omit that flag because older
reports did. Both rows need finite nonnegative `normalized_rmse`, a finite
original `score` in [0,100], and equal positive `scored_rows`. Duplicated indices,
invalid flags, malformed numbers, missing panels and incompatible row counts are
counted and excluded. Unexpected extra rows are reported separately. Baseline
records in these archives do not contain experiment specifications, so identity
of the paired query relies on the frozen runner's shared index contract; this
audit cannot independently reconstruct that query.

For N eligible paired experiments with candidate errors c_i and baseline errors
b_i, the reported values are:

* candidate MSE = mean(c_i²);
* baseline MSE = mean(b_i²), using exactly the same N experiments;
* skill = 1 − candidate MSE / baseline MSE;
* original prediction score = mean of the stored exponential scores, separately
  for candidate and baseline on those same N experiments.

Each experiment has equal weight regardless of its number of time samples or
channels. Skill is a ratio of mean MSEs, not a mean of experiment-level ratios.
Skill is undefined when N=0 or baseline MSE≤10⁻¹²; it is not forced to zero or
one. Negative skill is retained, including large negative values against an
extremely accurate baseline. There is no cross-kind or cross-cohort aggregate.

The exponential score is nonlinear: a model can have a higher mean score while
having worse mean squared error, for example by fitting many experiments well
and failing badly on a few. Both quantities are therefore shown. A large
relative MSE reduction against a nearly perfect baseline can coincide with a
very small absolute score gain.

Every planned manifest episode remains in the denominator. Completed,
invalid-predictor, incomplete, other model failure, infrastructure failure,
missing-report and unreadable-report categories are reported separately.
Every planned panel contributes either an eligible pair or an exclusion reason.
If an unsuccessful episode has some valid pairs, those pairs remain visible and
are counted by episode category. The metrics describe the valid paired subset;
they do not erase failure outcomes or assign made-up errors to them.

World summaries also report how many individual episodes have lower, equal or
higher candidate mean MSE than baseline, including unavailable episodes. Panels
within a world instance are dependent, and the smoke batch has only one instance;
no panel-level significance test or capability generalization is claimed.
Under the frozen runner contract, the baseline is each world's existing
algorithm supplied with all public experiment records collected during that
same episode. These algorithms may carry different model-family priors; they
are not interchangeable with a no-prior or no-data baseline. This audit compares
the archived references actually used, not an optimal or uniformly informed
baseline. Neither high absolute scores nor positive skill
establish mechanism recovery, novelty, or resistance to contamination.

Run the synthetic regression suite with:

```sh
python -m pytest env/tests/test_predictability_diagnostics.py -q
```

The suite checks equal experiment weighting, ratio-of-means arithmetic,
nonlinearity of scores, exact index pairing, failures/missingness, malformed
numeric data, near-zero baselines, public-output filtering, immutable inputs,
exclusive outputs, batch separation and the absence of simulator/API imports.
