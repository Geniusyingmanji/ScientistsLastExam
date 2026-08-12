# ProspectiveMetaAnalysis-v1 — synthesize registered evidence and design confirmation

## Scientific setting

A literature search can return several articles from one participant lineage, highlight an
outcome different from the preregistered primary endpoint, omit an eligible null trial, or mix
in the wrong population, comparator or design. Treating every article and highlighted result as
independent evidence can bias both a meta-analysis and the next experiment.

This task supplies a procedural registry-plus-publication corpus. Eligible trials are randomized,
use `target_condition`, compare with `standard_care`, and preregister `response_12w` as primary.
Each record declares its registration lineage, moderator, sample size, outcome estimates and
standard errors. The supported public model is

```text
effect(x) = intercept + moderator_slope * x,
```

with residual between-study standard deviation `tau`. Some worlds violate that linear family;
you should then abstain rather than force a benefit claim.

## Artifact and prospective confirmation

Implement:

```python
def synthesize_evidence(problem, confirm):
    """Screen records, commit a model/forecast/design, run one fresh study, update."""
```

`problem` contains `records`, exact eligibility criteria, effect/tau bounds, a decision moderator,
a benefit threshold and five candidate sites. Each site exposes its moderator, cost and maximum
sample size. Choose a sample size on the public grid without exceeding `study_budget`.

Before observing the fresh result, call `confirm(commit)` exactly once if you make a scientific
claim. The commit must contain:

- `screening`: included registration IDs, one registry-primary record per eligible lineage,
  record-ID groups sharing participants, and publications that highlight a non-preregistered
  outcome;
- `preconfirmation`: intercept, slope, tau, calibrated confidence, abstention and benefit claim;
- `site_id`, `sample_size`, and a 90% prediction interval for that exact new study.

`confirm` returns one newly generated preregistered primary result. The final artifact must repeat
the immutable `confirmation_commit` and provide `postconfirmation` model/claim fields. Editing the
commit after seeing the result fails closed. You may abstain without calling `confirm`, but that is
a valid zero-score baseline rather than evidence synthesis.

## Evaluation

- `combined_score` is development quality above always abstaining and keeps evidence integrity,
  supported-model recovery, prediction, decision/refusal, forecast, next-study information and
  post-confirmation updating as distinct components.
- `robustness_score` is the minimum across those components and worlds; one excellent pooled
  estimate cannot compensate for double counting or an unsupported claim.
- Held-out corpora change effect, heterogeneity, publication patterns and decision moderator.
- Duplicate-lineage F1, selective-report F1, false discovery, supported-claim coverage,
  unsupported-family refusal, forecast calibration and confirmation remain evaluator-only.

This is a synthetic registered-study laboratory. It does not replace a domain-specific systematic
review, individual-participant-data audit, risk-of-bias assessment, GRADE judgment, clinical trial
or real prospective meta-analysis. The fresh result is a sealed simulated confirmation, not a
human experiment or medical claim.

## Checking your submission's shape before spending a call

`frontier_science.contract_lint` is importable inside the sandbox. Calling it costs no oracle
budget and reveals nothing about the science — every check is about form, and none touches a
score, a hidden world or a reference value.

```python
from frontier_science.contract_lint import mapping, finite_array, in_range, explain

ok, why = mapping(submission, required=["a", "b"])
if not ok:
    ...  # `why` names the missing or unexpected keys
```

Available: `finite_array`, `binary_array`, `mapping`, `in_range`, `probabilities`,
`sequence_of_str`, and `explain` to join failures into one message. Each returns `(ok, reason)`
with a specific reason — "expected shape (12000, 1), got (3, 3)" rather than "invalid submission".

This exists because a rejected submission and a hard scientific problem both score zero, and this
task is one where submissions have been rejected often enough that the distinction matters.

## Rules

- Only edit `solution.py`; keep `synthesize_evidence(problem, confirm)`.
- Count statistical participant lineages, not articles, as independent evidence.
- At most one confirmation call; caught duplicate or invalid calls still invalidate the world.
- Deterministic CPU Python/NumPy/SciPy/stdlib only; no network/process creation.
- Do not read `verification/` or `frontier_eval/`.

## References

- DerSimonian and Laird, *Meta-analysis in clinical trials*, Controlled Clinical Trials 7(3),
  177–188 (1986), DOI `10.1016/0197-2456(86)90046-2`.
- Higgins and Thompson, *Quantifying heterogeneity in a meta-analysis*, Statistics in Medicine
  21(11), 1539–1558 (2002), DOI `10.1002/sim.1186`.
- Knapp and Hartung, *Improved tests for a random effects meta-regression with a single
  covariate*, Statistics in Medicine 22(17), 2693–2710 (2003), DOI `10.1002/sim.1482`.
- von Elm et al., *Different Patterns of Duplicate Publication: An Analysis of Articles Used in
  Systematic Reviews*, JAMA 291(8), 974–980 (2004), DOI `10.1001/jama.291.8.974`.
- Chan et al., *Empirical Evidence for Selective Reporting of Outcomes in Randomized Trials*,
  JAMA 291(20), 2457–2465 (2004), DOI `10.1001/jama.291.20.2457`.
- Seidler et al., *A guide to prospective meta-analysis*, BMJ 367, l5342 (2019), DOI
  `10.1136/bmj.l5342`.
- Page et al., *The PRISMA 2020 statement*, BMJ 372, n71 (2021), DOI `10.1136/bmj.n71`.
