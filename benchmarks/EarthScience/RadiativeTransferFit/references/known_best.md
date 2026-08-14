# Known best — RadiativeTransferFit

## Anchor

`verification/reference_retrieval.py` is a truth-blind retrieval, run through the task's own
evaluator. It uses only what a candidate receives — the public forward model and the observation
callback — and never reads the hidden world.

Reproduce with:

```bash
python scripts/measure_reference.py --task EarthScience/RadiativeTransferFit \
    --reference verification/reference_retrieval.py --entry discover_atmosphere
```

| | every recorded model proposal | reference |
|---|---:|---:|
| `combined_score` | 0.0000 | **0.7910** |
| `development_discovery_coverage` | 0.0 | 1.0 |
| `development_false_discovery_rate` | 0.0 | 0.0 |
| `development_correct_refusal_rate` | 1.0 | 1.0 |
| `mechanism_score` | 0.0 | 0.8606 |
| `heldout_mechanism_score` | — | 0.4750 |

The model column is not a weak baseline: every recorded proposal is valid and declines every
world, which scores exactly the all-abstain normalisation anchor. Its false-discovery and refusal
rates are perfect because declining cannot misfire. The reference matches both and adds the
mechanism recovery.

The reference is deliberately imperfect. It reaches 0.475 on held-out worlds, so the task retains
headroom; a reference scoring 1.0 would leave nothing to measure.

## What the reference does

1. **Observe** — two calls, eighteen units: twelve channels at `view_cosine = 1.0`, six of them
   again at `0.5`. Angle diversity separates a temperature-profile change from an optical-depth
   change, because slanting lengthens the path without changing the emitting temperatures.
2. **Select** — all thirty-two support patterns are fitted with inactive entries pinned to their
   inactive values, and the pattern is chosen by BIC.
3. **Decide** — abstain when the best-supported member of the public family still leaves a
   reduced chi-square above 2.0, which is what a world outside the family looks like; abstain
   also when nothing survives selection, which is the null atmosphere.

## Measured separation

Reduced chi-square of the best in-family fit, by world kind:

| kind | chi²/dof |
|---|---|
| `in_library` | 0.72 – 1.24 |
| `null` | 0.66 – 0.69 |
| `absorber` | 3.46 |
| `cloud` | 146.3 |

The out-of-family worlds are detectable at this budget and noise level, which is the fact that
makes correct refusal possible rather than lucky.

## Three attempts, and what each showed

| attempt | rule | combined | FDR (dev) | refusal (dev) |
|---|---|---:|---:|---:|
| 1 | chi-square threshold 4.0 | 0.0000 | 1.0 | 0.0 |
| 2 | threshold 2.0, abstain on null | 0.1615 | 0.5 | 0.5 |
| 3 | BIC subset selection | **0.7910** | 0.0 | 1.0 |

Attempt 1 claimed on every world and scored zero — the exact mirror of the blanket abstention it
was written to beat, and evidence that the normalisation demands discrimination rather than
either extreme. Attempt 3's change was to stop thresholding a least-squares fit: noise lands in
every knot, so thresholding marks four or five of five entries active on every world including
the nulls. Which entries are active is a model-selection question, and answering it as one is
what took the score from 0.16 to 0.79.
