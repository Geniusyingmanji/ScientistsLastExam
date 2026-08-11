# RNAEnsembleDesign — known best values

All values are recomputed by the oracle at evaluation time; none is quoted from a paper.

Measured 2026-08-11 on the benchmark host (Linux, Python 3.8, ViennaRNA 2.7.2).

## What the anchor is

ViennaRNA's `inverse_fold`, run by the evaluator on the same targets and kept as the best of ten
restarts by ensemble defect. It is a genuine reference rather than a ceiling: it optimises
minimum-free-energy structure match, and the score is ensemble defect, which it does not optimise.

Restart matching matters. Candidates are allowed to call `inverse_fold` themselves — forbidding it
would be a rule the harness cannot enforce, since the oracle sees a returned sequence and not how
it was produced. With the anchor taken as the best of ten restarts, calling the routine once
scores 0.5763 rather than 1.0 - the routine is stochastic and one draw is not its best of ten -
and restarting it is only doing what the anchor already did.

## How the targets are chosen

Structures are drawn from a motif grammar — hairpin branches inside a closing stem, with
single-nucleotide bulges — and then filtered on two properties rather than accepted as drawn:

1. **Designable.** ViennaRNA's `inverse_fold` must reach the structure exactly within a few
   restarts. Not every dot-bracket string is designable, and scoring an undesignable target
   measures how close a candidate gets to something impossible while making the anchor arbitrary.
2. **Inside an anchor-defect band.** The best of ten `inverse_fold` restarts must land between
   0.02 and 0.15 ensemble defect at the shipped level. Below the band the anchor is already near
   perfect and cannot show a searcher doing better; above it the target is effectively
   undesignable.

Both filters exist because hand-tuning the generator failed in both directions, and the failures
are worth recording. Long clean helices fill with GC pairs and stop being a design problem: the
first shipped target set had anchor defects near 0.03 and a twelve-proposal search drove its own
defects to 0.001, pressing against the numerical floor. Raising the bulge density to compensate
produced target sets where ViennaRNA reached the target structure on **none** of them, with anchor
defects near 0.40. Difficulty is now the band itself, which is a property of the task rather than a
knob someone guessed.

## Anchors at the shipped level

Measured on the benchmark host with ViennaRNA 2.7.2. Five development targets, 37 to 66
nucleotides, two or three branches.

| quantity | value |
|---|---:|
| baseline defect, poly-A | ≈ 0.75 |
| anchor defect, best of ten `inverse_fold` restarts, median | **0.1358** |
| fraction of targets the anchor reaches exactly | 0.80 |
| target generation time | 18 s |

## Calibration ladder

| Designer | development |
|---|---:|
| Shipped baseline — unstructured poly-A | **0.0000** |
| A single `inverse_fold` call | **0.5020** |
| ViennaRNA `inverse_fold`, best of ten restarts | **1.0000** (by definition) |
| Truth-blind reference — 60 random restarts scored by ensemble defect | **1.4248** |

The reference designer clears the anchor, and that is the finding rather than a defect: optimising
the objective that is scored beats optimising a proxy for it, even with an unsophisticated search.
This is the reason NUPACK-style design targets ensemble defect directly. A single `inverse_fold`
call scores about half, because the routine is stochastic and one draw is not its best of ten.

With the anchor near 0.136 and the numerical floor at 1e-6, a candidate reaching a defect of 0.001
scores about 3.9, so the region above the anchor has room to discriminate. That was not true of the
first shipped set, where the same defect scored 2.06 and was capped by the floor.

## Why the score is uncapped

`inverse_fold` is the community's reference routine for this problem, not its optimum, and it
optimises the wrong objective for this score. Designing directly against ensemble defect is an
active line of work — NUPACK's defect-weighted design, hierarchical decomposition, constraint
generation — so scores above 1.0 are the region of interest and clipping there would erase the
measurement.

## Reproduce

```bash
python -m frontier_science eval --allow-uncertified --task RNAEngineering/RNAEnsembleDesign
```
