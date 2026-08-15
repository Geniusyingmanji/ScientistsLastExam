# Known best — HeatExchangerDesign

## Scoring

`combined_score` normalises between two anchors — zero at the shipped baseline, one at the
reference witness — floored at zero and **not capped above**. A result better than the witness
scores above one.

The cap made the witness the best achievable score, so a better result read as exactly as good as
the witness and the task could report nothing about a searcher that had beaten it. Every run
recorded before the change scored at or below one, so their scores are unchanged. The floor stays,
because below the baseline is a worse result rather than a negative achievement.

`tests/test_uncapped_scoring.py` walks the inventory and fails if any task declared uncapped still
clips its normalisation at one.

## Anchor

A fixed-seed 4096-point scrambled Sobol proxy screen followed by an exact-model shortlist, scored
as dominated hypervolume. A Sobol screen is a strong sampling result and not an optimiser, which
is what leaves room above it.

| | score |
|---|---:|
| shipped baseline | 0.0000 |
| reference witness | 1.0000 |
| best recorded model run | 1.0000 |
