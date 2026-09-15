# LyapunovDecayCertificate — prove a decay rate, do not just simulate one

## The question

A switched linear system jumps among a published list of 3-by-3 Hurwitz matrices
`A_i`. A common quadratic Lyapunov function `V(x) = x^T P x` with a positive rate
`alpha` is a proof that every trajectory decays at least as `e^{-alpha t / 2}` in
the `P`-norm, **regardless of how the modes switch**. Finding `P` and `alpha` is
the work; a numerical simulation of one switching signal is not a certificate.

Submit exact rational `P` and `alpha`. Floats are rejected, not rounded: a
numerical LMI dump is not a proof. Each published instance is a list of
independent Hurwitz matrices that are not permutation-conjugate, so averaging
over the cyclic group does not collapse `P` to a one-parameter line. After
homogeneity the common Gram is a genuinely five-parameter search: a
cyclic-symmetric ansatz is legal and cheap, and it is not competitive with a
catalog that shears different planes independently.

## What you implement

```python
def build_lyapunov(instance):
    ...
    return {
        "p11": [num, den], "p12": [num, den], "p13": [num, den],
        "p22": [num, den], "p23": [num, den], "p33": [num, den],
        "alpha": [num, den],
    }
```

`P = [[p11, p12, p13], [p12, p22, p23], [p13, p23, p33]]` must be positive
definite. For every mode, `A_i^T P + P A_i + alpha P` must be negative
semidefinite. Both tests are Sylvester / principal-minor criteria in exact
`Fraction` arithmetic.

The score of a valid certificate is `min(max(0, (alpha - 1/10000) / (3/4)), 1)`, averaged over the
four published instances. The identity Gram at `alpha = 1/10000` is valid and
scores exactly zero. There is no abstain flag: a failed certificate scores that
instance zero.

### `instance` keys

| key | meaning |
|---|---|
| `name` | instance label |
| `mode_matrices` | list of 3-by-3 modes; each entry is `[numerator, denominator]` |
| `state_dimension` | 3 |
| `max_numerator` | 10**6 |
| `max_denominator` | 10**6 |

### submission keys

| key | meaning |
|---|---|
| `p11`, `p12`, `p13`, `p22`, `p23`, `p33` | integer or `[numerator, denominator]` |
| `alpha` | positive integer or `[numerator, denominator]` |

## Relation and distinction

- Not `ControlTheory/InvertedPendulumSwingUp`: that designs a **controller** for
  a cart-pole. This submits a **proof** of decay for a published switched linear
  plant, with no actuation.
- Not `QuantumFoundations/BellBoundCertificate`: that is an SOS identity for a
  Bell functional. This is a common quadratic Lyapunov function for ordinary
  differential equations.
- Not `QuantumFoundations/FourSettingMomentCertificate`: that is a moment-subset
  SOS bound for a Bell functional. This is a common quadratic Lyapunov function
  for ordinary differential equations.
- Not `InformationTheory/ShannonCapacityCertificate`: that sandwiches an open
  graph capacity. This proves switching-independent ODE decay.
- Not the retired `DynamicalSystems/LyapunovControl`: that search was a small-N
  controller, saturated, and is not this certificate.

`SpherePackingCertificate` also verifies exact rational bounds; its objects are packing
certificates, while this task proves switching-independent ODE decay.

## Scoring

Mean proven `alpha - 1/10000` over the clip unit `3/4`, clipped to [0, 1]. Malformed submissions, floats, or
indefinite `P` score zero and never raise out of the evaluator. `sle.contract_lint`
is importable and free to call for shape checks. The evaluator independently checks the
certificate in exact arithmetic.
