# LyapunovDecayCertificate — prove a decay rate, do not just simulate one

## The question

A switched linear system jumps among a published list of 2-by-2 Hurwitz matrices
`A_i`. A common quadratic Lyapunov function `V(x) = x^T P x` with a positive rate
`alpha` is a proof that every trajectory decays at least as `e^{-alpha t / 2}` in
the `P`-norm, **regardless of how the modes switch**. Finding `P` and `alpha` is
the work; a numerical simulation of one switching signal is not a certificate.

Submit exact rational `P` and `alpha`. Floats are rejected, not rounded: a
numerical LMI dump is not a proof.

## What you implement

```python
def build_lyapunov(instance):
    ...
    return {"p11": [num, den], "p12": [num, den], "p22": [num, den],
            "alpha": [num, den]}
```

`P = [[p11, p12], [p12, p22]]` must be positive definite. For every mode,
`A_i^T P + P A_i + alpha P` must be negative semidefinite. Both tests are
Sylvester criteria in exact `Fraction` arithmetic.

The score of a valid certificate is `min(alpha / (3/4), 1)`, averaged over the
four published instances. The identity Gram at `alpha = 1/10000` is valid and
scores near zero. There is no abstain flag: a failed certificate scores that
instance zero.

### `instance` keys

| key | meaning |
|---|---|
| `name` | instance label |
| `mode_matrices` | list of 2-by-2 modes; each entry is `[numerator, denominator]` |
| `state_dimension` | 2 |
| `max_numerator` | 10**6 |
| `max_denominator` | 10**6 |

### submission keys

| key | meaning |
|---|---|
| `p11`, `p12`, `p22` | integer or `[numerator, denominator]` |
| `alpha` | positive integer or `[numerator, denominator]` |

## Relation and distinction

- Not `ControlTheory/InvertedPendulumSwingUp`: that designs a **controller** for
  a cart-pole. This submits a **proof** of decay for a published switched linear
  plant, with no actuation.
- Not `QuantumFoundations/BellBoundCertificate`: that is an SOS identity for a
  Bell functional. This is a common quadratic Lyapunov function for ordinary
  differential equations.
- Not the retired `DynamicalSystems/LyapunovControl`: that search was a small-N
  controller, saturated, and is not this certificate.

## Scoring

Mean proven `alpha` over the clip unit `3/4`. Malformed submissions, floats, or
indefinite `P` score zero and never raise out of the evaluator. `contract_lint`
is the exact-arithmetic rejection of floats and of a Gram that does not certify.
