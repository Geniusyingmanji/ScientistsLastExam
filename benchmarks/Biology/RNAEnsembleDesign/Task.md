# RNA ensemble design

Design an RNA sequence that folds into a given secondary structure — not merely as its
minimum-free-energy shape, but across its whole Boltzmann ensemble.

## Why the ensemble and not the MFE

A sequence does not adopt one structure. At equilibrium it occupies an ensemble of structures
weighted by their free energies, and a design that hits the target as its MFE can still spend
much of its time in other shapes. The measure that captures this is the **ensemble defect**: the
expected number of nucleotides paired differently from the target, averaged over the ensemble and
divided by the length. It is the objective NUPACK-style design optimises, and it is what is
scored here.

## Your function

```python
def design_rna(structure: str) -> str:
    ...
```

`structure` is a dot-bracket string: `(` and `)` for paired positions, `.` for unpaired. Return an
`A`/`C`/`G`/`U` string of exactly `len(structure)`.

## Oracle and anchor

Folding thermodynamics come from **ViennaRNA** with the Turner nearest-neighbour parameters, not
from a reimplementation, so a score here measures agreement with the community model.

The anchor is ViennaRNA's own `inverse_fold`, run by the evaluator on the same targets at scoring
time and kept as the **best of ten restarts** by ensemble defect. You may call `inverse_fold`
yourself — one call reaches parity, and restarting it is what the anchor already does. Beating it
takes optimising the objective it does not: `inverse_fold` searches for MFE structure match, while
the score is ensemble defect.

## Scoring

For each target, with `d` the ensemble defect:

```text
score = log(d_baseline / d_candidate) / log(d_baseline / d_anchor)
```

- `d_baseline` is an unstructured poly-A sequence, near 0.75. Scoring 0 means you did no better.
- `d_anchor` is the restart-matched ViennaRNA designer, near 0.03. Reaching it scores 1.0.
- There is **no upper clamp**. Halving the defect below the anchor is worth roughly +0.2.

The ratio is taken in logs on purpose: the baseline defect is more than twenty times the anchor's,
so a linear normalisation would spend its whole range below 1.0 and compress the region where the
work actually happens.

`combined_score` is the mean over the development targets. Three further targets you have not seen,
drawn from a different generator seed and a wider branch count, are scored only if every
development target produced a valid sequence, and reported separately as `robustness_score`.

## Rules

- Only edit `solution.py`; keep `design_rna(structure)`.
- Deterministic CPU code. The standard library, NumPy, SciPy and ViennaRNA are available; use
  ViennaRNA to fold and score your own candidates as often as you like.
- Return exactly `len(structure)` characters from `ACGU`. Anything else is invalid.
- Do not read `verification/` or `frontier_eval/`.

## Difficulty

Targets are generated from a motif grammar rather than hand-written, so the set is reproducible
and a harder level is a genuine change of regime. At the shipped level they run 24 to 69
nucleotides with one to three hairpin branches inside a closing stem; higher levels widen both.
Do not assume a length or a topology — read them from the structure string you are given.
