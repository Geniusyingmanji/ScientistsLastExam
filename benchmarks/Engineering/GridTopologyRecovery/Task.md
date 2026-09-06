# GridTopologyRecovery

## The question

A five-bus DC network has unknown line status. Two frozen injection patterns are public.
You may buy **8** angle measurements `measure(pattern_index, bus_index)`. Name which graph in
the public catalog is in service, or refuse when two catalog graphs produce the same angles
on both injections (topology error identification, Monticelli).

## What you implement

```python
def recover_topology(problem, measure):
    ...
    return {"catalog_name": "graph_0"|...|"graph_4", "confidence": ..., "abstain": False}
```

### `problem` keys

| key | meaning |
|---|---|
| `bus_count` | 5 |
| `slack_bus` | 0 |
| `injection_patterns` | two length-5 real power vectors, MW (DC) |
| `catalog_names` | five named undirected graphs |
| `catalog_edges` | edge list for each catalog name, as pairs of bus indices |
| `measure_budget_calls` | 8 |
| `measurement_model` | DC voltage angle in radians |
| `abstain_when` | two catalog graphs are observationally equivalent |

`pattern_index` is 0 or 1. `bus_index` is in `[0, 4]`. Overspend fails closed.

## Relation and distinction

- Not `StructuralEngineering/ModalDamageAttribution`: that task knows the topology and asks
  which member lost stiffness.
- Not `Physics/HiddenCouplingNetwork`: analog units with tanh coupling, not DC power flow.
- Not `Algorithm/GraphFromDistances`: distance queries, not PMU angles.
- Not PR #21 `DistributionNetworkTopology`: that reconfigures a distribution feeder.
  This recovers which frozen five-bus catalog graph is in service, and refuses an
  electrically invisible extra chord.
- Not retired `PowerSystems/OptimalPowerFlow`: that was a dispatch optimization.

## Scoring

Mechanism, false discovery, refusal and coverage are separate. Always-abstain is exactly zero.
`contract_lint` is enforced by typed submissions: unknown catalog names fail closed.
