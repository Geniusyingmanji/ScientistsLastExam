# IsotopeFluxIdentifiability: scoring evidence — 2026-09-06

## Scientific endpoints

Zero is the all-refusal scientific floor; perfect supported identifiable fluxes
plus correct zero-net refusal defines one. The mean error over net and total
exchange flux, divided componentwise by max(truth,0.1), now has a zero-credit
tolerance of 0.025 instead of 0.6. The observation budget and three-start weighted
least-squares reference are unchanged. Individual parallel exchange branches
remain unidentifiable and are never accepted. The stricter tolerance was chosen
with reference measurements; shifted held-out measurements are reported
separately and do not constitute blind frontier validation.

## Reproduction and measurements

The legal `solution.py` baseline scores **0.000000**, valid=1. The input-only
comparison reference is `references/reference.py`.
Run it with `python -m sle eval --allow-uncertified --task <logical ID from
frontier_eval/metadata.yaml> --candidate <reference path> --timeout 300`.

| Solver | Development normalized score | heldout_scientific_score | Valid |
| --- | ---: | ---: | ---: |
| Original reference | 0.73709196 | 0.48395168 | 1 |

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

Scientific sources: doi:10.1016/j.ymben.2006.09.001.
