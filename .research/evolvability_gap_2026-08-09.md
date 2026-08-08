# Evolvability gap on the two community-oracle tasks

Date: 2026-08-09. Model: `gpt-5.6-sol` over the local keyless Azure proxy, low reasoning effort,
no provider-side generation seed. Algorithm: `greedy_rewrite`, budget 3. Host: benchmark machine,
real Bubblewrap sandbox.

## What is being measured

The **evolvability gap** is the difference between spending an oracle budget on a feedback loop
and spending the same budget on independent draws:

```text
Delta(t, N) = E[ N sequential proposals, each seeing the oracle's returned metrics ]
            − E[ best of N proposals that never see any oracle result ]
```

The control arm is the harness's existing `selection_blind` mode: every proposal is generated
from the frozen baseline parent, and evaluation results are retained only for offline selection.
Trajectory inspection confirms the arms behave as intended — under `selection_blind` all three
proposals carry distinct candidate hashes and share the baseline parent hash, while under
`normal` each proposal's parent is the previous accepted candidate.

This matters because `Delta ≈ 0` means a task measures the model's one-shot proposal
distribution rather than its ability to use feedback. Under the proposed admission rule, only
tasks with a reliably positive gap belong in a benchmark that claims to measure iterative
self-improvement.

## Result

Paired by seed. Two endpoints are reported because reading feedback consumes context, so equal
proposal counts are not equal resource budgets.

Both tasks reached the full 8 paired seeds; no cell failed.

### `MedicinalChemistry/MolecularLeadOptimization` (8 paired seeds)

| seed | normal | blind | difference |
|---|---:|---:|---:|
| 0 | 0.4778 | 0.4058 | +0.0719 |
| 1 | 0.4606 | 0.6325 | **−0.1719** |
| 2 | 0.8328 | 0.3918 | +0.4410 |
| 3 | 0.6604 | 0.3063 | +0.3541 |
| 4 | 1.0210 | 0.4327 | +0.5883 |
| 5 | 0.8911 | 0.3732 | +0.5179 |
| 6 | 0.7968 | 0.3028 | +0.4940 |
| 7 | 0.5802 | 0.3898 | +0.1904 |

mean 0.7151 versus 0.4044.

| endpoint | Delta | 95% CI | W/T/L |
|---|---:|---|---|
| full-horizon | **+0.3107** | **[+0.1298, +0.4916]** | 7/0/1 |
| common-token | **+0.1694** | **[+0.0362, +0.3026]** | 7/0/1 |

Seed 1 is the single loss and is worth keeping in view: the control drew an unusually good
open-loop proposal (0.6325 against a control mean of 0.4044) while the feedback arm drew a poor
one. A positive gap in the mean does not mean feedback wins every time.

### `QuantumErrorCorrection/QuantumErrorDecoder` (8 paired seeds)

mean 0.8814 versus 0.7470, normal ahead on every seed at the full horizon.

| endpoint | Delta | 95% CI | W/T/L |
|---|---:|---|---|
| full-horizon | **+0.1345** | **[+0.0669, +0.2020]** | 8/0/0 |
| common-token | **+0.1162** | **[+0.0473, +0.1850]** | 7/0/1 |

### Best-so-far against token budget

Both arms evaluated at shared budgets, averaged over paired seeds.

| budget (tokens) | QEC normal | QEC blind | Molecular normal | Molecular blind |
|---|---:|---:|---:|---:|
| 25% | 0.5905 | 0.4169 | 0.3989 | 0.2689 |
| 50% | 0.7489 | 0.6971 | 0.4161 | 0.3604 |
| 75% | 0.8632 | 0.7082 | 0.5738 | 0.4044 |
| 100% | 0.8814 | 0.7470 | 0.7151 | 0.4044 |
| 150% | 0.8814 | 0.7470 | 0.7151 | 0.4044 |

The feedback arm leads at every budget on both tasks. The control plateaus and stays flat —
which is what independent sampling must do, since additional draws only help through the maximum
and that saturates. The feedback arm keeps climbing.

## Relation to the Track F null

The project's one previous powered feedback experiment found the opposite: on
`DynamicalSystems/ActiveLawDiscovery`, normal feedback scored 0.7814 against 0.7973 for
selection-blind, an estimate of −0.0159 with p=0.336, in the wrong direction.

Both results can be true, and the difference is task design rather than model capability. On
ActiveLaw the open-loop arm already reached 0.797 of a 1.0 ceiling, so there was almost nothing
left for feedback to buy. On these two tasks the open-loop arms sit at 0.75 and 0.40 against
uncapped anchors, and the gap is exactly where the headroom is: the task with more headroom
(Molecular, control at 0.40) shows roughly 2.3 times the gap of the task with less
(QEC, control at 0.75).

That is the substantive claim this experiment supports: **a feedback effect is only observable on
tasks that leave room for one**, so feedback sensitivity is a property to establish before a task
is admitted, not a result to hope for afterwards.

## Methodological note: how not to token-match

Mean token ratios were 1.33x (Molecular) and 1.26x (QEC), feedback arm over control.

The first analysis truncated each feedback run at the token total its own paired control had
consumed. That inverted the sign, reporting −0.13 on QEC. The cause was a single seed where the
control was anomalously cheap, at 4.07 times fewer tokens: truncating there cut the feedback arm
below its first completed proposal, so a missing measurement was scored as a large negative.

Evaluating both arms at shared cohort-level budgets, as in the table above, removes the artifact
without discarding data. Per-pair truncation should not be used when control cost varies.

## Claim boundary

| Claim | Status |
|---|---|
| Iterative feedback beats matched open-loop sampling on these two tasks at budget 3 | Supported, both endpoints, CI excludes zero |
| The effect generalizes to other tasks or models | Not supported; two tasks, one model, no provider seed control |
| These tasks pass the proposed Delta admission gate | Supported at budget 3; the gate specifies N ≥ 100 with a population searcher |
| Larger budgets preserve the gap | Untested; budget 3 only |
| Anything about scientific discovery | Not supported; these are simulator and cheminformatics scores |

Replicate counts are 8 paired seeds per task. The intervals are normal approximations on small
samples and should be read as indicative rather than as a powered test.
