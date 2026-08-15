# Known best — DiffractionGratingDesign

## Scoring

`combined_score` is `(value - baseline) / (reference - baseline)`, floored at zero and **not
capped above**. Zero is the shipped baseline, one is the reference witness, and a result better
than the witness scores above one.

The cap made the witness the best achievable score: a better result read as exactly as good as the
witness, and the task could report nothing about a searcher that had beaten it. Every run recorded
before the change scored at or below one, so their scores are unchanged. The floor stays, because
below the baseline is a worse result rather than a negative achievement.

`tests/test_uncapped_scoring.py` walks the inventory and fails if any task declared uncapped still
clips its normalisation at one.

## Anchor

A calibrated five-layer RCWA witness, with nominal and robust performance replayed separately by
the evaluator. Five layers is a design choice rather than a limit, so the witness is a strong
rigorous-solver result and not an optimum.

| | score |
|---|---:|
| shipped baseline | 0.0000 |
| reference witness | 1.0000 |
| best recorded model run | 0.5421 |

## A caveat this task carries

`scripts/audit_theme_fit.py` flags this task's card for describing its reference in terms a correct
implementation could reach. Uncapping does not settle that: if the witness turns out to be
one-shot reachable, the headroom above it is what the task has left, and the card needs the
stronger claim removed rather than the score reinterpreted.
