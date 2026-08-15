# Known best — CalorimeterDesign

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

Separately calibrated fixed-seed nominal and worst-shift witnesses across a seven-instance archive,
recomputed by the evaluator.

| | score |
|---|---:|
| shipped baseline | 0.0000 |
| reference witness | 1.0000 |
| best recorded model run | 1.0000 |

The best recorded run **reaches** the witness, which is exactly the case the cap used to hide: at
1.0000 under a capped score there was no way to tell a searcher that had matched the witness from
one that had passed it. That run came after this task's input keys were documented — before that
it could not produce a single valid proposal.
