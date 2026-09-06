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
curve_family      y^2 = x^3 + a*x + b, |a|,|b| <= 1200, nonzero discriminant
prime_list        the queryable primes
cost_tiers        prime <= 100 costs 1, <= 1000 costs 2, otherwise 3
budget_units      6
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
only: ascending small-prime queries within the budget, per-prime residue enumeration
by direct Legendre sums, incremental CRT with coefficient-window pruning across
the wide +-1200 window, and refusal when no nonsingular lift survives. Local shortcut and ablation diagnostics are recorded in
`references/known_best.md`; they do not replace clean Linux sandbox replay,
independent review or a frozen frontier-model calibration draw.

## Frontier-Eng overlap comparison (2026-09-06)

无. Nearest catalog entries: AES-128 CTR; SHA-256; SHA3-256. Query finite-field point counts at chosen primes and recover an integer elliptic-curve coefficient pair or refuse. FE implements symmetric cryptographic throughput, with no arithmetic-geometry inverse problem.

See `.research/pr9_frontier_eng_overlap_2026-09-06.md` for the pinned 47-task paper and complete available repository catalog. The requested 95-entry source could not be reconciled with the available 78 rows (84 expanded tasks); source reconciliation and maintainer acceptance remain pending.
