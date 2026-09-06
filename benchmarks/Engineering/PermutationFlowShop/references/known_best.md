# Reference and admission record — PermutationFlowShop

## 1. Reference method

`verification/reference_solver.py` is NEH construction refined by seeded iterated
local search: three-random-insertion perturbations, best-insertion descent with
better-or-equal acceptance, restarts from the elite, and the accelerated insertion
evaluation (prefix completion tables and suffix tail tables, O(machines) per candidate
position — verified against brute-force makespans on thirty random cases). The
descent at 3000 iterations with seed 0 freezes the record makespans. The former
400-iteration default took 236 seconds on the maintainer's host; the shipped runnable
reference now performs one complete perturb-and-descent cycle. The frozen record is
not a claimed optimum; fresh instances in these size classes remain hard search problems.
A local direct evaluation of the runnable reference took 0.93 seconds on 2026-09-06.

## 2. Baseline and normalization

Zero is anchored at the NEH construction, computed inside the oracle (the as-given
order is so weak that any competent construction closes over ninety percent of the
gap, which would flatten the scale). The shipped `solution.py` (as-given order) scores
exactly `0.000000` after flooring, as does NEH itself by construction. The frozen
3000-iteration record anchors score one per instance:

| instance | size | baseline | witness |
|---|---|---:|---:|
| pfs_44011 | 20x5 | 1586 | 1180 |
| pfs_44017 | 30x10 | 2686 | 2182 |
| pfs_44023 | 50x5 | 3469 | 3023 |
| pfs_44029 | 50x10 | 3983 | 2979 |
| pfs_44037 (held-out) | 20x5 | 1445 | 1222 |
| pfs_44041 (held-out) | 30x5 | 2161 | 1734 |
| pfs_44043 (held-out) | 50x10 | 3763 | 3012 |

Beating the frozen record scores above one with no cap.

## 3. Capability comparisons and ablations

| variant | development | held-out |
|---|---:|---:|
| frozen record (3000 iterations) | 1.000 | 1.000 |
| 20 iterations | 0.929 | 0.957 |
| 2 iterations | 0.849 | 0.805 |
| runnable reference (1 iteration) | 0.636 | 0.773 |
| NEH construction only | 0.000 | 0.000 (zero anchor) |

Every capability contributes monotonically. These are local debugging numbers, not
frozen benchmark evidence.

## 4. Shortcut probes

The artifact is the permutation itself, so low-dimensional parameterized families do
not apply; probes ran on construction shortcuts. NEH alone — the classic construction
any textbook offers — closes roughly 0.85 of the gap, and the shipped baseline zero.
The remaining tail above the witness is genuine search; passing these probes does not
prove the absence of shortcuts.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the frozen witness.
Independent operations-research review remains required.

## 6. Construction errors and revisions

One construction error was caught locally on 2026-09-05 before any model saw the task:
the pure-Python insertion descent cost ten seconds per iteration on 100-job instances,
making any fixed-iteration witness irreproducible in CPU minutes. The instance family
was capped at fifty jobs (Taillard's 20x5 and 50x10 classes are themselves decades
open) and the descent was rebuilt on accelerated prefix/suffix tables, with the
accelerated evaluation pinned against brute force. Recorded in
`tests/test_permutation_flow_shop.py`.

## 7. Robustness and reproducibility

Verification is exact integer simulation, so determinism holds by construction; the
held-out instances use fresh seeds of the same sizes. The package declares 5 seconds
expected evaluation time and a 300-second candidate timeout. Formal Linux sandbox replay,
global evidence refresh and independent replication are pending. See the task card
citations for background; the fresh-seeded instances are not the published Taillard
tables.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task ProductionSystems/PermutationFlowShop \
  --reference verification/reference_solver.py \
  --entry schedule_flow_shop
```
