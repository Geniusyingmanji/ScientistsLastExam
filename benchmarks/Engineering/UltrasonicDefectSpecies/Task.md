# UltrasonicDefectSpecies

## The question

A pulse-echo A-scan of a steel plate is either a **crack** (phase-inverted
narrow echo), a **pore** (same-phase echo plus a weak ring), a
**lack-of-fusion** doublet, or a clean scan. Two defects at once, or a
mode-converted extra arrival that is not a single species, must be refused.

You have **14** charged `measure(time_us)` assays. They return amplitude with
frozen noise. The longitudinal speed is published.

## What you implement

```python
def identify_species(problem, measure):
    ...
    return {"species": "crack"|"pore"|"lack_of_fusion"|"none",
            "confidence": ..., "abstain": False}
```

### `problem` keys

| key | meaning |
|---|---|
| `time_bounds_us` | inclusive `[0.8, 20]` |
| `measure_budget_calls` | 14 |
| `family_names` | `crack`, `pore`, `lack_of_fusion`, `none` |
| `wave_speed_mm_per_us` | longitudinal speed, 5.9 |
| `measurement_model` | `measure` returns amplitude |
| `abstain_when` | two species, or a mode-converted extra echo |

Spending past the budget fails the world closed.

## Relation and distinction

- Not `StructuralEngineering/ModalDamageAttribution`: that knows the topology
  and asks **which member** lost stiffness. This asks **which defect species**
  produced an A-scan, and a clean plate is in-family.
- Not `Sensors/QuartzCrystalMicrobalanceLab`: that inverts a named BVD circuit
  from an I/Q sweep. This classifies an ultrasonic echo family.
- Not `Spectroscopy/CrowdedSpectrumAssignment`: molecular lines, not a
  pulse-echo defect catalog.

## Scoring

Mechanism, false discovery, refusal and coverage are reported separately.
Always-abstain is exactly zero. The held-out split is evaluator-only.
`contract_lint` fails closed on unknown species and non-boolean abstain flags.
