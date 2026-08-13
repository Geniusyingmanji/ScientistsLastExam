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

Same task, same budget, same control, **seed-paired**, after the crash fixes made every cell
recoverable:

| arm | n | arm mean | control mean | Delta | 95% CI | W/T/L | sign test |
|---|---:|---:|---:|---:|---|---|---:|
| `greedy_rewrite` normal | 6 | 0.8763 | 0.9695 | **−0.0932** | [−0.359, +0.172] | **1/0/5** | p=0.219 |
| OpenEvolve | **12** | 0.8956 | 0.8216 | **+0.0740** | [−0.129, +0.277] | **8/0/4** | p=0.388 |

Per-seed OpenEvolve minus control: `+0.29, +0.18, −0.34, −0.30, +0.12, −0.53, +0.61, +0.32,
−0.27, +0.40, +0.39, +0.02`.

**The reversal did not reproduce.** Greedy falls below the open-loop control and loses five of
six paired seeds; the population searcher stays above it and wins eight of twelve. The
qualitative distinction is the predicted one.

**Nothing here is statistically established.** The OpenEvolve gap is +0.074 with a confidence
interval spanning zero and a sign test at p=0.388. The difference between the two arms' gaps is
0.167, which is smaller than the per-seed spread of roughly 1.1. Twelve seeds are not enough for
this task's variance.

### The interim read was inflated, and why that matters

At n=10 this comparison looked much stronger: +0.1525 with 8 wins and 2 losses. The two missing
seeds were missing because of a crash, not a result — and adding them dropped the estimate to
+0.0740.

The mechanism is not what one would guess. OpenEvolve did *well* on those seeds, scoring 0.990
and 1.034. They became losses because the open-loop control drew exceptionally well there,
1.3252 and 1.3363 against a control mean of 0.82. So the missing cells were not missing at random
with respect to the paired difference, even though they were missing for a purely mechanical
reason.

This is a concrete instance of the concern raised when the sidecar defect was found: cells that
disappear must be recovered, not analysed around. Reporting the n=10 number as if the missing
pair were uninformative would have overstated the effect by a factor of two.

## 3. The sidecar defect is reproducible, not rare

Two of six OpenEvolve runs on Molecular (seeds 1 and 4) died identically:

```text
File "sle/algorithms/openevolve_backend.py", line 191, in openevolve
  metrics = load_full_metrics(...)
FileNotFoundError: missing trusted metric sidecar for candidate <digest>
```

Combined with the earlier attempt, that is 3 failures in 9 OpenEvolve runs on this task — about a
third. The candidate is evaluated and then its trusted metric sidecar cannot be found. This has to
be fixed before any OpenEvolve study can be seed-paired, because losing a third of cells at
random destroys pairing and biases whatever survives.

It did not occur in either QEC run, so it may be task- or timing-dependent.

## What to do next

1. ~~Fix the sidecar defect.~~ Done: upstream evaluator timeouts no longer abort a run, and the
   skipped count is reported as `upstream_unevaluated_programs`. A follow-on contiguity bug in
   that fix is also fixed. All 12 seeds now complete.
2. The Molecular comparison is now seed-paired at n=12 and still not conclusive: the arms differ
   by 0.167 against a per-seed spread near 1.1. Resolving that needs far more replicates than
   twelve, or a variance-reduction design — the same procedural world for both arms, or common
   random numbers across the paired proposals.
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
| A population searcher avoids greedy's budget-10 reversal | **Directionally consistent, not established.** Seed-paired at n=12: +0.074, CI spans zero, sign test p=0.388. Greedy loses 5 of 6, OpenEvolve wins 8 of 12 |
| OpenEvolve is better than greedy | Not tested; the budgets differ (40 versus 10) and the Molecular comparison is underpowered |
