# Known best — RNAInverseDesign

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

A deterministic target-compatible local-search witness, scored by the same public objective as the
candidate and recomputed at evaluation time. Local search from a target-compatible start is a
strong classical baseline for inverse folding and is routinely beaten by better search, which is
what makes the headroom real.

| | score |
|---|---:|
| shipped baseline | 0.0000 |
| reference witness | 1.0000 |
| best recorded model run | 0.9996 |

This is the closest any recorded run has come to a witness on this inventory. Under the old cap
that 0.9996 was indistinguishable from having matched the witness exactly; it is now one
measurement away from telling us whether the searcher can pass it.
