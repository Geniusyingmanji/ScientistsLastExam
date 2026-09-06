# SingleMoleculeKinetics: scoring evidence — 2026-09-06

## Scientific endpoints

Zero is the all-refusal scientific floor. Perfect supported recovery plus correct
unsupported refusal defines one. The best simultaneous label-permutation error
is mean absolute log-rate error plus three times mean absolute efficiency error.
Its zero-credit tolerance is tightened from 1.2 to 0.10. This is an accuracy
requirement, not multiplication of the old combined score. Exact parameters
still receive one; a 0.05 log-rate shift at exact efficiencies receives 0.5
mechanism credit. Photon budget, traces and the two-start Baum-Welch reference
are unchanged. Reference measurements informed this tolerance, so they are not
blind frontier calibration.

## Reproduction and measurements

The legal `solution.py` baseline scores **0.000000**, valid=1. The input-only
comparison reference is `references/reference.py`.
Run it with `python -m sle eval --allow-uncertified --task <logical ID from
frontier_eval/metadata.yaml> --candidate <reference path> --timeout 300`.

| Solver | Development normalized score | heldout_scientific_score | Valid |
| --- | ---: | ---: | ---: |
| Original reference | 0.67103780 | 0.62057054 | 1 |

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

Scientific sources: doi:10.1016/j.bpj.2013.12.055.
