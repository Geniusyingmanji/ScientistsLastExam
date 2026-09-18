# IsolationLevelAudit: what has been measured

Every number here is recomputed by three scripts in `.research/isolation_level_audit/`, which import
the packaged evaluator, reference, baseline and probes. `summary.py` has six sections: `scores`,
`axes`, `shifts`, `sound`, `power`, `detect`. `settleable.py` recomputes the per-world settleability
flags the evaluator carries and fails if one disagrees. `budget.py` has three: `concentrate`,
`single`, `cycle`, and it checks the headroom claimed at the end of this file. All of it was run in
process on macOS; the
repository's Bubblewrap sandbox does not run there, so `shortcut_probe.expected_score` in
`TASK_CARD.yaml` stays `null` until the Linux gate fills it.

## The scale

`summary.py scores`, twelve development and eight held-out worlds, budget 9000 operations each.

| strategy | dev | held | right | wrong | declined | share of reference |
|---|---|---|---|---|---|---|
| **reference** `verification/reference_opportunity_audit.py` | **0.5000** | **0.6250** | 0.50 | 0.00 | 0.50 | — |
| baseline `solution.py` (symptom scan) | 0.0000 | 0.0000 | 0.17 | 0.83 | 0.00 | 0 % |
| no-refusal | 0.3333 | 0.5000 | 0.67 | 0.33 | 0.00 | 67 % |
| naive-refusal | 0.1667 | 0.3750 | 0.50 | 0.33 | 0.17 | 33 % |
| round-count-power | 0.0833 | 0.2500 | 0.50 | 0.42 | 0.08 | 17 % |
| tenth-budget | 0.0833 | 0.1250 | 0.08 | 0.00 | 0.92 | 17 % |
| blanket-decline | 0.0000 | 0.0000 | 0.00 | 0.00 | 1.00 | 0 % |
| always-read-committed | 0.0000 | 0.0000 | 0.25 | 0.75 | 0.00 | 0 % |
| always-snapshot-isolation | 0.0000 | 0.0000 | 0.17 | 0.83 | 0.00 | 0 % |
| always-strict-serializable | 0.0000 | 0.0000 | 0.08 | 0.92 | 0.00 | 0 % |
| per-key-only | 0.0000 | 0.0000 | 0.33 | 0.67 | 0.00 | 0 % |
| abort-rate-only | 0.0000 | 0.0000 | 0.25 | 0.75 | 0.00 | 0 % |
| undesigned-traffic | 0.0000 | 0.0000 | 0.00 | 1.00 | 0.00 | 0 % |

The reference names six of the twelve development worlds and declines six, and it names no world
wrongly on either split. The best shortcut reaches two thirds of it, and it is not clean: no-refusal
names the wrong level in four of the twelve development worlds, naive-refusal in four as well.

No-refusal is deliberately the strongest member of its family. It is the reference with the last
step deleted: the same four patterns, the same detector, the same two-phase allocation that spends
the tail of the budget only where the verdict could still fall, and then it names whatever the
evidence came to instead of asking whether the quiet levels were ever contended. An earlier version
cycled the four patterns evenly over the whole budget and scored 0.1667, half as much, so declaring
that one would have understated what the calibration is worth by a factor of two.

## The three discovery axes

`summary.py axes`. The false-discovery rate counts wrong levels against the worlds a candidate
actually named. The other two are read against what each world could have supported: a refusal is
correct only where the budget could not have settled the world, and coverage is how much of what was
settleable the candidate went on to settle.

Every one of the three is published beside its count, since a rate on its own has no resolution.
The refusal denominator is six on the development split and three held out, the coverage
denominator six and five, and the false-discovery denominator is whatever the candidate named,
which is zero for one that declines everything and all twelve for one that names every world.

| strategy | dev fdr | dev correct refusal | dev coverage | held fdr | held refusal | held coverage |
|---|---|---|---|---|---|---|
| **reference** | **0.000** | **1.000** | **1.000** | **0.000** | **1.000** | **1.000** |
| baseline | 0.833 | 0.000 | 1.000 | 0.750 | 0.000 | 1.000 |
| no-refusal | 0.333 | 0.000 | 1.000 | 0.250 | 0.000 | 1.000 |
| naive-refusal | 0.400 | 0.167 | 0.833 | 0.200 | 0.667 | 0.800 |
| round-count-power | 0.455 | 0.000 | 0.833 | 0.375 | 0.000 | 1.000 |
| blanket-decline | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | 0.000 |
| tenth-budget | 0.000 | 1.000 | 0.167 | 0.000 | 1.000 | 0.200 |

The reference declines exactly the worlds the settleability measurement calls starved and names
exactly the ones it calls settleable, on both splits. The reference never reads the flags, and the
measuring protocol never consults the reference, so the agreement is evidence that the labels mean
what they say. It is not independent evidence, though: the reference's `MIN_OPP` thresholds were
read off the same exposure rates that govern whether a full-budget sweep settles a world, so the
two are answering one question with the same arithmetic. What the agreement rules out is a label
that is merely a restatement of the world's weak rate.

## Under re-drawn worlds

`summary.py shifts`, the same grid with every world seed shifted four ways, 80 world-runs each.

| strategy | dev mean | dev min | held mean | held min | wrong calls |
|---|---|---|---|---|---|
| **reference** | **0.5417** | 0.5000 | **0.6562** | 0.6250 | **0** |
| naive-refusal | 0.2917 | 0.0000 | 0.4375 | 0.1250 | 16 |
| no-refusal | 0.2500 | 0.1667 | 0.4375 | 0.2500 | 27 |
| round-count-power | 0.2083 | 0.0000 | 0.3750 | 0.0000 | 28 |
| tenth-budget | 0.1042 | 0.0833 | 0.2188 | 0.1250 | 0 |
| baseline and the seven blind or cheap strategies | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 to 80 |

The reference is flat across shifts and never wrong. No shortcut passes 54 per cent of it once the
seeds move, and the one that gets there is wrong in 16 of its 80 world-runs while no-refusal is
wrong in 27. The order flips here: no-refusal leads on the fixed grid at 67 per cent and falls to 46
per cent across shifts, because naming a level without checking whether it was contended pays off
only on the particular draws where the evidence happened to arrive.

## Which worlds the budget can settle

`settleable.py`. One draw counts as settled when a full-budget round-robin over the four contention
patterns witnesses the class that pins the world's own level and would also have caught a store at
every level below it, run at the same weak rate and seed. Neither clause mentions the reference. The
flag is the share of 50 re-drawn seeds that come out settled, because a single run fails now and then
even where the budget is ample.

| split | settleable | starved |
|---|---|---|
| development | 6 (shares 0.94 to 1.00) | 6 (shares 0.02 to 0.18) |
| held out | 5 (shares 0.96 to 1.00) | 3 (shares 0.00 to 0.14) |

No world lands between 0.35 and 0.80, so no flag turns on where the line was drawn. Two rules fell
out of building the set, and the earlier version broke both:

- **No starved world is strict serializable.** With nothing witnessed the verdict defaults to the
  top of the ladder, so a starved world there pays a candidate that never declines exactly what it
  pays one that reasoned.
- **No starved world is read uncommitted.** There is none to build. A dirty write is the cheapest
  class to catch, and even at `min_weak_rate` a read uncommitted store is settled in about half of
  draws.

The starved worlds are read committed, parallel snapshot and snapshot isolation, where classes
above the truth still fire. That is what makes them discriminating: the evidence points somewhere,
just not far enough down the ladder, so an uncalibrated answer is wrong rather than absent. A set
whose starved worlds sat high on the ladder instead witnessed nothing at all, and the cheap rule of
declining only when nothing fired reached 83 per cent of the reference on it.

## Why the task is well posed

`summary.py sound` runs all four contention patterns for 300 rounds at each of six levels, three
weak rates (0.10, 0.30, 0.50) and three seeds, and checks the classes the history witnesses against
the classes the level permits. **No violation.** An auditor that reads the evidence correctly
therefore never names a level below the truth; the only way to be wrong is to name one above it,
which is what the refusal is for.

## Where the power is

`summary.py power`, 500 rounds per cell. `opp/rnd` is how often a round really raced two transactions
on the weak path, which the operation clocks certify; `expose` is how often, given such a round, the
store's own level gave itself away.

| level | opp/rnd at p = 0.10 / 0.20 / 0.35 / 0.50 | exposure |
|---|---|---|
| read_uncommitted | 0.012 / 0.070 / 0.224 / 0.464 | 0.50 / 0.60 / 0.57 / 0.57 |
| read_committed | 0.008 / 0.012 / 0.140 / 0.222 | 0.75 / 1.00 / 0.91 / 0.91 |
| parallel_snapshot | 0.006 / 0.020 / 0.044 / 0.126 | 0.00 / 0.20 / 0.23 / 0.25 |
| snapshot_isolation | 0.002 / 0.022 / 0.060 / 0.098 | 1.00 / 0.91 / 0.93 / 0.90 |
| serializable | 0.014 / 0.054 / 0.186 / 0.402 | 0.86 / 0.93 / 0.92 / 0.95 |

Opportunities are quadratic in the weak rate, which is the whole reason the budget runs out. The
reference's thresholds `MIN_OPP = {3, 2, 9, 2, 2}` are the smallest counts that put
`(1 - exposure) ** count` under 0.10, with a floor of two. Parallel snapshot is the expensive
boundary: a fork needs the two replicas to disagree, not merely to lag, so one opportunity in four
exposes it and nine quiet ones are needed to rule it out.

## What a strategy that never declines would answer

`summary.py detect`, ten seeds per cell, the share of runs in which the level's own class is caught
at all within the budget.

| level | 0.04 | 0.07 | 0.10 | 0.14 | 0.20 | 0.30 | 0.45 |
|---|---|---|---|---|---|---|---|
| read_uncommitted | 0.20 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| read_committed | 0.20 | 0.50 | 0.90 | 1.00 | 1.00 | 1.00 | 1.00 |
| parallel_snapshot | 0.10 | 0.20 | 0.60 | 0.70 | 0.90 | 1.00 | 1.00 |
| snapshot_isolation | 0.20 | 0.50 | 0.90 | 1.00 | 1.00 | 1.00 | 1.00 |
| serializable | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

Serializable is the outlier: a stale read needs only a read-only transaction and a replica four
ticks behind, so it is caught even where nothing else is. That is why a serializable world is never
one of the starved ones.

## Headroom the reference leaves

`budget.py concentrate`, 40 replicate seeds per world. The reference allocates greedily by pattern
cost and keeps sweeping all four shapes, so only about a quarter of its rounds are forks. Spending
the whole budget on forks instead leaves the total round count almost unchanged, because the four
shapes cost about the same, but it multiplies the fork rounds roughly fivefold. On the starved
parallel-snapshot worlds the reference declines, that is the difference between seeing the long fork
and not:

| world | weak rate | long fork, balanced | long fork, fork only |
|---|---|---|---|
| dev-08 | 0.080 | 0.35 | 0.85 |
| dev-10 | 0.050 | 0.17 | 0.42 |
| dev-11 | 0.070 | 0.28 | 0.80 |
| held-07 | 0.060 | 0.17 | 0.68 |

So four of the nine starved worlds are settleable by a better allocation, and the reference's 0.500
is not the ceiling.

The headroom is real but it is not cheap, which is the point. `budget.py single` runs the
reference's own decision rule with the shapes narrowed and nothing else changed:

| patterns kept | dev | share of reference |
|---|---|---|
| fork | 0.0000 | 0 % |
| conflict | 0.1667 | 33 % |
| repeat | 0.0833 | 17 % |
| disjoint | 0.0000 | 0 % |
| fork + conflict | 0.2500 | 50 % |
| fork + repeat | 0.0833 | 17 % |
| conflict + repeat | 0.1667 | 33 % |

Every one of them is below the bar, and fork alone is the worst of all. The shapes a narrowed sweep
drops are the ones that rule out the other boundaries, so it declines worlds the full sweep names.
Concentration pays only after the level has been diagnosed well enough to know which boundary is in
question, and doing that on a budget is the part that is not cheap.

Two more places where a better auditor can do better, neither of them measured here:

- Its refusal is a fixed per-level opportunity count, not a posterior over the level given the whole
  history. A solver that pools the evidence across boundaries, or that estimates the weak rate from
  the observed interleavings and computes its own miss probability, can answer where the reference
  will not.
- It stops at the first witness of a class instead of accumulating strength of evidence, so it
  cannot distinguish a level it has seen once from one it has seen twenty times.

One thing that looks like headroom and is not: `CYCLE_MAX = 4` bounds the anti-dependency cycles the
analysis chases, but `budget.py cycle` scores 0.5000 development and 0.6250 held out at every bound
from 4 to 12. No shape produces more than five transactions in a round, and a cycle cannot be longer
than the round that made it, so the bound is never reached.
