# Discovery rubric v0.1 — operator review, separate from prediction

This rubric evaluates scoped equations and research evidence. It is not a hidden
family-name quiz. No automatic scientific-difficulty certificate or total score.

## Candidate deliverables
`model.py: predict(spec)` returns measurements for every requested time/channel.
`report.md` supplies equations, variable meanings/units, inferred parameters,
uncertainty, alternatives, experiment choices, and validity limits.
`mechanisms.json` is a list of objects with `claim`, `equation`, `scope`,
`evidence_ids`, `uncertainty`. Equivalent notation and latent-state coordinates
are allowed. Additional unrequested mechanisms are audited as possible false
claims, rather than ignored when calculating precision.

## Fixed operator modules
1. Substrate-to-A growth plus multiple carbon products.
2. Consumption of an A product by B with biomass/product yield accounting.
3. B product allocation: constant or regulated as applicable.
4. Consumption of a B product by C and inhibition by another pool.
5. Signal dependence of allocation, if present.
6. Environment dependence of the regulation threshold, if present.
7. Finite response memory, if present; instantaneous controls are legitimate.
8. Turnover and inert carbon bookkeeping.

Module applicability and structural identifiability are operator facts established
before formal evaluation, not claims supplied to the agent. The engineering pilot
cannot itself establish this complete denominator. Report coverage as provisional
until each module has an identifiability witness under legal interventions.

## Per-module review fields
- `applicable`: yes/no; `identifiable`: established/unresolved.
- `claim_status`: recovered/partial/incorrect/not_claimed/unresolved.
- `equation_status`: algebraically_equivalent/functional_only/incorrect/absent.
- `evidence_status`: prospective_discrimination/retrospective_fit/assertion/none.
- `evidence_ids` and exact final-artifact locations; reviewer explanation.
- `scope`: tested domain, untested extrapolation and confounded parameters.

A correct mechanism with incorrect rate law receives mechanism credit only.
A flexible predictor with accurate curves but no interpretable equation receives
prediction credit only. Numeric checks of a submitted equation establish
functional agreement on the tested domain, not unique symbolic recovery.
Algebraic equivalence must be checked after declared variable/unit transformations;
parameters recoverable only as products are graded as products.

## Reported metrics
- established module coverage = recovered / applicable identifiable modules;
  list partials separately; never turn unresolved denominator entries into zero.
- false discovery fraction = incorrect / all submitted adjudicated claims;
  report counts and unresolved claims alongside it. Deduplicate equivalent claims.
- equation recovery count, with algebraic vs functional-only counts separated.
- prospective evidence count: a recorded prediction and competing explanation
  must precede the fresh observation that discriminates them.
- trajectory errors per observable, and new-condition/intervention/history errors.
- operational failures and budgets separate from all scientific scores.

No human interpretation of missing traces as success. Same-family independent
review is provisional; preserve disagreements and source records.
