# The evolvability gap is not budget-invariant, and it can reverse

Date: 2026-08-09. Same protocol as `evolvability_gap_2026-08-09.md`: paired
`normal` versus `selection_blind`, `greedy_rewrite`, `gpt-5.6-sol`, real sandbox. The only
change is the proposal budget.

## The result

| task | budget | pairs | normal | blind | Delta (full) | 95% CI | W/T/L | token ratio |
|---|---:|---:|---:|---:|---:|---|---|---:|
| MolecularLeadOptimization | 3 | 8 | 0.7151 | 0.4044 | **+0.3107** | [+0.130, +0.492] | 7/0/1 | 1.33 |
| MolecularLeadOptimization | 10 | 6 | 0.8763 | 0.9695 | **−0.0932** | [−0.359, +0.172] | **1/0/5** | 1.72 |
| QuantumErrorDecoder | 3 | 8 | 0.8814 | 0.7470 | **+0.1345** | [+0.067, +0.202] | 8/0/0 | 1.26 |
| QuantumErrorDecoder | 10 | 6 | 0.9490 | 0.8694 | **+0.0796** | [+0.038, +0.121] | 6/0/0 | 1.52 |

At the token-matched endpoint, budget 10 gives −0.1327 on Molecular and +0.0517 on QEC, the
latter with a CI of [−0.021, +0.124] that now includes zero.

**On Molecular the sign flips: at budget 10 the open-loop control wins five of six paired
seeds.** On QEC the gap survives but shrinks by 41%, and its token-matched version loses
significance.

This directly contradicts the expectation stated in the budget-3 note, which was that the gap
should widen because best-of-N saturates. It does not, and the previous note's claim boundary
line "larger budgets preserve the gap — untested" is now answered: **no**.

## Why

Two mechanisms, both visible in the data.

**Best-of-N gets genuinely stronger.** On Molecular the control reaches 1.3252, 1.3363 and
1.2928 on seeds 2, 3 and 5 — above the approved-drug anchor. The per-draw score distribution has
a long right tail, and ten independent draws sample that tail while three do not. The control
mean rises from 0.4044 at budget 3 to 0.9695 at budget 10.

**Single-incumbent feedback locks in.** The feedback arm's variance is much larger at budget 10
(sd 0.3231 versus the control's 0.3528 but with a far worse floor: seed 1 ends at 0.3552). A
greedy loop commits to one incumbent and keeps editing it; if the first accepted candidate sits
in a poor basin, ten steps of refinement cannot leave it, whereas an independent sampler simply
draws again from the full distribution.

**And feedback's overhead compounds.** The token ratio grows with horizon on both tasks, 1.26 to
1.52 and 1.33 to 1.72. Reading results costs context, that cost accumulates, and at matched
tokens the feedback arm affords relatively fewer effective steps the longer the run goes.

## What this does and does not say

It is a result about **`greedy_rewrite`**, not about feedback in general. Single-incumbent hill
climbing with no population, no archive and no novelty pressure is the weakest possible
instantiation of iterative search, and its collapse is predicted: the project's own literature
matrix cites Gurkan et al. 2026, where over 93% of mutations revisit an earlier structural form
in 87% of chains. Avoiding exactly this is why AlphaEvolve-class systems maintain program
databases and island models.

Supporting contrast from the same session: OpenEvolve on QuantumErrorDecoder does not flatline
the way greedy does. Its per-step scores over eleven steps are
`0.831, 0.713, 0.000, 0.673, 0.779, 0.917, 0.917, 0.939, 0.939, 0.939` — real exploration,
including failed candidates, with the incumbent climbing in three stages to 0.9392. That is what
population search buys, and it is the arm this comparison is still missing.

## Consequences for the benchmark design

1. **The evolvability gap must be reported as a function of budget, not as a scalar.** A task
   admitted on a budget-3 gap can lose it entirely by budget 10. Any admission rule of the form
   "Delta > 0" is underspecified without the budget and the searcher.
2. **The crossover point is itself the interesting measurement.** Where best-of-N overtakes a
   given searcher characterises the searcher, and comparing that crossover across searchers is a
   sharper instrument than a single gap number.
3. **This strengthens the case for running the population backends.** The most likely reading is
   that greedy's crossover is early and a population searcher's is much later; that is a
   prediction, and it is testable with the machinery now working.
4. It also re-frames the project's Track F null. That study used greedy at budget 3 on a task
   whose control already sat at 0.797 — a regime where, on this evidence, greedy has little room
   and independent sampling is competitive.

## Claim boundary

| Claim | Status |
|---|---|
| The gap shrinks with budget on both tasks | Supported, 6 pairs each at budget 10 |
| The gap reverses on Molecular at budget 10 | Observed, 1/0/5, but the CI spans zero — direction is suggestive, magnitude is not established |
| The gap survives on QEC at budget 10 | Supported at full horizon, CI excludes zero; **not** supported token-matched |
| This is a property of feedback in general | **Not supported.** It is a property of single-incumbent greedy search |
| A population searcher would behave differently | Untested prediction |
| Anything beyond budget 10 | Untested |

Six paired seeds per cell at budget 10 versus eight at budget 3. Intervals are normal
approximations on small samples.
