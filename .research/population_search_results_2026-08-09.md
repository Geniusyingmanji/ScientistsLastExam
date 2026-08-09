# Population search after the censoring fix

Date: 2026-08-09. OpenEvolve 0.2.26, `gpt-5.6-sol` over the chat wire, real sandbox, code-length
cap raised from 10,000 to 64,000 characters. Zero candidates discarded in any run below.

## 1. The censoring fix changes the answer, not just the process

`QuantumErrorCorrection/QuantumErrorDecoder`, budget 40, seed 0:

| run | discarded | evaluated | best |
|---|---:|---:|---:|
| before the fix | **29 of 40** | 12 | 0.9392 |
| after the fix | **0 of 40** | 41 | **0.9932** |

Best-so-far trajectory: `0 → 0.652 → 0.791 → 0.833 → 0.970 → … → 0.9932`, with long plateaus
between staged improvements. 3693 s wall.

So the earlier 0.9392 was not a plateau and not a capability measurement; it was the default
configuration throwing away 29 of the model's 40 candidates because a surface-code decoder does
not fit in 10,000 characters. **A silent default moved the reported score by 0.054 on a task
whose whole scoring range above the reference decoders is about 0.6.**

For context on the same task: the shipped baseline is 0, the two numpy/scipy reference decoders
reach 0.2395 and 0.3832, greedy at budget 10 averages 0.9490, and the PyMatching anchor is 1.0.
OpenEvolve at budget 40 gets within 0.007 of the anchor without reaching it.

That is a well-behaved flagship result: the anchor is approachable under real search but is not
free, which is exactly the property `CirclePacking` turned out to lack.

## 2. Does a population searcher avoid greedy's budget-10 reversal?

The budget-dependence note found that on `MolecularLeadOptimization` at budget 10, greedy's gap
reversed — the open-loop control won five of six paired seeds. The proposed explanation was that a
single incumbent locks into a basin while independent sampling keeps drawing from a long right
tail. If that is right, a population searcher should not reverse.

Same task, same budget, same control:

| arm | mean | n | relative to control |
|---|---:|---:|---:|
| `selection_blind` (open loop) | 0.9695 | 6 | — |
| `greedy_rewrite` normal | 0.8763 | 6 | **−0.0932** |
| OpenEvolve | **0.9881** | **4** | **+0.0186** |

Per seed, OpenEvolve scored 0.6740, 1.3241, 1.2400, 0.7144.

**Directionally this is what the hypothesis predicts**: greedy falls below the open-loop control
while the population searcher does not. The qualitative distinction is the one that was
predicted, and it is the first evidence for it.

**It is not established.** Four usable seeds with a standard deviation of 0.2958 give a standard
error near 0.15, so a 0.019 difference from the control is far inside the noise; the arms are not
seed-paired because two OpenEvolve runs crashed; and n=4 against n=6 is unbalanced. The honest
statement is that the reversal seen with greedy **did not reproduce** with a population searcher,
not that a population searcher is better.

## 3. The sidecar defect is reproducible, not rare

Two of six OpenEvolve runs on Molecular (seeds 1 and 4) died identically:

```text
File "frontier_science/algorithms/openevolve_backend.py", line 191, in openevolve
  metrics = load_full_metrics(...)
FileNotFoundError: missing trusted metric sidecar for candidate <digest>
```

Combined with the earlier attempt, that is 3 failures in 9 OpenEvolve runs on this task — about a
third. The candidate is evaluated and then its trusted metric sidecar cannot be found. This has to
be fixed before any OpenEvolve study can be seed-paired, because losing a third of cells at
random destroys pairing and biases whatever survives.

It did not occur in either QEC run, so it may be task- or timing-dependent.

## What to do next

1. Fix the sidecar defect. Nothing else about population search can be measured cleanly until
   cells stop disappearing.
2. Repeat the Molecular comparison seed-paired with enough replicates to resolve a difference of
   about 0.1 against a standard deviation of 0.3 — on the order of 30 seeds per arm, or a
   variance-reduction design.
3. Re-run the crossover measurement with OpenEvolve at several budgets. The interesting quantity
   from the budget-dependence note is where best-of-N overtakes a given searcher; greedy's
   crossover is between budget 3 and 10 on this task, and the prediction is that a population
   searcher's is later.
4. Re-check every earlier OpenEvolve number in this repository against the code-length cap. Any
   run made before this fix on a long-artifact task is a lower bound.

## Claim boundary

| Claim | Status |
|---|---|
| The code-length cap censored the earlier QEC run | Established; 29 of 40 discarded, 0 after the fix |
| OpenEvolve reaches 0.9932 on QEC at budget 40 | Single seed, single run |
| QEC's anchor is approachable but not free under real search | Supported by this run plus the reference ladder |
| A population searcher avoids greedy's budget-10 reversal | **Directionally consistent, not established.** n=4, sd 0.30, unpaired, 33% crash rate |
| OpenEvolve is better than greedy | Not tested; the budgets differ (40 versus 10) and the Molecular comparison is underpowered |
