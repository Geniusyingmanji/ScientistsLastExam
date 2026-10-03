# What GPT-5.6 found in the five microbial pilot episodes

This is a descriptive audit of all five `core-c2` microbial episodes, using their
public observation records and candidate text/code. It does not rerun the model,
change the historical scores, or compare a proposed mechanism to an answer key.
The five runs submitted executable predictors and averaged 12.0/100. That low
predictive score does not mean that their investigations were scientifically empty.

Two reviewers in separate fresh contexts each read the same five frozen packets:
75 recorded rounds and 160 public trajectories. Neither received hidden dynamics,
operator scores or prior reviews. Candidate source was read without execution.
Their 30 paired dimension assessments agree; their rationales and exact anchors
remain separate. These are same-family, provisional judgments, pending external
review. Packet exports are partial and recorded order is not authenticated time.

## Supported findings and missing steps

| Episode | What was learned or explicitly proposed | What the evidence does not establish |
|---|---|---|
| 01 | Selective fraction removal changes partner growth. A fixed temperature law, `q(T) = 2^((T-30)/10)`, is proposed before new 25/35 °C tests sampled at matched effective times; the returned trajectories approximately overlap. | The final ODE omits inhibitory feedback and lacks a successful fit/validation lineage. Its near-zero A-effect claim contradicts its own saved contrast. |
| 02 | Selective depletion, dose dependence and community dependence are supported. The late-depletion B effect at 18 h changes from −0.05297 in AB to −0.09308 in ABC. | The final B-dependent suppression term does not identify the extracellular mediator. Pairwise effect magnitude does not transfer unchanged to the full community. |
| 03 | The candidate proposes a fraction with both a beneficial role for C and an inhibitory role for A. Depletion decreases C and increases A, including a test without C. | Direct biochemical action and fitted kinetic constants are unresolved. Another fraction's effect remains outside the final account; two final intervals miss the saved contrasts. |
| 04 | Round 6 code explicitly includes the richest coupled account: nutrient uptake, production/consumption of fractions, inhibition of A, and inhibition of C by a B-associated fraction. Earlier interventions and analysis produced useful numerical contrasts. | The fit times out; the final predictor drops both inhibitory terms. The proposed C-inhibition link lacks a matched isolating intervention. Composing the equations into a full feedback loop is reviewer interpretation, not a validated candidate result. |
| 05 | Primary intervention signs extend to sampled temperature and nutrient changes. An inhibitory explanation is proposed for accelerated growth after depletion. | Direct B inhibition is confounded with mediation through A. “Weak control” and uniformly smaller low-nutrient effects are contradicted by saved data; the final account does not reconcile them. |

The candidate-authored feedback hypothesis in episode 04 is a substantive result
about the exploration trace. It is not evidence that the complete delayed loop
was recovered and validated. No final ODE in these five packets has a recorded
prospective test preserving its complete coefficients. Fraction labels have
meaning within one world only and must not be pooled across episodes.

## Concrete evidence failures

Three conspicuous submitted intervals conflict with the candidate's already
observed, protocol-matched contrasts:

| Episode / readout | Submitted interval | Saved treatment-minus-control value |
|---|---:|---:|
| 01, A at 18 h | [−0.008, 0.008] | +0.090907 |
| 03, A at 12 h | [0.003, 0.1] | +0.296109 |
| 05, B at 24 h | [0.03, 0.13] | +0.151229 |

These are consistency checks against saved measurements, not fresh replicate
outcomes, interval-coverage estimates or replacements for historical verification.
The complete audit retains all 12 submitted intervals, including smaller misses
and agreements. Episode 04 submitted no final numerical claims.

Two temperature-clock diagnostics also used interpolation beyond the available
reference horizon, holding the endpoint constant. Their large hot-temperature
residuals cannot establish a physical boundary of the temperature law. Exact-time
support and extrapolation must be checked before interpreting a residual.

Episode 04 used successful numerical contrasts earlier, but ultimately stated
that measured arrays were unavailable. The frozen runner already allowed early
`submit` and supplied remaining analysis/wall budgets. Its prompt retained all
research notes, the observation catalog and the last two results; older arrays
were accessible through the budgeted analysis namespace. The record therefore
supports an evidence-retention/access problem, not the claim that no data were
ever returned or that early submission was impossible. It does not isolate the
causal contribution of context, tool timeouts and scientific reasoning.

## Consequences for the next task version

1. Keep a bounded evidence ledger available through final submission: observation
   IDs, exact protocols/readout times, successful contrasts, failed predictions
   and immutable candidate-model versions. A typed observation accessor should
   reduce dictionary/matrix errors without suggesting a scientific answer.
2. Record an agent-chosen prospective prediction with exact coordinates,
   coefficients or version hash, uncertainty/tolerance and a subsequent outcome.
   Separate qualitative sign tests from numerical model transfer.
3. Check time matching, reference support and contradictions with cited values.
   These are mechanical relevance checks, not mechanism certification. Preserve
   small disagreements and uncertainty instead of forcing a positive finding.
4. Make the existing early-submit path and active computation allowance clearer.
   Preserve bounded fit progress and let a failed global fit coexist with valid
   local findings. Any improved interface requires a new, separately labelled
   GPT trial; this audit does not demonstrate an improvement.
5. Let the agent choose matched mediator challenges and report a surviving rival.
   Fraction add-back or transfer would be a future public capability, requiring
   mass accounting and identifiability review. The tested batch interface did
   not offer it; it must not be assumed retroactively.

The new all-five review assigns episode 01's empirical-boundary dimension
“not demonstrated”; an earlier seven-world sample review assigned it “partial”.
Both records remain preserved. No ordinal depth grade, discovery-success rate or
historical score was changed. See [scaling readiness](../SCALING_READINESS.md)
for the separate interface, structural-holdout and paired-budget requirements.

## Evidence provenance

The private audit contains the five packet hashes, ten anchored annotations,
saved-value arithmetic, full request/response traces and mechanical comparisons.
Mechanical checks validate references and recorded ordering only.

| Record | SHA-256 |
|---|---|
| Frozen review plan | `2ce03af2d9d94182c28de1bd72e5ff1a89c7675758a094fbb712b3e0bd70068f` |
| Reviewer A seal | `ed7a113d7d457b86cb488dccd8d9c102ec1d7ee7d0b9f6df72b4dba62a5f0eff` |
| Reviewer B seal | `60705567b7b65954fd17a5d9adc36c010593a92a3a9e7f4fce5dc9880daf87f5` |

Raw trajectories, hidden instance identifiers and private evaluation targets stay
outside the public report. Integrity audit is unavailable; external review is pending.
