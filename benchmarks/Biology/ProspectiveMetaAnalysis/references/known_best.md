# Known best — ProspectiveMetaAnalysis

## Anchor

`verification/reference_synthesis.py` screens the corpus, pools it, commits a forecast, runs the
one prospective confirmation and updates — through the task's own evaluator, from the supplied
problem alone, never reading the hidden world.

Reproduce with:

```bash
python scripts/measure_reference.py --task Biology/ProspectiveMetaAnalysis \
    --reference verification/reference_synthesis.py --entry synthesize_evidence
```

| | every recorded model proposal | reference |
|---|---:|---:|
| `combined_score` | 0.0000 | **0.9088** |
| `development_preconfirmation_mechanism_score` | 0.0 | **0.9266** |
| `heldout_preconfirmation_mechanism_score` | — | 0.7960 |
| `development_supported_claim_coverage` | 0.0 | 1.0 |
| `development_false_discovery_rate` | 0.0 | 0.0 |
| `development_unsupported_refusal_rate` | 1.0 | 1.0 |
| `development_confirmation_interval_coverage` | — | 1.0 |

## What the reference does

1. **Screen** — eligibility is stated exactly, so it is applied exactly. Records sharing a
   registration are one study reported twice: the registry result is kept as the primary record
   and the group is declared a duplicate, because counting a study twice is what makes a pooled
   estimate confident and wrong. A publication highlighting an outcome other than its own
   preregistered primary is named as a selective report, whether or not its study enters the pool.
2. **Pool** — random-effects meta-regression: DerSimonian-Laird for the between-study variance,
   then weighted least squares for intercept and slope.
3. **Decide** — claim a benefit only when the predicted effect at the decision moderator clears
   the published threshold by more than its own standard error. A point estimate over the line
   with an interval straddling it is not a finding.
4. **Design** — the site whose moderator sits furthest from the centre of existing evidence
   tightens the slope most, at the largest sample size the budget and the site allow on the public
   grid.
5. **Forecast** — a prediction interval for that one new study: the mean's uncertainty widened by
   tau and by the sampling error the chosen size implies. A confidence interval for the mean is
   the usual way this is got wrong, and it is far too narrow.
6. **Update** — refit with the fresh result included.

## Detecting the unsupported family

The published model is linear in the moderator. A corpus that is not needs to be refused, and the
test is to add a quadratic term and ask whether it is needed:

| corpus | curvature t |
|---|---|
| `linear_positive` | 0.17, 0.43, 0.63 |
| `linear_mixed` | 0.24, 0.29, 0.65 |
| `linear_null` | 0.75, 1.32 |
| `nonlinear` | **2.40, 2.86** |

The conventional threshold of 2.0 falls in the gap.

A first version tested something else: whether the pooled effect landed outside the published
effect bounds. It never fired once. A curved moderator relationship still produces perfectly
ordinary effect sizes — the curvature is in how they vary with the moderator, not in how large
they are — so bounds cannot see it, and the reference claimed on every unsupported corpus while
reporting a refusal rate of zero. Replacing the bounds test with the curvature test took the score
from 0.8326 to 0.9088 and the refusal rate from 0.0 to 1.0.
