# GlenFlowLawDiscovery

## The question

Ice creeps as `v = A tau^n`. Glen's law has `n` near 3; temperate Newtonian ice
has `n = 1`. Basal sliding added to internal deformation **curves** the log-log
plot, and a plug that does not feel stress at all sits outside the family:
refuse.

You have **12** charged `measure(stress_kPa)` assays. They return `ln v` with
frozen noise.

## What you implement

```python
def identify_flow_law(problem, measure):
    ...
    return {"family": "glen"|"newtonian", "n": ..., "confidence": ...,
            "abstain": False}
```

### `problem` keys

| key | meaning |
|---|---|
| `stress_bounds_kPa` | inclusive `[20, 200]` |
| `measure_budget_calls` | 12 |
| `family_names` | `glen`, `newtonian` |
| `rate_law` | `v = A * tau^n` |
| `measurement_model` | `measure` returns `ln v` |
| `abstain_when` | sliding mixes the slope, or n is outside the family |

Spending past the budget fails the world closed.

## Relation and distinction

- Not `Oceanography/AMOCTippingRefusal`: that is a fold in a scalar climate
  ODE. This is a rheological exponent in ice.
- Not `Turbulence/WallClosureDiscovery`: a wall mixing-length formula, not Glen
  creep.
- Not PR #20 `IceObservationNetworkDesign`: that **places sensors**. This
  recovers the flow law from budgeted speed-vs-stress assays, or refuses.

## Scoring

Mechanism, false discovery, refusal and coverage are reported separately.
Always-abstain is exactly zero. The held-out split is evaluator-only.
`contract_lint` fails closed on unknown families and non-boolean abstain flags.
