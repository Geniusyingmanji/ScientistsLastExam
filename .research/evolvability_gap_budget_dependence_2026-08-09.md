# The evolvability gap is not budget-invariant, and it can reverse

Date: 2026-08-09. Same protocol as `evolvability_gap_2026-08-09.md`: paired
`normal` versus `selection_blind`, `greedy_rewrite`, `gpt-5.6-sol`, real sandbox. The only
change is the proposal budget.

## The result

### The gap as a function of budget

`MedicinalChemistry/MolecularLeadOptimization`, `greedy_rewrite` against the open-loop control,
seed-paired at every budget:

| budget | pairs | normal | blind | Delta | 95% CI | W/T/L | sign test |
|---:|---:|---:|---:|---:|---|---|---:|
| 3 | 8 | 0.7151 | 0.4044 | **+0.3107** | [+0.130, +0.492] | 7/0/1 | p=0.070 |
| 5 | 8 | 0.9050 | 0.5336 | **+0.3714** | **[+0.148, +0.594]** | **8/0/0** | **p=0.0078** |
| 7 | 8 | 0.7718 | 0.7362 | +0.0356 | [−0.271, +0.342] | 4/0/4 | p=1.000 |
| 10 | 6 | 0.8763 | 0.9695 | **−0.0932** | [−0.359, +0.172] | 1/0/5 | p=0.219 |

**The gap is not monotone. It peaks at budget 5**, where it is also the single strongest result
in this study — eight paired wins out of eight, sign test p=0.0078 — then collapses by 90% by
budget 7, reaches parity there (4 wins, 4 losses, p=1.000), and turns negative by budget 10.
Linear interpolation puts the sign change near **budget 7.8**.

So for this searcher on this task there is a real but **narrow window**, roughly budgets 3 to 6,
in which feedback clearly beats matched independent sampling.

### The second task has no crossover at all

`QuantumErrorCorrection/QuantumErrorDecoder`, same searcher, same model, same protocol:

| budget | pairs | normal | blind | Delta | 95% CI | W/T/L | sign test |
|---:|---:|---:|---:|---:|---|---|---:|
| 3 | 8 | 0.8814 | 0.7470 | **+0.1345** | [+0.067, +0.202] | 8/0/0 | p=0.0078 |
| 5 | 6 | 0.8855 | 0.8243 | +0.0612 | [−0.080, +0.202] | 5/0/1 | p=0.219 |
| 10 | 6 | 0.9490 | 0.8694 | **+0.0796** | [+0.038, +0.121] | 6/0/0 | p=0.031 |
| 15 | 6 | 0.9952 | 0.8236 | **+0.1716** | [+0.112, +0.231] | 6/0/0 | p=0.031 |
| 20 | 6 | 0.9554 | 0.8446 | **+0.1107** | [+0.028, +0.194] | 5/0/1 | p=0.219 |

**The gap is positive at every budget from 3 to 20**, with three of five confidence intervals
excluding zero, and it is *largest* at budget 15. There is no crossover in the range where
Molecular's gap had already gone negative twice over.

### So the crossover is a task property, not a searcher property

That was the open question, and the answer is unambiguous. Identical searcher, identical model,
identical protocol; one task crosses near budget 7.8 and the other has not crossed by 20.

The mechanism is visible in the control arms alone:

| arm | budget 3 → max budget | range | shape |
|---|---|---:|---|
| Molecular open loop | 0.404 → 0.970 | **0.565** | climbs throughout |
| QEC open loop | 0.747 → 0.845 | **0.122** | **flat from budget 5**: 0.824, 0.869, 0.824, 0.845 |
| Molecular feedback | 0.715 → 0.876 | 0.190 | no trend |
| QEC feedback | 0.881 → 0.955 | 0.114 | climbs, peaking at 0.995 |

**Best-of-N saturates on QEC and does not on Molecular.** The molecular task's per-draw
distribution has a long right tail — single draws reach 1.33 against a control mean of 0.40 — so
more draws keep finding better portfolios. The decoder task's per-draw quality is bounded by what
one generation can write; drawing again does not produce a dramatically better decoder, while
iteratively refining one does, and the feedback arm climbs toward the matching anchor.

### The admission rule this implies

This is sharper than `Delta > 0`, and it is measurable from the control arm alone:

> **A task measures iterative improvement to the extent that its open-loop control saturates
> with budget.** If best-of-N keeps improving, independent sampling will eventually overtake any
> searcher, and the gap you measure is an artefact of the budget you happened to pick.

That is a one-armed, cheaper test than the paired comparison, it explains both tasks, and it
gives a structural reason for a gap to persist rather than a number that happens to be positive.

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

**And the feedback arm plateaus while the control keeps climbing.** The budget sweep separates
these cleanly. Across budgets 3, 5, 7 and 10 the control rises monotonically —
0.4044, 0.5336, 0.7362, 0.9695, a gain of 0.565 — while the feedback arm stays inside
0.715–0.905, a range of 0.190 with no trend.

That is a more precise account than "greedy locks in". The feedback arm does not fall apart with
budget; **it saturates early, around 0.8–0.9, and best-of-N simply catches up to it and passes
it.** The single-incumbent failure is an inability to keep improving, not a collapse. Seed-level
lock-in still happens — one budget-10 seed ends at 0.3552 after ten steps of refining a poor
basin — but the aggregate movement is the control's, not the feedback arm's.

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

An attempted contrast from the same session **failed to settle it**. OpenEvolve on
QuantumErrorDecoder does show real exploration — per-step scores
`0.831, 0.713, 0.000, 0.673, 0.779, 0.917, 0.917, 0.939, 0.939, 0.939`, with the incumbent
climbing in three stages — but that run turned out to be censored rather than converged:
**29 of its 40 iterations were discarded before evaluation** for exceeding OpenEvolve's default
10,000-character code cap, which a surface-code decoder does not fit under. And the direct test,
OpenEvolve against the same open-loop control on Molecular at budget 10, produced 1.0263 and
0.5932 on two surviving seeds (a third crashed on an adapter defect) against a control mean of
0.9695. Two seeds with a 0.43 spread have no power.

**The population-search explanation now has directional support but is still not established.**
Repeating the comparison with the code-length cap fixed gives OpenEvolve 0.9881 against the same
0.9695 control — that is +0.019 where greedy was −0.093, so **the reversal did not reproduce with
a population searcher**. That is the predicted qualitative distinction. It is not a finding: four
usable seeds with sd 0.2958 put a 0.019 difference well inside the noise, the arms are not
seed-paired because a third of the OpenEvolve runs crash on a reproducible adapter defect, and
n=4 against n=6 is unbalanced. Details and the required follow-up are in
`population_search_results_2026-08-09.md`.

## Consequences for the benchmark design

1. **The evolvability gap must be reported as a function of budget, not as a scalar.** A task
   admitted on a budget-3 gap can lose it entirely by budget 10. Any admission rule of the form
   "Delta > 0" is underspecified without the budget and the searcher.
2. **The crossover is measured, and it is a task property.** With `greedy_rewrite` the molecular
   gap peaks at budget 5 and crosses near 7.8, while the decoder gap is still positive at budget
   20. So a crossover budget characterises a task–searcher pair, never a searcher alone, and it
   cannot be quoted as a single benchmark-wide number.
3. **This strengthens the case for running the population backends.** The most likely reading is
   that greedy's crossover is early and a population searcher's is much later; that is a
   prediction, and it is testable with the machinery now working.
4. It also re-frames the project's Track F null. That study used greedy at budget 3 on a task
   whose control already sat at 0.797 — a regime where, on this evidence, greedy has little room
   and independent sampling is competitive.

## Claim boundary

| Claim | Status |
|---|---|
| The gap shrinks with budget on both tasks | **Refuted.** Molecular: +0.311, +0.371, +0.036, −0.093 at budgets 3, 5, 7, 10. QEC: +0.135, +0.061, +0.080, +0.172, +0.111 at 3, 5, 10, 15, 20 — positive throughout |
| The crossover is a task property, not a searcher property | Supported; identical searcher and model, one task crosses near 7.8 and the other has not crossed by 20 |
| Open-loop saturation explains which tasks keep a gap | Supported on these two; QEC's control is flat from budget 5 (0.824, 0.869, 0.824, 0.845) while Molecular's climbs 0.404 → 0.970. Two tasks is not a law |
| The gap reverses on Molecular at budget 10 | Observed, 1/0/5, but the CI spans zero — direction is suggestive, magnitude is not established |
| The gap peaks mid-range rather than at the smallest budget | Supported on Molecular (peak at 5, p=0.0078) and consistent with QEC (peak at 15) |
| The gap survives on QEC at budget 10 | Supported at full horizon, CI excludes zero; **not** supported token-matched |
| This is a property of feedback in general | **Not supported.** It is a property of single-incumbent greedy search |
| A population searcher would behave differently | **Directionally consistent, not established.** Re-run with the censoring fixed: OpenEvolve +0.019 versus the control where greedy was −0.093, so the reversal did not reproduce — but n=4, sd 0.30, unpaired, 33% crash rate. See `population_search_results_2026-08-09.md` |
| The gap peaks at budget 5 and crosses zero near 7.8 | Supported for this task and searcher; 8 paired seeds at budgets 3, 5, 7 and 6 at 10 |
| Anything beyond budget 10, or the same shape on QuantumErrorDecoder | Untested; QEC has only budgets 3 and 10, both positive |

Six paired seeds per cell at budget 10 versus eight at budget 3. Intervals are normal
approximations on small samples.
