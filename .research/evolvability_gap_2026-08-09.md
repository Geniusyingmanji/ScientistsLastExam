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

### `MedicinalChemistry/MolecularLeadOptimization` (5 paired seeds)

| seed | normal | blind | difference |
|---|---:|---:|---:|
| 0 | 0.4778 | 0.4058 | +0.0719 |
| 3 | 0.6604 | 0.3063 | +0.3541 |
| 4 | 1.0210 | 0.4327 | +0.5883 |
| 6 | 0.7968 | 0.3028 | +0.4940 |
| 7 | 0.5802 | 0.3898 | +0.1904 |

mean 0.7072 versus 0.3675.

| endpoint | Delta | 95% CI | W/T/L |
|---|---:|---|---|
| full-horizon | **+0.3397** | **[+0.1539, +0.5256]** | 5/0/0 |
| common-token | **+0.2389** | **[+0.0921, +0.3857]** | 5/0/0 |

### `QuantumErrorCorrection/QuantumErrorDecoder` (7 paired seeds)

mean 0.8711 versus 0.7497, normal ahead on every seed.

| endpoint | Delta | 95% CI | W/T/L |
|---|---:|---|---|
| full-horizon | **+0.1214** | **[+0.0492, +0.1935]** | 7/0/0 |
| common-token | **+0.1005** | **[+0.0294, +0.1715]** | 6/0/1 |

### Best-so-far against token budget

Both arms evaluated at shared budgets, averaged over paired seeds.

| budget (tokens) | QEC normal | QEC blind | Molecular normal | Molecular blind |
|---|---:|---:|---:|---:|
| 25% | 0.5428 | 0.3725 | 0.4275 | 0.1895 |
| 50% | 0.7238 | 0.6927 | 0.4275 | 0.2971 |
| 75% | 0.8502 | 0.7055 | 0.6064 | 0.3675 |
| 100% | 0.8711 | 0.7497 | 0.7072 | 0.3675 |
| 150% | 0.8711 | 0.7497 | 0.7072 | 0.3675 |

The feedback arm leads at every budget on both tasks. The control plateaus and stays flat —
which is what independent sampling must do, since additional draws only help through the maximum
and that saturates. The feedback arm keeps climbing.

## Relation to the Track F null

The project's one previous powered feedback experiment found the opposite: on
`DynamicalSystems/ActiveLawDiscovery`, normal feedback scored 0.7814 against 0.7973 for
selection-blind, an estimate of −0.0159 with p=0.336, in the wrong direction.

Both results can be true, and the difference is task design rather than model capability. On
ActiveLaw the open-loop arm already reached 0.797 of a 1.0 ceiling, so there was almost nothing
left for feedback to buy. On these two tasks the open-loop arms sit at 0.75 and 0.37 against
uncapped anchors, and the gap is exactly where the headroom is: the task with more headroom
(Molecular, control at 0.37) shows roughly three times the gap of the task with less
(QEC, control at 0.75).

That is the substantive claim this experiment supports: **a feedback effect is only observable on
tasks that leave room for one**, so feedback sensitivity is a property to establish before a task
is admitted, not a result to hope for afterwards.

## Methodological note: how not to token-match

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

Replicate counts are 5 and 7 paired seeds. The intervals are normal approximations on small
samples and should be read as indicative rather than as a powered test.
