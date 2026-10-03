# Evidence and model lineage in the five reaction episodes

A fresh review of the five saved public packets found meaningful prospective
evidence for particular fitted models. It also found that some final predictors
changed the parameters used in those earlier checks. Prediction scores, earlier
validation residuals and scientific claims therefore need separate provenance.

The reviewer read exported public observations, notes, analysis results and
candidate source as inert text. It did not see private truth or scores, execute
candidate code, fit a model or run a simulation. All packets have export gaps.
The review is same-family, provisional and pending external review, with no
canonical integrity audit. Historical scores and depth annotations are retained.

## What each record supports

| Public packet | Strongest relevant saved evidence | Relationship to the final predictor |
|---|---|---|
| `review-core-016` | Useful sparse-network fits and deliberately requested new mixture/event challenges; reported challenge residuals follow an all-data refit | Final literal coefficients materially differ from the audited fit |
| `review-core-017` | An unchanged fitted vector predicts six later mixture/event protocols below a previously stated 0.003 mM RMSE criterion | Final literals copy a later rounded all-data fit; the earlier prospective test remains bound to its earlier vector |
| `review-core-018` | Two numerical contrast predictions precede later matched observations | Final literal coefficients materially differ from the subsequently audited constrained fit |
| `review-core-019` | An unchanged vector predicts four later independent repetitions | Final rates are retained, but activation energies are reconstructed at runtime from embedded model-generated contrasts; equivalence is unresolved |
| `review-core-020` | A basis-only fit predicts records excluded from its objective, after those target records were already visible | Final literal coefficients materially differ from the successful basis-only fits |

In packet 017, round-6 coefficients are copied into round-8 analysis, which
computes errors before refitting. Six saved RMSEs range from 0.00160 to
0.00225 mM. The targets include changed mixtures, temperature schedules,
additions and their combination. The final explanation quotes a later refit
range as if it were this earlier check; the genuine pre-refit result still meets
the stated criterion. This supports scoped transfer of that earlier version.

Packet 019 similarly preserves coefficients before four later observations,
giving saved errors of 0.00208–0.00221 mM. Those physical protocols repeat
earlier conditions with changed sampling grids. This supports independent
replication; it does not by itself demonstrate transfer to a new physical regime.
The review did not execute the final energy-reconstruction routine, so it makes
no claim about its numerical equivalence or final prediction error.
Both saved RMSE summaries include the assigned t=0 rows; these are archived
diagnostics, not errors recomputed on later free readouts alone.

Packet 018 has two point contrasts recorded before matched observations. Saved
observed-minus-predicted differences are approximately +0.000953 and
−0.000546 mM. Broad event residuals reported later follow refitting and have a
different evidential status.

The final coefficient changes are substantive in several records. For example,
packet 016 changes a saved C→D rate/energy pair from approximately
`(0.0407794, 35793)` to `(0.022, 31500)` in units of s⁻¹ and J/mol. Packet 018
changes B→A from approximately `(0.0599825, 38807)` to `(0.025, 18000)`.
Packet 020 changes D→B from approximately `(0.112963, 38844)` to
`(0.05, 34000)`. Earlier residuals cannot be silently attributed to these changed
predictors. This source comparison alone does not measure whether a change
improves or worsens prediction.

## Supplied theory and unresolved alternatives

All five public problems supply reversible first-order transfer, conservation,
detailed balance and the Arrhenius temperature law. The empirical work concerns
topology, coefficients, effects and adequacy within that family. It does not
establish discovery of those supplied laws; see the [public-prior
inventory](../PUBLIC_PRIORS.md).

Packet 017 contains informative topology-deletion comparisons, but the dense
fit imposes a positive lower bound on every included edge. Removing a pair can
therefore improve the fit without constituting an unrestricted nested comparison.
Later uncertainty estimates also leave sufficiently weak exchange unresolved.
Finite noisy data do not prove an exactly absent edge or unique microscopic
network.

## Trace anchors and next interface requirement

The five structured private reviews retain exact JSON pointers and source
extracts. Key public-packet locations are the `fit_vector` in packet 017 round
6, `validation_preregistered_rmse` in round 8, `theta` in packet 019 round 7,
`validation_rmse` in round 9, and packet 018 round-6 contrast results. Final
source resides at `/final_candidate/submission/predictor_code`. Recorded round
order is not independently authenticated wall-clock chronology.

Future runs should preserve candidate-selected fitted snapshots and bind each
prospective test to one immutable version. Final reporting should identify
which version was tested and explicitly label later revisions. Existing snapshot
and prospective modules provide engineering support for that workflow; these
old traces do not establish that GPT will use them or benefit from them.
The missing evidence requires a new interface cohort, not rewriting old scores.
