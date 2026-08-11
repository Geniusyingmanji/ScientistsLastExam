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
reaches parity and restarting it is only doing what the anchor already did.

## Anchors at the shipped level

| Target | length | branches | baseline defect | anchor defect | anchor reaches target |
|---|---:|---:|---:|---:|---|
| `t0_b1_n24` | 24 | 1 | 0.8333 | 0.0051 | yes |
| `t1_b2_n49` | 49 | 2 | 0.7347 | 0.0958 | yes |
| `t2_b3_n66` | 66 | 3 | 0.7273 | 0.0451 | yes |
| `t3_b1_n30` | 30 | 1 | — | — | yes |
| `t4_b2_n50` | 50 | 2 | — | — | yes |
| `t5_b3_n69` | 69 | 3 | — | — | yes |

The baseline defect near 0.75 against an anchor defect near 0.03 is why the score is a log ratio:
a linear normalisation would spend its whole range on the gap between doing nothing and reaching
the reference, and compress the region above 1.0 where the work is.

## Calibration ladder

| Designer | development | sealed |
|---|---:|---:|
| Shipped baseline — unstructured poly-A | **0.0000** | 0.0000 |
| Truth-blind reference — 60 random restarts scored by ensemble defect | **1.3506** | — |
| ViennaRNA `inverse_fold`, best of ten restarts | **1.0000** (by definition) | 1.0000 |

The reference designer clears the anchor, and that is the finding rather than a defect: optimising
the objective that is scored beats optimising a proxy for it, even with an unsophisticated search.
This is the same reason NUPACK-style design targets ensemble defect directly. It also sets a real
bar — the reference is 60 restarts of constrained random sampling, so a candidate has to do better
than that to exceed 1.35.

## Difficulty levels

`DIFFICULTY` in `verification/evaluator.py` selects the target generator. Level 1 is shipped. A
level with no entry raises rather than being extrapolated.

| Level | target lengths | branches | truth-blind reference |
|---:|---|---|---:|
| 1 | 24–69 | 1–3 | 1.3506 |
| 2 | 59–103 | 2–4 | 1.1937 |
| 3 | 84–146 | 3–5 | 1.1028 |

The reference's margin over the anchor narrows as targets grow, which is the ladder behaving: the
anchor stays strong (it reaches the target structure on every level) while random restart runs out
of room. Sealed targets move with the level and use a separate generator seed.

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
