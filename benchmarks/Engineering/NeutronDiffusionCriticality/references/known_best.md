# Known best — NeutronDiffusionCriticality

## Scoring

`combined_score = (k_eff - k_uniform) / (k_reference - k_uniform)`, floored at zero and **not
capped above**. Zero is a uniform 5% loading, one is the reference witness, and a loading more
reactive than the witness scores above one.

The cap made the witness the best achievable score. Every run recorded before the change scored at
or below one, so their scores are unchanged. The floor stays: less reactive than uniform is a worse
design, not a negative achievement.

## Anchor

A reproducible symmetric multistart constrained optimisation, recomputed by the evaluator as
`_compute_keff(REFERENCE_LOADING)` rather than quoted. Multistart local optimisation under a mean
enrichment constraint is a strong classical result and not a bound on reactivity, which is what
makes exceeding it a result rather than an overflow.

| | score |
|---|---:|
| uniform 5% loading | 0.0000 |
| reference witness | 1.0000 |
| best recorded model run | 0.9675 |

At 0.9675 the best recorded searcher is close enough that the cap was about to start hiding
results.

## Reproduce

```bash
python scripts/measure_reference.py --task Engineering/NeutronDiffusionCriticality \
    --reference solution.py --entry optimize_enrichment
```
