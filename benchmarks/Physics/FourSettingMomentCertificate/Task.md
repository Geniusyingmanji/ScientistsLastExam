# FourSettingMomentCertificate — exact SOS on I_4422^{13} with a frozen moment pool

## Scientific setting

Alice and Bob each have four binary measurements. Brunner and Gisin (arXiv:0711.3362)
list 26 tight Bell inequalities for that scenario. This task uses **`I_{4422}^{13}`**,
printed in full in that paper's Appendix A, not `I3322` and not a free word-budget SOS
on the sibling `BellBoundCertificate` task.

The Collins–Gisin table is

```
         |  -2  -1  -1   0
    ---------------------
     -2  |   0   1   1   1
     -1  |   1  -2   1   1
     -1  |   1   1  -1   1
      0  |   1   1   1  -1     ≤ 0
```

Converted to ±1 correlators by `P(A)=(1+a)/2` and `P(AB)=(1+a+b+ab)/4`, then multiplied
by 4 to clear denominators. Exhaustive enumeration of the 256 deterministic strategies
gives classical maximum **0**. The affine form `1 + I_CG` is quoted in arXiv:1811.11820
as `L=1`, `Q=1.25`, so the two-qubit quantum value of `I_CG` is **0.25**. A certificate
proving a bound below 0.25 is reported, not scored.

The open part is **which extra NPA-2 moments to spend a Hamming-weight budget on**.
The frozen pool is every length-2 same-party word (`A_i A_k` for `i≠k` and `B_j B_l`
for `j≠l`): 24 words. Each instance allows at most `k` extras from that pool, on top
of the nine NPA-1 words (identity, four `A`'s, four `B`'s). Free words outside the pool
are rejected. That is a different identity from `BellBoundCertificate`, which lets the
basis be any reduced words up to a letter cap.

The evaluator never solves an SDP. Floats are rejected.

## Your task

Implement:

```python
def build_certificate(instance):
    """Return {"basis": [...], "squares": [{"weight": ..., "vector": ...}, ...]}."""
```

`instance` contains:

| key | value |
|---|---|
| `name`, `settings` | instance id and `(4, 4)` |
| `functional` | correlator coefficients of the ×4 stored form |
| `scale`, `offset` | reported bound is `(beta + offset) / scale` |
| `extra_budget` | Hamming weight `k` of extra moments |
| `moment_pool` | the frozen list of allowed extra words `[[A-letters, B-letters], ...]` |
| `max_basis` | `9 + extra_budget` |
| `max_squares`, `max_word_letters` | caps |
| `max_numerator`, `max_denominator` | rational magnitude caps |
| `free_bound` | triangle bound 4, the zero of the scale |
| `catalog_sos_bound` | catalog SOS 3.5; the pairing grid reaches this and scores ~0.46 |
| `score_one_bound` | wave-1 evaluator target 3.0, not a published NPA-2 number |
| `published_target_bound` | same as `score_one_bound` |
| `best_known_quantum_value` | 0.25 |

`basis` words are `[A-letters, B-letters]` with setting indices in `{0,1,2,3}`, already
reduced (`A_i A_i` is illegal). Extra words must occur in `moment_pool`. Weights and
vector entries are integers or `[numerator, denominator]` pairs.

## Scoring

Mean over three budgets `k=4,8,12` of logarithmic progress in the gap to 0.25:

```text
(log10(4 - 0.25) - log10(bound - 0.25)) / (log10(4 - 0.25) - log10(3.0 - 0.25))
```

Triangle scores zero. Score one is hung at certified bound 3.0, which is a wave-1
evaluator target, not a published NPA-2 number. The catalog SOS at 3.5 scores about
0.46. Stronger exact certificates score above one. Below 0.25 is reported and
scored zero.

## Difficulty ladder

| ablation | bound | combined_score |
|---|---:|---:|
| triangle, no extras | 4.00 | 0.000 |
| one CHSH block | 3.75 | 0.222 |
| two CHSH blocks (catalog) | 3.50 | 0.461 |
| score-one wave target | 3.00 | 1.000 |

A 36-point grid over A/B pairings and signs finds the catalog on 2 of 36 points
(score 0.46, does not reach 3.0). Beating 3.0 needs a different SOS.

## Tools and scope

- NumPy/SciPy only. No CVXPY, no MOSEK, no network.
- Only edit `solution.py`; keep `build_certificate(instance)`.
- Do not read `verification/` or `frontier_eval/`.

## Relation to nearby tasks

- **BellBoundCertificate** is I3322 plus CHSH, with a free word budget. This functional
  is `I_4422^{13}` and the extras are a Hamming subset of a frozen pool.
- Sphere packing certificates are Cohn–Elkies functions, not Bell SOS.
