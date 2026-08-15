# Known best — LowThrustTransfer

## The anchor this task used to have, and the one it has now

The task card said the reference was "independently repropagated feasible finite-thrust
reachability witnesses generated before target freezing; they are not claimed globally optimal."
The evaluator did not use them. It normalised

```text
score = (utility - baseline) / (1 - baseline)
```

against a utility of **one** — perfect terminal accuracy reached with zero propellant, which no
finite-thrust transfer can approach. The witnesses were in the scenario data, used to make the
targets reachable, and never scored.

Measured: the witnesses scored **0.646 – 0.810** on that scale, mean 0.729. So the card named an
anchor the code did not use, and the code's anchor was unreachable by construction.

The normalisation now runs against the witness:

```text
score = max((utility - baseline) / (reference_utility - baseline), 0)
```

Zero at the coast baseline, **one at the witness**, uncapped above it because the witnesses are
feasible transfers and are not claimed optimal.

## What this does to recorded scores

Every score on this task changes, by roughly 1/0.73. The best recorded searcher moves from 0.0401
to about 0.055 — it had looked like the hardest task in the inventory partly because its scale ran
to an impossible ideal.

| | old scale (ideal = 1) | witness scale (witness = 1) |
|---|---:|---:|
| coast baseline | 0.0000 | 0.0000 |
| reference witness | 0.729 (mean) | **1.0000** |
| best recorded model run | 0.0401 | ≈0.055 |

Runs recorded before this change are not comparable with runs after it. That is a real cost and it
is the reason the change is recorded here rather than made quietly: the previous numbers were not
wrong arithmetic, they were answering a different question.

## Reproduce

The frozen witness utilities in `FROZEN_REFERENCE_UTILITIES` come from repropagating each
scenario's own `reference_coefficients`:

```python
for instance in evaluator._instances():
    coefficients = instance["reference_coefficients"]
    evaluator._score_instance(lambda *a, **k: coefficients, instance)["score"]
```

Under the current normalisation that returns exactly 1.0 for every scenario, which is the check
that the anchor and the constants agree.
