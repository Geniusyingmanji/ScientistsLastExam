# Reference and admission record — EllipticCurveRecovery

## 1. Reference method

`verification/reference_solver.py` is standalone: ascending small primes queried
until the budget binds (eight units; the wide +-1200 window needs most of them),
per-prime enumeration of every (a mod p, b mod p) reproducing the returned count
by direct Legendre sums, incremental Chinese-remainder lifting with
coefficient-window pruning at each step (keeping the partial sets small instead of
exploding over the cartesian product), singular lift filtering, and refusal when
zero or multiple lifts survive. It deliberately lacks quadratic-form acceleration
and Hasse-interval reasoning.

## 2. Baseline and normalization

The shipped `solution.py` queries one prime and guesses (0, 1): `0.000000`. The
true pair scores one. Measured on 2026-09-05 the reference reaches `1.0000`
development and robustness with zero false discoveries and full refusal.

## 3. Capability comparisons and ablations

| variant | development |
|---|---:|
| full reference (budgeted ascending primes) | 1.000 |
| six primes in the wide window | 0.000 |

The wide window makes the prime ladder load-bearing: six primes leave twin curves
sharing all counts, the budget buys eight. Local debugging numbers, not frozen
benchmark evidence.

## 4. Shortcut probes

A fixed guess scores zero; residue enumeration over any single prime alone leaves
hundreds of candidates. No low-dimensional shortcut applies — the artifact is the
integer pair and the information budget is the difficulty.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the reference — the
residue-then-CRT strategy is the admission question.

## 6. Construction errors and revisions

Five construction errors were caught locally, the fifth in the 2026-09-06
difficulty rework. (i) A half-written compatibility shim never constrained
residues across primes. (ii) The cartesian CRT enumeration exploded once a fifth
prime was added — rebuilt incrementally with window pruning. (iii) Four primes
left twin-curve ambiguity on two development worlds. (iv) The point counter
dropped the y = 0 point at roots of the cubic (x^3 + 1 over F_11 counted 22
against the classical 12) — corrected in both the oracle and the reference, and
pinned against the classical value. (v) The difficulty audit judged the +-40
window knowledge-gated with budget to spare — the window widened to +-1200 and
primes repriced so the residue-then-CRT strategy now has to manage a real
information budget. All pinned in `tests/test_round4_new_tasks.py`.

## 7. Robustness and reproducibility

All counts are exact integer computations; determinism is arithmetic. Development
and held-out curves use fresh seeds. Formal Linux sandbox replay, global evidence
refresh and independent replication are pending.

## Reproduce

```bash
python scripts/measure_reference.py \
  --task Mathematics/EllipticCurveRecovery \
  --reference verification/reference_solver.py \
  --entry recover_curve
```
