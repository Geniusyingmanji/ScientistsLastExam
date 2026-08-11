# RNAEnsembleDesign — known best values

All values are recomputed by the oracle at evaluation time; none is quoted from a paper.

Measured 2026-08-11 on the benchmark host (Linux, Python 3.8, ViennaRNA 2.7.2).

## What the anchor is

ViennaRNA's `inverse_pf_fold` — the routine that maximises the target's probability under the
partition function — run by the evaluator on the same targets and kept as the best of three
restarts by ensemble defect.

Choosing it over `inverse_fold` was not cosmetic. Measured on this task's own targets, ten
restarts of each:

| routine | median best ensemble defect | seconds per target |
|---|---:|---:|
| `inverse_fold` (MFE structure match) | 0.10834 | 0.7 |
| `inverse_pf_fold` (partition function) | **0.00145** | 10.5 |

A factor of about seventy-five, on every target. The first version of this task anchored on
`inverse_fold`, and a twelve-proposal search cleared that anchor four times over — the bar had
been set by a routine optimising a different objective from the one being scored. The
partition-function routine is also far steadier across restarts, which is why three suffice where
the other needed ten.

Candidates may call either routine. Forbidding it would be a rule the harness cannot enforce,
since the oracle sees a returned sequence and not how it was produced. Restarting `inverse_pf_fold`
more times than the anchor did is therefore a legitimate and shallow way to score slightly above
1.0; the uncapped score is what shows whether a search went further than that.

## How the targets are chosen

Structures are drawn from a motif grammar — hairpin branches inside a closing stem, with
single-nucleotide bulges — and then filtered on two properties rather than accepted as drawn:

1. **Designable.** `inverse_fold` must reach the structure exactly within a few restarts. Not every
   dot-bracket string is designable, and scoring an undesignable target measures how close a
   candidate gets to something impossible while making the anchor arbitrary.
2. **Inside an anchor-defect band.** The best of three `inverse_pf_fold` restarts must land between
   0.0008 and 0.004 ensemble defect at the shipped level. Below the band the anchor is already at
   the numerical floor; above it the target is effectively undesignable.

Both filters exist because hand-tuning the generator failed in both directions. Long clean helices
fill with GC pairs and stop being a design problem: an early target set had anchor defects near
0.03 and a twelve-proposal search drove its own defects to 0.001, pressing against the numerical
floor. Raising bulge density to compensate produced target sets ViennaRNA reached on **none** of
them. Difficulty is now the band, which is a property of the task rather than a guess.

A practical note recorded because it cost real time: ViennaRNA **segfaults** on an unbalanced
dot-bracket string rather than raising, so the evaluator checks balance before every call.

## Calibration ladder

Five development targets, 37 to 66 nucleotides, two or three branches. Measured on the benchmark
host with ViennaRNA 2.7.2.

| Designer | development |
|---|---:|
| Shipped baseline — unstructured poly-A | **0.0000** |
| Truth-blind reference — 60 random restarts scored by ensemble defect | **0.4197** |
| ViennaRNA `inverse_pf_fold`, best of three restarts | **1.0000** (by definition) |

The reference designer now reaches 42% of the way to the anchor instead of clearing it, which is
what an anchor should look like. Its ensemble defect is 0.0559 against the anchor's 0.00149.

## Evaluation cost

Target generation takes 33 s and the anchor another 30 s or so, both once per process. Because the
harness evaluates each proposal in a fresh process, that overhead is paid per proposal: observed
step wall times through the harness are 126 to 162 s against a 300 s timeout, leaving a candidate
roughly 140 s of its own.

This is the price of recomputing the anchor rather than quoting it, and it is worth stating rather
than hiding. It also bounds the ladder: level 3 targets are longer and `inverse_pf_fold` costs
about 10 s per target per restart, so a level beyond 3 would need either fewer targets or a
cheaper anchor.

Measured searcher behaviour at the shipped level: a `greedy_rewrite` run scores 0.91 to 0.98 by
its ninth proposal — working right at the community reference rather than four times past it,
which is what the same searcher did against the `inverse_fold` anchor.

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
