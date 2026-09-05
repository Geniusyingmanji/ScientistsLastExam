# Reference and admission record — EllipticCurveRecovery

## 1. Reference method

`verification/reference_solver.py` is standalone: six small primes (11, 13, 17, 19,
23, 29; total cost six units of eight), per-prime enumeration of every (a mod p,
b mod p) reproducing the returned count by direct Legendre sums, incremental
Chinese-remainder lifting with coefficient-window pruning at each step (keeping
the partial sets small instead of exploding over the cartesian product), singular
lift filtering, and refusal when zero or multiple lifts survive. It deliberately
lacks large-prime confirmation queries, quadratic-form acceleration and
Hasse-interval reasoning.

## 2. Baseline and normalization

The shipped `solution.py` queries one prime and guesses (0, 1): `0.000000`. The
true pair scores one. Measured on 2026-09-05 the reference reaches `1.0000`
development and robustness with zero false discoveries and full refusal.

## 3. Capability comparisons and ablations

| variant | development |
|---|---:|
| full reference (six primes) | 1.000 |
| five primes | 0.800 |
| four primes | 0.000 |

The prime ladder is load-bearing: four small primes leave twin curves that share
all counts, six resolve them. Local debugging numbers, not frozen benchmark
evidence.

## 4. Shortcut probes

A fixed guess scores zero; residue enumeration over any single prime alone leaves
hundreds of candidates. No low-dimensional shortcut applies — the artifact is the
integer pair and the information budget is the difficulty.

## 5. Frontier-model calibration

Not run. This task remains `candidate`. A clean Linux model draw, frozen before
exposure, must show that the first proposal does not reach the reference — the
residue-then-CRT strategy is the admission question.

## 6. Construction errors and revisions

Four construction errors were caught locally on 2026-09-05. (i) A half-written
compatibility shim never constrained residues across primes. (ii) The cartesian
CRT enumeration exploded once a fifth prime was added — rebuilt incrementally
with window pruning. (iii) Four primes left twin-curve ambiguity on two
development worlds — two more primes resolve it. (iv) The point counter dropped
the y = 0 point at roots of the cubic (x^3 + 1 over F_11 counted 22 against the
classical 12) — corrected in both the oracle and the reference, and pinned against
the classical value. All pinned in `tests/test_round4_new_tasks.py`.

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
