# Known best — RANSCalibration

## Scoring

`combined_score` normalises the calibration loss: `(baseline_loss - loss) / (baseline_loss -
reference_loss)`, floored at zero and **not capped above**. Zero is the shipped baseline, one is
the calibrated reference witness, and a closure that fits better than the witness scores above one.

The cap was removed because the reference is a witness rather than a bound. A better closure read
as exactly as good as the witness, and the task could report nothing about a searcher that had
beaten it. Every run recorded before the change scored at or below one, so their scores are
unchanged. The floor stays: a loss worse than the baseline is a worse calibration, not a negative
achievement.

## Anchor

Independently calibrated development nominal and worst-shift witnesses, recomputed by the
evaluator. The task asks for a *transferable* closure — the objective spans four friction Reynolds
numbers and the higher two are evaluator-only — so a witness calibrated on the development pair is
strong without being the best possible transfer.

| | score |
|---|---:|
| shipped baseline | 0.0000 |
| reference witness | 1.0000 |
| best recorded model run | 0.3277 |

## Reproduce

```bash
python scripts/measure_reference.py --task Engineering/RANSCalibration \
    --reference solution.py --entry calibrate_closure
```
