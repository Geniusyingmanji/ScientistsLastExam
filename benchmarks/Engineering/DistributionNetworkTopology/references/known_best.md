# Reference and admission record — DistributionNetworkTopology

## 1. Reference method

`verification/reference_solver.py` is standalone: greedy set-cover probing of the
route family (several hundred routes, far beyond the budget), majority-vote
re-probes of every failed route against flips, exhaustive minimal hitting sets over
the candidate pipes, a discrimination loop probing routes that separate rival
candidates, and refusal when the surviving ambiguity is structural (identical
incidence columns — the twin corridor) or unresolved. It deliberately lacks
information-theoretic probe selection and Bayesian flip handling.

## 2. Baseline and normalization

The shipped `solution.py` probes one route and blames its first pipe: `0.000000`.
A truth-informed claim scores one. Measured on 2026-09-05 the reference reaches
`1.0000` development and robustness at the shipped level 1 with zero false
discoveries and full refusal.

## 3. Capability comparisons and ablations

| variant | level 1 | level 2 | level 3 |
|---|---:|---:|---:|
| full reference | 1.000 | 0.400 | 0.200 |
| discrimination disabled | 0.400 | — | — |

The difficulty ladder is steep: multi-break worlds under flips are where honest
tomography starts costing. Local debugging numbers, not frozen benchmark evidence.

## 4. Shortcut probes

Blaming the first failed route's first pipe scores zero; probing is the only signal
source, so shortcut risk concentrates in probe-selection efficiency, which is the
intended difficulty at levels 2 and 3.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the reference at level 2.

## 6. Construction errors and revisions

Six construction errors were caught locally on 2026-09-05. (i) The route
enumeration revisited cells and never terminated. (ii) An alphabetical truncation
to eighteen routes left pipes that no route could test. (iii) Mirror-symmetric break
sets appeared in supported worlds — truth sampling now enforces signature
uniqueness at generation. (iv) The twin pipe ids did not match the route table.
(v) A tie rule biased toward failure widened the failed set under flips. (vi) The
reference swept routes alphabetically and burned the budget before covering. All
pinned in `tests/test_distribution_network_topology.py`.

## 7. Robustness and reproducibility

Break sets are signature-filtered at generation; repeated probes draw fresh flips by
construction. Determinism was checked by comparing two full evaluation dictionaries.
Formal Linux sandbox replay, global evidence refresh and independent replication
are pending.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task WaterDistribution/DistributionNetworkTopology \
  --reference verification/reference_solver.py \
  --entry recover_network
```
