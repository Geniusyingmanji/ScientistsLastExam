# EllipticCurveRecovery — recover curve coefficients from prime point counts

## Scientific setting

An elliptic curve y^2 = x^3 + ax + b is determined by its point counts modulo
primes: each count pins the pair (a mod p, b mod p), and the Chinese remainder
theorem lifts enough residues into the bounded integer window. The budget makes
prime selection an information decision — small primes are cheap but occasionally
leave twin curves, one more prime resolves them — and two worlds break the
elliptic premise: a singular cubic and a genus-two quartic whose counts no pair
(a, b) reproduces.

## Your task

```python
def recover_curve(problem, count_points, budget_units):
    """Return {"a": int, "b": int within public bounds, "abstain": bool,
               "confidence": float in [0,1]}."""
```

`problem` is a mapping with the keys

```text
curve_family      y^2 = x^3 + a*x + b, |a|,|b| <= 40, nonzero discriminant
prime_list        the queryable primes
cost_tiers        prime <= 200 costs 1, <= 2000 costs 2, otherwise 3
budget_units      8
answer_semantics  the oracle returns #E(F_p) exactly
refusal_note      singular cubics and genus-two quartics must be refused
```

`count_points(prime)` charges by tier and returns `{prime, point_count,
budget_cost}`. Overspending or unknown primes invalidate the world even when
caught.

## Evaluation

- `combined_score` is development coefficient recovery above the always-abstain
  baseline: exp(-6 x normalized total absolute error of a and b).
- Singular and genus-two worlds score refusal only; abstaining scores one and any
  coefficient claim scores zero.
- False discovery rate, correct refusal rate and discovery coverage are reported
  with denominators; a full abstention scores exactly zero.
- `robustness_score` repeats the audit on held-out curves and failures.

This is exact integer arithmetic, not a numerical experiment.

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy/stdlib code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Oracle errors and overspending invalidate the world even when caught.
- Use `sle.contract_lint` for free local shape checks before returning an inference.

Reference: Silverman, *The Arithmetic of Elliptic Curves*, ISBN `9780387094939`.

## 关系与区别 / Relationship to nearby tasks

SequenceLawRecovery infers recurrences from integer terms; ExactIdentityEvidence
certifies identities from purchasable digits. This task inverts exact arithmetic
objects — point counts over finite fields — with prime-selection economics, CRT
lifting into a bounded window, and refusal worlds that break the curve family
itself.

## Admission and reference scope

This package remains **candidate**. The runnable reference uses public inputs
only: six small-prime queries, per-prime residue enumeration by direct Legendre
sums, incremental CRT with coefficient-window pruning, and refusal when no
nonsingular lift survives. Local shortcut and ablation diagnostics are recorded in
`references/known_best.md`; they do not replace clean Linux sandbox replay,
independent review or a frozen frontier-model calibration draw.
