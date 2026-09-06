# FedBatchBioprocessDesign: scoring evidence — 2026-09-06

## Scientific endpoints

Zero is the constant-feed schedule's robust productivity. One is the utility
of an independently recomputed feasible schedule obtained by bounded Nelder-Mead
refinement (220 iterations) of the unchanged 54-schedule grid reference. All five
frozen schedules are in `verification/evaluator.py::ANCHOR_DESIGNS`.
`references/headroom_probe.py` reconstructs them from public inputs without
world identifiers or a schedule lookup table. These feasible anchors are not
claimed global optima; stronger schedules can tie at the clipped endpoint.

## Reproduction and measurements

The legal `solution.py` baseline scores **0.000000**, valid=1. The input-only
comparison reference is `verification/reference_design.py`.
Run it with `python -m sle eval --allow-uncertified --task <logical ID from
frontier_eval/metadata.yaml> --candidate <reference path> --timeout 300`.

| Solver | Development normalized score | heldout_robust_score | Valid |
| --- | ---: | ---: | ---: |
| Original reference | 0.51657669 | 0.64079264 | 1 |
| Public-input headroom probe | 1.00000000 | 1.00000000 | 1 |

The discovery held-out column is raw scientific quality, not the normalized
development scale. Optimization held-out scores use the same normalization as
development. All reference algorithms are unchanged by this calibration.
The superseded reference=1 measurements do not describe this revision.

## Limits and provenance

These original procedural worlds are repository-visible; held-out means excluded
from search feedback, not server-secret. No external datasets or code are
redistributed. Model simplifications and nearest-task overlap are in `Task.md`.
Precision/headroom measurements do not establish expert difficulty: strong
classical comparisons, frontier draws, long-horizon search and external domain
review remain pending. The task stays **candidate**.

Scientific sources: doi:10.1016/j.ifacol.2020.12.1167.
