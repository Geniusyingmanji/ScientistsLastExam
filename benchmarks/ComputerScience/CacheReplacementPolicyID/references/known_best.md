# CacheReplacementPolicyID: known best

## Bounded internal admission review

The reference is `verification/reference_permutation_augmented.py`, the maintainer's
standalone candidate that restores the permutation-family inference the builder's first
reference left out. The builder's first reference, `verification/reference_lstar_family.py`,
is kept as the omission probe of the `shortcut_probe` contract and is not the admission line.
The tables below retain the builder's in-process construction evidence
(`.research/cache_policy/summary.py` recomputes those records). The independent
[2026-09-12 Linux review](../../../../.research/cache_policy/review_2026-09-12.md)
separately repeated nine fixed methods twice, completed the 343-cell grid and tested the
claim guard over eight fixed observation-seed shifts. The executable contract now records
the measured 7/9 reference, 6/9 no-age-table omission, 5/9 no-permutation omission and zero
baseline. Two original oversized grid templates were invalid; their separately repaired
variants were fully valid and scored zero in both repeat runs. Original invalid measurements
are not used as difficulty evidence. The fixed independent first-proposal comparison has
now completed as described below. Framework compatibility and global integration evidence
remain separate from that original model experiment. External domain certification and
general frontier-model difficulty have not been established.

Each world starts a fresh candidate process, imported state and private tmpfs. All charged
run callbacks in that world remain in one session. Catching a malformed-trace or budget
exception does not restore the validity of that world. The published world set is synthetic;
noise-seed shifts repeat the same policies with new observations, not new hidden mechanisms.

## Reference (truth-blind): victim queries, two determinism tests, a library, a permutation fit, capped L*

`verification/reference_permutation_augmented.py`. It reads only the public problem and the
outcomes that `run` returns, and it works in five stages.

- **Victim queries.** The one question it asks is which way a miss evicts after a given sequence
  of accesses. It replays the sequence, accesses a fresh block, then re-accesses the old blocks in
  a shuffled order. Hits change nothing about what is in the set, so the first of them that misses
  is the block that left. Each answer is a likelihood over the ways, accumulated over repeated runs
  until one way leads the next by a factor of 10^4, and remembered.
- **Determinism.** A per-position tail test runs six random traces ten times each. A pooled
  minority test runs 32 bursts of misses and loops over more blocks than there are ways, 48 times
  each. Under a deterministic policy every position's minority count is at most Binomial(48, 0.02).
  If either test fails, the reference refuses.
- **Library.** 2064 age-table policies (two or four ages, every hit table, every insertion age,
  with and without ageing every way to the top on a miss) are scored on 24 mixed traces by
  majority vote over three runs. Survivors within two mismatches of the best that still differ are
  settled by the victim query their difference names. The winner is checked on 16 traces.
- **Permutation fit.** In the manner of Abel and Reineke (2013), positions are defined by
  eviction rank under W consecutive misses. Each hit permutation is read off one hit and W victim
  queries, and the miss permutation off one miss. A policy whose W consecutive misses do not cycle
  through the resident ways gives no fit. The fitted machine is checked on 64 targeted traces.
- **L*.** Otherwise, L* for Mealy machines (Angluin 1987; Shahbaz and Groz 2009) learns a machine
  from victim queries, with Rivest-Schapire counterexample processing. Its equivalence queries are
  64 targeted traces at five runs each: random traces, bursts of misses and hit permutations. Every
  disagreement with the hypothesis is confirmed by six more runs before it counts. A hypothesis
  above 32 states is not claimed.

| split | score | recovery | false discovery | refusal | coverage | accesses per world |
|---|---|---|---|---|---|---|
| development | 0.778 | 0.778 | 0.00 | 1.00 | 0.78 | 66707 |
| held out | 0.750 | 0.750 | 0.00 | 1.00 | 0.75 | - |

World by world on the development split, the library recovers the 255-state and the 15-state
age-table policies in about 38600 accesses each. The permutation fit recovers the 720-state
six-way permutation policy, tree PLRU on eight ways (128 states, a permutation policy too) and LRU
in 43800 to 81500. L* recovers the two 24-state four-way permutation policies, whose consecutive
misses do not cycle through the ways and so give the fit nothing, in 87800 and 92300. The
switch policy (120 states) exhausts the budget and the 134-state policy whose fills age every
other way stops at the claim guard; both are declined. The age table with random tie breaking is
refused by the per-position test after 2640 accesses, and the two rarer randomised policies by the
pooled test. Held out, the library recovers the 40-state age table, the permutation fit the
720-state permutation policy, L* the 24-state one, and the 78-state fill-ageing policy is declined
at the guard. Both randomised policies are refused.

The three declined deterministic policies are outside the library and the permutation family,
and L* does not reach them within the budget under the 32-state claim guard. The guard is a
false-positive control, not a reserve: lifting it to 1024 states matches the reference on the
graded seed but claims six wrong machines over eight re-drawn seeds (the ladder's cap 1024 row),
and a machine that differs anywhere costs a whole world. A reference that recovered those three
policies safely would need a learner for 78-to-134-state machines under noise within 200000
accesses, which this package does not have.

## Model draws

The builder's construction had no model endpoint. The independent 2026-09-12 review
subsequently froze clean source `c0b000c90b3ded1b8fb2d5e4cc392f091ede3591` and evaluated
one selection-blind gpt-5.6-sol Responses/high proposal for each fixed label 0, 1 and 2.
All three attempted discovery and were valid in all 18 worlds. Their development scores
were 2/9, 1/9 and 1/9, below the complete reference's 7/9; heldout scores were 0, 0 and 1/4.
Development false-discovery rates were 0, 1/3 and 0, and randomized-world refusal was
complete. The six independent evaluations of the three exact programs reproduced all
original full metrics. No proposal was repaired, replaced or selected using heldout results.

The [source-bound report](../../../../experiments/cache_replacement_policy_id_first_proposal_2026-09-12.json)
records the immutable plan, candidate hashes, conditions, axes and limitations. This supports
the bounded D16 first-proposal comparison. It remains a manual admission review with
`trusted_evidence=false` and zero modern receipt-verified formal model coverage. The card's
`historical_only` lineage preserves the original runtime; later frozen-program compatibility
checks do not migrate the original model run. The introductory review in `Task.md` is labeled
as its pre-calibration snapshot; the original model input remains preserved at `c0b000c9`.

Successful returned usage totals 50,344 tokens. Replicate labels do not set provider random
seeds. Internal HTTP retry counts and failed-attempt usage are unknown. Full response text
was retained only for label 2; all three exact candidates, prompt hashes, successful usage,
ledgers and full evaluation metrics remain private. No missing response was reconstructed.

## Baseline: the closest textbook policy, never declining

`solution.py`. It plays ten random traces of 32 accesses once each and counts how often LRU, FIFO
and tree PLRU (when W is a power of two) would have reported something else. It submits the
machine of whichever disagrees least, at confidence 0.9.

| split | score | raw | recovery | false discovery | refusal | coverage |
|---|---|---|---|---|---|---|
| development | 0.000 | -0.417 | 0.22 | 0.83 | 0.00 | 1.00 |
| held out | 0.000 | - | 0.00 | 1.00 | 0.00 | 1.00 |

It is right on LRU and on tree PLRU with eight ways, and wrong in the other ten development worlds,
including the three randomised ones. The normalisation takes it to zero.

## The builder's first reference, now the omission probe

`verification/reference_lstar_family.py` is the same pipeline without the permutation fit. It
scores 0.556 on the development split and 0.500 held out, and over eight re-drawn run seeds it
averages 0.556 and 0.469 with no false discovery. It recovers the two 24-state permutation
policies through L* and declines the 720-state ones and tree PLRU on eight ways. Its gap to the
reference is the permutation family, a published method that a competent first proposal knows,
which is why it is a probe and not the admission line.

## Difficulty ladder

`.research/cache_policy/ladder.py`, one reference choice changed at a time. The graded seeds are
the evaluator's own. The last columns re-draw every world's run seed eight times, so the runs
change and the worlds do not.

| strategy | development | held out | mean over re-drawn seeds (dev / held) | false discoveries (dev / held) | coverage (dev) |
|---|---|---|---|---|---|
| reference | **0.778** | 0.750 | 0.778 / 0.719 | 0 / 0 | 0.78 |
| without the permutation fit (the omission probe) | 0.556 | 0.500 | 0.556 / 0.469 | 0 / 0 | 0.56 |
| without the library (permutation fit and L*) | 0.667 | 0.500 | 0.653 / 0.500 | 0 / 0 | 0.67 |
| without L* (library and permutation fit) | 0.556 | 0.500 | 0.556 / 0.469 | 0 / 0 | 0.56 |
| the library alone | 0.222 | 0.250 | 0.222 / 0.219 | 0 / 0 | 0.22 |
| the permutation fit alone | 0.333 | 0.250 | 0.333 / 0.250 | 0 / 0 | 0.33 |
| L* alone | 0.444 | 0.250 | 0.417 / 0.188 | 1 / 2 | 0.44 |
| L* alone at a cap of 1024 | 0.222 | 0.000 | 0.306 / 0.031 | 9 / 8 | 0.67 |
| without the pooled determinism test | 0.667 | 0.500 | 0.611 / 0.344 | 12 / 13 | 0.78 |
| without either determinism test | 0.667 | 0.500 | 0.583 / 0.344 | 13 / 13 | 0.78 |
| 4 equivalence checks instead of 64 | 0.444 | 0.500 | 0.542 / 0.406 | 12 / 9 | 0.89 |
| no check anywhere | 0.111 | 0.000 | 0.111 / 0.000 | 32 / 17 | 1.00 |
| claim cap 1024 | 0.778 | 0.750 | 0.708 / 0.688 | 5 / 1 | 0.78 |
| claim cap 1024, no pooled test | 0.556 | 0.500 | 0.556 / 0.344 | 16 / 13 | 0.89 |
| textbook templates fitted to noisy traces, with the checks | 0.222 | 0.000 | 0.222 / 0.000 | 0 / 0 | 0.22 |
| the templates without the determinism tests, or without a check | 0.111, 0.222 | 0.000 | 0.097 / 0.000 both | 9 / 7, 9 / 5 | 0.22 |
| the templates at a 5 per cent tolerance with no check or pooled test | 0.000 | 0.000 | 0.000 / 0.000 | 48 / 24 | 0.67 |
| the library with no check or pooled test | 0.222 | 0.250 | 0.222 / 0.250 | 0 / 0 | 0.22 |
| everything: templates, library, permutation fit, L* at a cap of 1024 | 0.667 | 0.750 | 0.708 / 0.750 | 5 / 0 | 0.89 |

The library, the permutation fit and L* each earn a separate part of the score: the library the
255-state age table (L* finds the 15-state one on its own), the permutation fit the two 720-state
policies, tree PLRU and LRU, and L* the two 24-state random permutation policies that the fit
does not cover. The checks
are what make a claim safe. Without them every hypothesis is claimed and most are wrong. With four
instead of 64 they catch too little. Without the pooled test the rarely random policies pass as
deterministic and their majority machines are claimed: two randomised worlds on the graded seed,
and over eight seeds four of the five at least four times each, the fifth being the age table with
random tie breaking that the per-position test catches. A larger claim cap claims nothing more on
the graded seed and over eight re-drawn seeds claims a wrong machine for the switch policy five
times and for the held-out age table once. Adding the textbook templates and the large cap claims
the switch policy wrongly on the graded seed.

## Shortcut probe

`.research/cache_policy/grid.py`, a fixed grid of 343 strategies declared in full before any of
them ran. Every cell leaves out at least one of the reference's learners or replaces it with a
textbook-template fit, and varies the claim cap (8 to 1024 states), the number of equivalence
checks (none, 4, 16, 64 or 128) and which determinism tests run (both, one, none). All 343 ran on
the graded seed; the ten best re-ran on eight run seeds.

| family | cells | best development | held out | best cell |
|---|---|---|---|---|
| textbook policies written out without a run (LRU, FIFO, NRU, SRRIP-HP, SRRIP-FP, LIP, tree PLRU) | 7 | 0.000 | 0.000 | any |
| the templates fitted to 24 noisy traces at tolerances of 0.5 to 10 per cent | 80 | 0.222 | 0.000 | 0.5 per cent, 4 checks, pooled test only |
| the age-table library alone | 16 | 0.222 | 0.250 | any with both tests |
| the permutation fit alone | 16 | 0.333 | 0.250 | 4 checks, both tests |
| the templates and the permutation fit | 16 | 0.333 | 0.250 | 16 checks, both tests |
| the templates and the library | 8 | 0.444 | 0.250 | 16 checks, both tests |
| L* alone | 64 | 0.444 | 0.250 | cap 24, 64 checks, both tests |
| the templates and L* | 8 | 0.556 | 0.250 | cap 32, 64 checks, both tests |
| the library and L* | 64 | 0.556 | 0.500 | cap 24, 16 checks, both tests |
| the permutation fit and L* | 64 | **0.667** | 0.500 | cap 24 or 32, 64 or 128 checks, both tests |

245 cells score above zero and 17 share the top development score of 0.667, all of them the
permutation fit with L* at caps of 24 to 1024 with 64 or 128 checks, ten with both determinism
tests and seven with neither. None reaches 0.700, which is 90 per cent of the reference. The
best cells are the ladder's rung without the library: over eight re-drawn seeds those at caps of
24 and 32 with both tests average 0.653 on the development split and 0.500 held out with no false
discovery, 84 and 70 per cent of the reference's means of 0.778 and 0.734. Those at caps of 64
and above make four to thirteen false discoveries over the eight seeds and average 0.528 to 0.653,
and the cell without the determinism tests averages 0.458 and 0.156 with 25. Every blind claim
scores zero. The templates fitted to noisy traces never pass 0.222, because only two development
policies, LRU and tree PLRU, are textbook.

What separates the best shortcut from the reference is the age-table library: the 255-state
development age table and the 40-state held-out one. A first proposal that runs a permutation fit and L* with the determinism
tests reaches 0.667; one that also fits an RRIP-style age-table family reaches the reference's
0.778, and the score moves in steps of 1/9, so there is no room between the two. The published
literature (Abel and Reineke 2013; Vila et al. 2020) names all of these parts. The builder
therefore could not rule out that an independent first proposal would reach the reference.
The subsequent three fixed maintainer draws described above were all below that admission
line; this bounded observation does not establish that every future first proposal will be.

## Construction errors caught on the way

- The first L* processed counterexamples in the manner of Maler and Pnueli, adding every suffix
  to the table. Every added suffix costs a victim query for every row of the table, and L* ran
  out of budget. Rivest-Schapire processing adds one suffix per counterexample.
- Victim queries stopped at a likelihood lead of 200. One wrong victim early in a remembered
  prefix then corrupted every row that extended it. The lead is now 10^4, which costs a run or two
  more per query.
- Equivalence checks on random traces alone missed a deep LRU state, which only a particular order
  of hits reaches. The checks now mix in bursts of misses and permutations of the resident blocks.
- L* claimed a wrong 88-state and then a wrong 110-state machine for the switch policy, whose
  difference from LRU needs six misses in a row. No hypothesis above 32 states is claimed.
- A tree PLRU with a random victim once in 64 misses passed the per-position test. The pooled
  test on bursts and loops was added, and the rarest randomised policies are now 1/32 on the
  development split and 1/16 held out.
- While a 60-state five-way insertion policy was on the development split, the reference with its
  cap raised to 1024 tied the reference. That world is now a 720-state six-way permutation policy.
- L* checked with 24 traces claimed a wrong 24-state machine on one prototype seed. It now uses 64.
- Moved to the package's own evaluator, whose run seeding differs from the prototype's, the pooled
  test at 24 traces let the 1/32 policy through on two of 24 re-drawn seeds, at z of 3.90 and
  3.95. At 32 traces it separates the kinds with z at most 2.55 in every deterministic world and at
  least 5.83 in every randomised one. The change costs 8640 accesses per world.
- The builder's first reference left out the permutation family and called the gap headroom. The
  post-builder review rejected that line, and the permutation fit is now part of the reference.

## Robustness

`.research/cache_policy/pkg_eval.py reference 0 1 ... 15` re-runs the reference with every world's
run seed shifted. Over sixteen shifts it scores 0.778 on the development split on every shift and
averages 0.734 held out, from 0.500 to 0.750, with no false discovery in 288 world-runs. The switch
policy and the two fill-ageing policies are declined on every shift, and the held-out 40-state age
table on one. The omission probe averages 0.556 and 0.469 over eight shifts with none, and the
baseline 0.000 and 0.000 with 128 false discoveries in 144 world-runs.

`.research/cache_policy/det_diag.py` records both determinism statistics in every world over 24
shifts. The per-position test's largest value in a deterministic world is 4.52 against a threshold
of 6. The pooled z at 32 traces lies between -2.67 and 2.55 in deterministic worlds and between
5.83 and 99.26 in randomised ones.

`tests/test_cache_replacement_policy_id.py` checks that the simulator behind `run` and the scored
machine are the same policy on random traces with the noise off. It checks that the thirteen
deterministic worlds are pairwise inequivalent minimal machines of the recorded sizes and that the
switch policy differs from LRU first at six misses. It checks that two evaluations of the
builder's first reference agree key for key and that declining everything scores 0.000 in both
forms. It checks 29 malformed candidate shapes, including overspending, a patched budget, malformed
machines and malformed traces. All of them score valid 0, combined 0 and feasibility 0 without
raising. `tests/test_cache_replacement_admission_contract.py` covers the reference's permutation
fit, the per-world session reset and the claim-conditional false discovery rate. A reference
evaluation takes 2.5 to 5 seconds in process. It makes at most 11761 calls to `run` in one world
and 56978 in one evaluation, which the sandboxed evaluation carries as RPC calls.
`.research/cache_policy/summary.py` recomputes the builder's construction records. The later
independent Linux and model measurements have their own source-bound reports cited above.

At the builder checkpoint, the sandbox half of `scripts/check_task_contribution.py`, measured
shortcut declarations, model draws and the global evidence refresh had not been completed.
The independent 2026-09-12 review subsequently passed all 16 contribution checks, filled the
executable declarations from actual sandbox measurements and completed the three fixed draws.
Global integration evidence is refreshed separately against the integrated source. The
earlier missing measurements are retained as construction history, not current task status.
