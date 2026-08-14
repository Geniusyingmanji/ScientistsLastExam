# Known best — TrussWeightMinimization

## Scoring

`combined_score` is `(baseline_weight - candidate_weight) / (baseline_weight - reference_weight)`,
floored at zero and **not capped above**. Zero is the shipped baseline, one is the reference
witness, and a design lighter than the witness scores above one.

The cap was removed because it made the witness the best achievable result: a lighter truss read
as exactly as good as the witness, and the task could report nothing about a searcher that had
beaten it. Every run recorded before the change scored at or below one, so their scores are
unchanged — removing the cap only stops the next result from being invisible.

The floor stays. Below the baseline is a worse design, not a negative achievement, and the
normalisation has no meaning there.

## Anchor

The reference is an independently calibrated multistart witness: feasible nominal and robust local
optima computed by the evaluator, not a number quoted from a paper. It is a strong classical
result and it is not optimal — that is what makes exceeding it a result rather than an overflow.

| | score |
|---|---:|
| shipped baseline (`solution.py`) | 0.0000 |
| reference witness | 1.0000 |
| best recorded model run | 0.6415 |

The best recorded searcher reaches 0.64 of the way from the baseline to the witness, so the
headroom this uncapping opens is not yet in reach — which is the right state for it to be in.

## Reproduce

```bash
python scripts/measure_reference.py --task Engineering/TrussWeightMinimization \
    --reference solution.py --entry design_truss
```

`tests/test_uncapped_scoring.py` pins the scoring property itself: matching the witness scores
exactly one, beating it scores above one, and the card and the scorer agree about which mode the
task is in.
