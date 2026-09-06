# PhylogeneticParsimonySearch: scoring evidence — 2026-09-06

## Scientific endpoints

Zero is the caterpillar tree. One is the sum across sites of distinct-state
count minus one, a lower bound on every tree's Fitch cost. This relaxation may
be unattainable jointly across sites; it is not a published record. Scoring is
now explicitly **clipped**, and average linkage is no longer the endpoint.
The unchanged input-only NNI probe in `verification/headroom_probe.py` improves
both development and held-out scores, which remain bounded by one.

## Reproduction and measurements

The legal `solution.py` baseline scores **0.000000**, valid=1. The input-only
comparison reference is `verification/reference_search.py`.
Reproduce using:

```sh
python -m sle eval --allow-uncertified --task Phylogenetics/PhylogeneticParsimonySearch \
  --candidate benchmarks/Biology/PhylogeneticParsimonySearch/verification/reference_search.py --timeout 300
```

Baseline and reference were validated through the Linux candidate sandbox on
implementation commit `3b62c02`; baseline score was exactly zero and both were valid.

| Solver | Development normalized score | heldout_score | Valid |
| --- | ---: | ---: | ---: |
| Original reference | 0.67836236 | 0.65117581 | 1 |
| Public-input headroom probe | 0.70492678 | 0.69624860 | 1 |

The discovery held-out column is raw scientific quality, not the normalized
development scale. Optimization held-out scores use the same normalization as
development. All reference algorithms are unchanged by this calibration.
Pre-calibration score measurements do not describe this revision.

## Limits and provenance

These original procedural worlds are repository-visible; held-out means excluded
from search feedback, not server-secret. No external datasets or code are
redistributed. Model simplifications and nearest-task overlap are in `Task.md`.
Precision/headroom measurements do not establish expert difficulty: strong
classical comparisons, frontier draws, long-horizon search and external domain
review remain pending. The task stays **candidate**.

Scientific sources: doi:10.1111/j.1096-0031.1999.tb00277.x, doi:10.1186/s12859-018-2009-1.
