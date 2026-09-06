# HeavyTailEvidence

## The question

A positive sample is either a power law with known `xmin`, a lognormal above `xmin`, a
stretched-exponential cutoff outside both families, or too short to tell. This is the
Clauset–Shalizi–Newman setting: the **evidence**, not a parameter fit of a named model
that is already known to be true.

You receive a public sample and may buy up to **24** extra draws via `extra_draw()`.
Name the family or refuse.

## What you implement

```python
def synthesize_tail_evidence(problem, extra_draw):
    ...
    return {"family": "powerlaw"|"lognormal", "alpha": ..., "confidence": ...,
            "abstain": False}
```

For lognormal claims `alpha` is ignored except that it must be finite and `> 1`.

### `problem` keys

| key | meaning |
|---|---|
| `xmin` | lower bound used by both in-family generators |
| `public_sample` | observed values already collected |
| `extra_draw_budget` | 24 |
| `family_names` | `powerlaw`, `lognormal` |
| `abstain_when` | n too small, or cutoff / stretched exponential |

## Relation and distinction

- Not `ParticlePhysics/LookElsewhereAnomaly`: a mass-window trials factor, not tail families.
- Not `ParticlePhysics/DiscrepantMeasurements`: replicated constants, not heavy tails.
- Not PR #23 `ExactIdentityEvidence`: a constructed identity, not Clauset tail families.
- Not `Mathematics/SequenceLawRecovery`: integer recurrences.
- Not `DynamicalSystems/ActiveLawDiscovery`: ODE terms.

## Scoring

Mechanism, false discovery, refusal and coverage are separate. Always-abstain is exactly zero.
`contract_lint` fails closed on unknown families.
