# Reference and admission record — DistributionNetworkTopology

## 1. Reference method

`verification/reference_solver.py` is standalone: a likelihood-tracked hypothesis
search. Hypotheses are break sets of at most two pipes (extended to three when
every hypothesis accrues heavy flip penalties); each probe updates a
log-likelihood under the published flip rate with a per-pipe complexity penalty so
supersets never tie the truth; the next route is chosen to split the leading
hypothesis cluster as evenly as possible; a three-log-unit margin settles a claim,
and unresolvable rivalries are checked for structural twins (identical incidence
columns) before refusing. It deliberately lacks full entropy computation and
Bayesian model averaging.

## 2. Baseline and normalization

The shipped `solution.py` probes one route and blames its first pipe: `0.000000`.
A truth-informed claim scores one. Measured on 2026-09-05 the reference reaches
`1.0000` development and robustness at the shipped level 1 with zero false
discoveries and full refusal.

## 3. Capability comparisons and ablations

| variant | level 1 | level 2 | level 3 |
|---|---:|---:|---:|
| likelihood reference | 1.000 | 0.900 | 0.600 |
| pre-hardening set-cover reference | 1.000 | 0.400 | 0.200 |

The rework replaced cover-probing with hypothesis tracking; the level-2 default now
carries real multi-break ambiguity under flips. Local debugging numbers, not frozen
benchmark evidence.

## 4. Shortcut probes

Blaming the first failed route's first pipe scores zero; probing is the only signal
source, so shortcut risk concentrates in probe-selection efficiency, which is the
intended difficulty at levels 2 and 3.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the reference at level 2.

## 6. Construction errors and revisions

Seven construction errors were caught locally, the seventh in the 2026-09-06
difficulty rework. (i) The route enumeration revisited cells and never terminated.
(ii) An alphabetical truncation to eighteen routes left pipes that no route could
test. (iii) Mirror-symmetric break sets appeared in supported worlds — truth
sampling now enforces signature uniqueness at generation. (iv) The twin pipe ids
did not match the route table. (v) A tie rule biased toward failure widened the
failed set under flips. (vi) The reference swept routes alphabetically and burned
the budget before covering. (vii) The difficulty audit found the shipped level-1
default saturated (reference 1.000, single breaks trivially recoverable) while the
set-cover reference collapsed at level 2 (0.400/0.000) — the reference was rebuilt
as a likelihood tracker and the default raised to level 2. All pinned in
`tests/test_round4_new_tasks.py`.

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
