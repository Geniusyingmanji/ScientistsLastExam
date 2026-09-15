# ChowlaCosineCertificate — certify a smaller global cosine bound

## Scientific problem

Choose `n_terms` distinct positive integer frequencies `A` and prove, for every real `x`,

```text
r + sum(a in A) cos(a*x) >= 0.
```

The artifact is the frequency set together with an exact rational squared-modulus certificate.
This is a finite optimization analogue of the Chowla cosine problem, not a claim about its
asymptotic conjecture. Bedert (arXiv:2509.05260v3) proves a current asymptotic polynomial bound;
this task instead scores exact certificates at three fixed sizes and frequency ceilings.

## Exact certificate

Implement `build_certificate(problem)`. Return

```python
{
    "frequencies": [a_1, ..., a_n],
    "bound": [numerator, denominator],
    "factors": [
        {
            "weight": [numerator, denominator],
            "terms": [[exponent, [numerator, denominator]], ...],
        },
        ...,
    ],
}
```

An integer may replace any rational pair. Booleans and floats are not integers here. Denominators
must be positive. Each factor represents a polynomial `q_j(z)=sum_e c_{j,e} z^e`, and the verifier
checks the complete Laurent identity

```text
r + sum(a in A) (z^a + z^(-a))/2
    = sum_j w_j q_j(z) q_j(z^(-1)).
```

All coefficients and weights are rational, every `w_j` is nonnegative, and equality is checked for
every signed Laurent exponent, including exponents outside `A`. Therefore setting `z=exp(i*x)`
proves the global inequality without angular sampling. Numerical search may propose a certificate,
but only the exact submitted identity is scored.

The three calls contain these public keys:

| key | meaning |
|---|---|
| `n_terms` | required number of distinct frequencies: 15, 28, or 45 |
| `max_frequency` | largest permitted frequency and factor exponent: 64, 128, or 256 |
| `max_factors` | maximum number of squared-modulus factors |
| `max_total_terms` | sum of sparse term counts across all factors |
| `max_pair_products` | sum of squared sparse term counts, bounding exact expansion work |
| `max_rational_bits` | bit cap for every raw integer in a rational |
| `max_denominator_lcm_bits` | bit cap for the LCM of all submitted raw denominators |
| `reference_bound` | exact `[numerator, denominator]` score-one reference bound |

Sparse exponents within a factor must be unique and nonnegative; sparse coefficients must be
nonzero. The submitted rational bound must satisfy `0 < bound <= n_terms`. The returned
`frequencies`, `bound`, and `factors` are all required. A malformed or false certificate scores zero
for that world and cannot remove it from the aggregate.

## Reference boundary

The frozen scale uses a constructive reference, not a proven finite optimum.
Reference artifacts and historical shortcut measurements are evaluator-side audit
resources; they are not supplied as a worked solution in this prompt. Published
constructions remain prior knowledge, so removing the worked example does not
establish task difficulty or contamination resistance.

## Scoring and limits

For a valid world,

```text
score = max(0, (n_terms - r) / (n_terms - reference_bound)).
```

The reported `combined_score` is the mean over all three worlds. The baseline uses
`A={1,...,n_terms}` and one factor `|1+z^a|^2/2` per frequency, proving `r=n_terms` and scoring zero.
The frozen constructive reference scores one. The scale is uncapped above one, although each fixed world is
mathematically bounded because `r>0`.

Score one is not a global best-known result. Historical shortcut measurements are
recorded in the evaluator-side audit, and admission remains unresolved. A larger score proves a
stronger bound for the submitted finite frequency set; it does not prove global optimality, improve
the best asymptotic exponent, or establish benchmark difficulty.

## Relation to other tasks

`DiscreteGeometry/SpherePackingCertificate` and `QuantumFoundations/BellBoundCertificate` also
score exact arguments, but their certificates bound packing density and noncommutative Bell
operators. This task checks a commutative Laurent identity for a constructed frequency set.
`Mathematics/CapSetFrontier` scores a finite combinatorial object rather than a proof of a global
trigonometric inequality. Epoch AI publishes a Chowla-family problem with a quantified asymptotic
target and sampled verification; the present task openly shares that family but uses fixed sizes,
frequency budgets, and exact rational certificates. No Chowla-cosine task was found in the checked
Frontier-Eng appendix or task catalogue as of 2026-09-06.
