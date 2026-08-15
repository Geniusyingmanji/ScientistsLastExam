# Known best — MOSFETDoping

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

Fixed-seed 2048-point scrambled-Sobol screens followed by full compact-model evaluation, scored as
dominated hypervolume over the drive/leakage/area trade-off. The witness is a screen, not a
multi-objective optimiser.

| | score |
|---|---:|
| shipped baseline | 0.0000 |
| reference witness | 1.0000 |
| best recorded model run | 0.7397 |
