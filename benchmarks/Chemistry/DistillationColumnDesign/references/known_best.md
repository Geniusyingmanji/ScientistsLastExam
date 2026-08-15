# Known best — DistillationColumnDesign

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

Separately calibrated fixed-seed nominal-cost and off-design-robust mixed-integer witnesses,
recomputed at scoring time. Cost is minimised, so the normalisation runs
`(baseline_cost - candidate_cost) / (baseline_cost - reference_cost)`.

| | score |
|---|---:|
| shipped baseline | 0.0000 |
| reference witness | 1.0000 |
| best recorded model run | 0.9960 |
