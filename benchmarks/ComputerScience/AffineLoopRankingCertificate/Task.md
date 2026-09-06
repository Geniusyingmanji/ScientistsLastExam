# AffineLoopRankingCertificate — prove a loop ranks, do not just run it

## The question

An integer affine while-loop is published in full: a conjunction of linear
guards `g_i · x + d_i ≥ 0` and an update `x := A x + b`. A linear ranking
function `ρ(x) = r · x + s` with a positive `delta` is a proof that **every**
guard-satisfying state descends by at least `delta`, independently of any
start state you might simulate.

Submit exact rationals. `r` must have 1-norm exactly 1 so that `delta` is
comparable across directions. Floats are rejected, not rounded: a numerical
LP dump is not a certificate. The two implications are proved by Farkas
multipliers, not by sampling states.

## What you implement

```python
def build_ranking(instance):
    ...
    return {"r": [[num, den], ...], "s": [num, den], "delta": [num, den],
            "nonneg_lambdas": [[num, den], ...],
            "decrease_lambdas": [[num, den], ...]}
```

Let `ρ(x) = r·x + s`. The multipliers must witness, in exact `Fraction`
arithmetic:

1. `ρ ≥ 0` on the guard polyhedron: `r = Σ λ_i g_i` and
   `s - Σ λ_i d_i ≥ 0` with `λ ≥ 0`.
2. `ρ(x) - ρ(Ax+b) ≥ delta` on the same polyhedron, with a second multiplier
   vector `μ ≥ 0`.

The score of a valid certificate is `min(delta / 3, 1)`, averaged over the
four published loops. The first standard-basis ranking at `delta = 1/10000`
is valid and scores near zero. There is no abstain flag: a failed certificate
scores that instance zero.

### `instance` keys

| key | meaning |
|---|---|
| `name` | instance label |
| `dimension` | 2 or 3 |
| `guards` | list of `{g, d}` with `g·x + d ≥ 0`; each entry `[numerator, denominator]` |
| `A` | affine update matrix, same rational encoding |
| `b` | affine update offset |
| `max_numerator` | 10**6 |
| `max_denominator` | 10**6 |

### submission keys

| key | meaning |
|---|---|
| `r` | ranking slope, 1-norm exactly 1 |
| `s` | ranking constant |
| `delta` | positive uniform decrease |
| `nonneg_lambdas` | Farkas multipliers for `ρ ≥ 0`, one per guard |
| `decrease_lambdas` | Farkas multipliers for the decrease |

## Relation and distinction

- Not `ControlTheory/LyapunovDecayCertificate`: that is a **continuous**
  quadratic Lyapunov function for a switched ODE. This is a **discrete**
  linear ranking function for an integer affine loop, with a 1-norm
  normalisation that Lyapunov does not need.
- Not `Algorithm/GraphFromDistances`: that recovers a graph from queries.
  This submits a proof of termination, not a graph.
- Not `Algorithm/MatrixMultiplicationRank`: a bilinear decomposition, not a
  ranking function.

## Scoring

Mean proven `delta` over the clip unit `3`. Malformed submissions, floats, a
ranking whose 1-norm is not 1, or a Farkas identity that does not hold score
zero and never raise out of the evaluator. `contract_lint` is the
exact-arithmetic rejection of floats and of a multiplier vector that does
not certify.
