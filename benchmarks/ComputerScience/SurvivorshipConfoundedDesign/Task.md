# SurvivorshipConfoundedDesign — association among survivors is not a treatment effect

This is not `CausalDiscovery/InterventionalSCM` (full samples, recover a 7-node DAG) and not
`SystemsBiology/GeneNetworkIntervention` (ODE network plus a phenotype). Here every returned
row has already been selected on an outcome-dependent filter. A hidden confounder opens
T ← C → Y and also feeds selection, so the survivor table is associated even when there is
no T→Y edge (Hernán-style selection / CausalGame survivorship). In this task's stated
model class, T has no direct path to selection and selection probability is known to increase
with Y. Those two restrictions, rather than randomisation alone, make the sign of a survival
contrast identify the sign of T→Y.

You may observe survivors, or randomise T and then watch who still returns.

## Your task

```python
def recover_effect(problem, observe_survivors, intervene):
    # observe_survivors(n) -> {"treatment", "outcome", "n_requested", "n_returned"}
    # intervene(t, n) -> same, from do(T=t) then selection
    return {"has_treatment_effect": True, "effect_sign": 1.0, "confidence": ..., "abstain": False}
```

When abstaining:

```python
return {"abstain": True, "confidence": ...}
```

### `problem` — every key you are given

| key | meaning |
|---|---|
| `treatment_name` | column name of T (`treatment`) |
| `outcome_name` | column name of Y (`outcome`) |
| `observe_batch_max` | largest n for `observe_survivors` (800) |
| `intervene_batch_max` | largest n for `intervene` (800) |
| `budget_units` | units for this world (8) |
| `sample_unit` | each call costs `ceil(n / 100)` units |
| `treatment_probe_low` | lowest allowed `do(T)` value (−1.2) |
| `treatment_probe_high` | highest allowed `do(T)` value (1.2) |
| `measurement_model` | prose: returned rows are survivors; both calls report `n_requested` / `n_returned` |
| `selection_note` | prose: `n_returned / n_requested` is the survival rate; selection increases with Y and has no direct T input |
| `abstain_when` | prose: survivor association is confounding plus selection, or `do(T)` does not move survival |

### `observe_survivors(n)` and `intervene(t, n)`

`n` must be an integer in `[8, observe_batch_max]` or `[8, intervene_batch_max]`. `t` must
lie in `[treatment_probe_low, treatment_probe_high]`. Overspending the budget raises and
the world scores zero. The hidden confounder is never returned.

### What you return

| key | meaning |
|---|---|
| `has_treatment_effect` | boolean; required unless abstaining |
| `effect_sign` | finite nonzero number; required when `has_treatment_effect` is true; only the sign is scored |
| `confidence` | finite number in `[0, 1]` |
| `abstain` | boolean; if true, the effect fields are ignored |

Anything malformed scores that world zero.

## Scoring

The public `combined_score` is development mechanism recovery, normalised so that declining
every world is exactly zero. A true T→Y edge scores only if you claim it with the right
sign. Claiming an effect on a collider or a blank is a false discovery. False-discovery,
correct refusal, coverage and the held-out split are reported separately and never averaged.

- `sle.contract_lint` is importable and free to call for shape checks. It costs no oracle call.
- Only edit `solution.py`. Keep `recover_effect(problem, observe_survivors, intervene)`.
- NumPy/SciPy only. Deterministic CPU code. No network or process creation. Do not read
  `verification/` or `frontier_eval/`.
