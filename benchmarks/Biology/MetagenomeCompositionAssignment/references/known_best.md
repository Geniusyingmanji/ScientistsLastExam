# MetagenomeCompositionAssignment: scoring evidence — 2026-09-06

## Scientific endpoints

Zero is the blanket-refusal floor; one requires exact supported taxa/abundances,
correct unresolved alias groups, and correct library-inadequacy refusal.
Absolute abundance tolerance is now 0.025 (2.5 percentage points), replacing 0.15.
Taxon F1, alias precision penalties and the two-panel budget are unchanged.
The original conditional-profile fit is unchanged. Exact identifiable abundance
still earns full component credit; tightening this precision threshold does
not manufacture a reference-based ceiling. The reference informed calibration,
so the measured procedural worlds are not blind validation.

## Reproduction and measurements

The legal `solution.py` baseline scores **0.000000**, valid=1. The input-only
comparison reference is `verification/reference_assignment.py`.
Run it with `python -m sle eval --allow-uncertified --task <logical ID from
frontier_eval/metadata.yaml> --candidate <reference path> --timeout 300`.

| Solver | Development normalized score | heldout_scientific_score | Valid |
| --- | ---: | ---: | ---: |
| Original reference | 0.69450426 | 0.86021894 | 1 |

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

Scientific sources: doi:10.1093/bioinformatics/btu721.
