# Known best — ElectrolyteConductivityDesign

## Scoring

`combined_score` is `(value - baseline) / (reference - baseline)`, floored at zero and **not
capped above**. Zero is the shipped baseline, one is the reference witness, and a result better
than the witness scores above one.

The cap was removed because it made the witness the best achievable score: a better result read
as exactly as good as the witness, and the task could report nothing about a searcher that had
beaten it. Every run recorded before the change scored at or below one, so their scores are
unchanged — removing the cap only stops the next result being invisible. The floor stays, because
below the baseline is a worse result rather than a negative achievement.

`tests/test_uncapped_scoring.py` walks the inventory and fails if any task declared uncapped still
clips its normalisation at one, so the card and the scorer cannot drift apart.

## Anchor

An exhaustive three-formulation search over the two discovery-assay repeats, recomputed at scoring
time. It is exhaustive within the assayed set and not within the formulation space.

| | score |
|---|---:|
| shipped baseline | 0.0000 |
| reference witness | 1.0000 |
| best recorded model run | 0.7544 |
