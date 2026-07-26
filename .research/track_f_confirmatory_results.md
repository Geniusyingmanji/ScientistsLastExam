# Track F confirmatory result and design implications

Status: complete, 2026-07-26 UTC. This note is a claim--evidence audit of the frozen Track F
study. The preregistration, search report, public confirmation projection, and analysis report
are the numerical sources of record. It does not replace those machine-readable artifacts.

## Frozen evidence chain

| Stage | Artifact | Result |
|---|---|---|
| Preregistration | `experiments/track_f_preregistration_2026-07-26_v1.json` | SHA-256 `c26d39d35386f295192d369a3948002b5c40b967aa922a45fb1d1bab8e729d32`; one powered primary fixed before outcomes |
| Search | `experiments/track_f_search_2026-07-26_v1.json` | 384/384 cells and 1,152/1,152 proposals; no infrastructure failure or retry |
| Fresh confirmation | `experiments/track_f_confirmation_2026-07-26_v1.json` | 768 endpoints, 490 unique artifacts, and 980/980 replay evaluations; no infrastructure failure or stochastic artifact |
| Frozen analysis | `experiments/track_f_analysis_2026-07-26_v1.json` | trusted execution; all invalid endpoints retained at the fixed score floor |

The public confirmation report is a hash-bound projection of the complete local report. It
removes per-world and per-instance diagnostics that directly echo private panel parameters. The
complete report remains outside Git with mode `0600` and SHA-256
`2f6276b27bdf86a7e80ea235d8f718f52d92cc6170a82a56f9aab725046a888e`. Running the frozen
analyzer on the complete and public reports produced exactly equal scientific result fields.

## Confirmatory result

The powered primary did not identify an advantage for iterative normal feedback over an
equal-token selection-blind proposal batch on fresh ActiveLaw worlds. At the common realized
token endpoint, normal feedback had mean normalized mechanism score `0.781418` (SD `0.090343`,
`n=48`), whereas selection-blind had mean `0.797338` (SD `0.069641`, `n=48`). The preregistered
independent-draw Welch contrast was `-0.015920` with 95% CI `[-0.048638, 0.016798]`, two-sided
`p=0.336216`, and Hedges' `g=-0.195797`. The estimate was opposite the preregistered positive
direction and did not approach the design MDE of `0.15`.

This result supports a narrow negative conclusion: for the frozen GPT-5.5, greedy-rewrite,
three-proposal, ActiveLaw procedural population, the experiment provides no evidence that the
normal feedback treatment improves fresh mechanism recovery over selection-blind generation at
matched realized tokens. It does not establish equivalence, because the confidence interval still
contains small effects in either direction.

The full-proposal ActiveLaw comparison was also small and descriptive: normal minus
selection-blind was `-0.005388` with 95% CI `[-0.040974, 0.030198]` and `p=0.764050`. This endpoint
was not the powered primary and does not change the confirmatory conclusion.

## Descriptive science stress test

Diffraction remained a high-variance stress test rather than a confirmatory second hypothesis.
At the common-token endpoint, fresh robustness means were `0.374027` for normal, `0.232567` for
score-only, `0.315939` for delayed replay, and `0.307938` for selection-blind. The corresponding
SDs were `0.364530`, `0.281739`, `0.340061`, and `0.323697`; every condition reached the score
floor, and three reached the ceiling. Normal minus selection-blind was `0.066089` with 95% CI
`[-0.073649, 0.205827]` and descriptive `p=0.350056`.

Normal minus score-only at this endpoint had descriptive `p=0.036183`, but it was one of many
unadjusted secondary contrasts and was explicitly outside the confirmatory claim set. It must not
be promoted to a positive feedback finding.

Search candidate validity was task dependent. ActiveLaw produced 568 valid proposals out of 576,
whereas Diffraction produced 336 valid proposals out of 576. These are scientific candidate
outcomes rather than infrastructure failures. Confirmation retained four deterministically invalid
unique artifacts, corresponding to seven invalid endpoints after endpoint-to-artifact reuse.

## What the experiment suggests about agent optimization

1. **Feedback value must be measured net of its context cost.** At the full horizon, ActiveLaw
   normal consumed a mean `21,458` tokens versus `14,480` for selection-blind. At the common-token
   endpoint, normal completed a mean `1.96` proposal steps while selection-blind completed all
   three. The treatment therefore changes both information and the number of affordable search
   opportunities. Equal proposal counts alone are not a fair resource comparison.
2. **A capable one-shot proposal distribution can dominate a short feedback loop.** On ActiveLaw,
   all four fresh full-horizon means lay between `0.784228` and `0.797338`; selection-blind was not
   worse than the feedback treatments. This is evidence about this short frozen regime, not a
   general statement that scientific feedback has no value.
3. **Validity and tail behavior are part of performance.** Diffraction's SD was close to its mean,
   and search validity was only `58.3%`. Mean best score alone would hide how often the agent
   produces unusable scientific artifacts and how much performance depends on rare high-scoring
   proposals.
4. **Fresh replay is a separate gate from search improvement.** The confirmation phase evaluated
   the declared artifacts on precommitted fresh mechanism and physical panels, replayed every
   unique artifact twice, and retained invalid artifacts. Search curves without this gate cannot
   support transfer, robustness, or discovery claims.
5. **Feedback effects are task and endpoint specific.** ActiveLaw and Diffraction use different
   scientific axes and show different descriptive patterns. Averaging them into one score would
   erase mechanism recovery, physical robustness, validity, and resource differences.
6. **Many independent model draws are necessary.** The 48-draw conditions still produced wide
   Diffraction intervals. A few seeds or the best trajectory would have supported unstable and
   potentially opposite narratives.

## Claim boundary

| Claim | Evidence status | Allowed statement |
|---|---|---|
| Normal feedback improves ActiveLaw at equal tokens | Rejected by the preregistered test | No identified improvement; estimate `-0.015920`, `p=0.336216` |
| The treatments are equivalent | Not tested with an equivalence margin | Do not claim equivalence |
| Normal beats score-only on Diffraction | One unadjusted descriptive contrast | Report descriptively only; no significance claim |
| A general scientific-agent feedback effect exists | Two heterogeneous tasks, only one powered primary | Unsupported |
| Independent physical or laboratory validation is complete | Fresh local procedural simulators only | Unsupported |
| Autonomous scientific discovery was demonstrated | No novelty, external replication, or real-world discovery gate | Unsupported |

## Consequences for the approximately 50-task portfolio

Every task counted toward the scientific portfolio should now satisfy the following minimum
contract in addition to oracle and sandbox integrity:

- a declared scientific role: optimization, mechanism/discovery, or replication, without silently
  averaging heterogeneous axes;
- a legal weak baseline, a truth-blind domain reference, and measurable non-saturated headroom;
- development, sealed, and fresh confirmation worlds or an explicitly justified equivalent;
- failure-inclusive validity, safety, false-discovery/refusal, generalization, and scientific-utility
  fields rather than one scalar score;
- normal, selection-blind, and independent-restart controls with both full-horizon and common-cost
  endpoints;
- fixed risk sets, several independent provider draws, all-result ledgers, and no best-seed
  selection;
- deterministic replay or a preregistered stochastic aggregation rule, with infrastructure failure
  separated from candidate invalidity;
- an aggregate-only public confirmation projection that cannot reveal sealed world parameters;
- independent simulator, data-source, or domain review before physical or scientific validation
  language; and
- explicit builder/model lineage so task construction with GPT-5.5 is not mistaken for held-out
  model evaluation.

The current inventory therefore remains `7 certified / 43 candidate / 9 quarantined`. Fifty tasks
are internally runnable and scientifically motivated, but this Track F result does not upgrade the
43 candidates to certified status. Each candidate must pass the portfolio contract above, and only
the measurement-healthy subset should enter later 2/6/12-hour scaling curves.
