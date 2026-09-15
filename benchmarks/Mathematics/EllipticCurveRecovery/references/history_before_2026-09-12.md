# Archived construction history through 2026-09-08

The following records describe superseded worlds, scoring and references. Their
model-draw observations do not calibrate the current revision. Current evidence
and corrections are in `known_best.md` and `review_evidence.json`.

# Reference and admission record — EllipticCurveRecovery

Maintainer-facing. `frontier_eval/agent_files.txt` serves only `Task.md`,
`solution.py` and `frontier_eval/constraints.txt` (and `sle.spec`'s
`agent_visible_text()` composes the agent context from `Task.md` plus
`constraints.txt` only), so nothing in this file reaches candidates by
construction.

## 1. Reference method

`verification/reference_solver.py` is standalone: ascending small primes queried
until the budget binds (eight units; the wide +-1200 window needs most of them),
per-prime enumeration of every (a mod p, b mod p) reproducing the returned count
by direct Legendre sums, incremental Chinese-remainder lifting with
coefficient-window pruning at each step (keeping the partial sets small instead of
exploding over the cartesian product), singular lift filtering, and refusal when
zero or multiple lifts survive. It deliberately lacks quadratic-form acceleration
and Hasse-interval reasoning.

## 1a. Solution-family notes (maintainer-facing — never serve to candidates)

The intended strategy family, removed from the agent-visible `Task.md` on
2026-09-07 after a clean-room solver written from the old wording tied the
reference (0.750/0.750) in 0.4 s. `Task.md` now states phenomenon and interface
only; the recipe lives here:

- Each per-prime point count leaves a finite set of compatible pairs
  (a mod p, b mod p), and the Chinese remainder theorem combines enough residue
  sets to isolate a unique pair in the bounded integer window.
- The budget makes prime selection an information decision — small primes are
  cheap but occasionally leave twin curves, and one more prime resolves them.
- The reference realizes this as ascending small-prime queries within the
  budget, per-prime residue enumeration by direct Legendre sums, incremental CRT
  with coefficient-window pruning across the wide +-1200 window, and refusal
  when no nonsingular lift survives. Exact recovery from a smaller prime
  certificate can score above the full-budget reference under the efficiency
  multiplier.

## 2. Baseline and normalization

The shipped `solution.py` queries one prime and guesses (0, 1): `0.000000`. Supported
recovery is multiplied by `1 - 0.25 * budget_used / 8`; correct-refusal credit stays
unweighted and separately reported. The full-budget reference has evidence efficiency
`0.750`. Re-measured on 2026-09-06, it reaches `0.750000` development and robustness
with zero false discoveries and full refusal.

## 3. Capability comparisons and ablations

Re-measured on 2026-09-07 by truncating the reference's `QUERY_PRIMES` to the
first six small primes (11, 13, 17, 19, 23, 29; six budget units) and running
`verification/evaluator.py` directly, double-run deterministic:

| variant | development | held-out robustness |
|---|---:|---:|
| full reference (budgeted ascending primes) | 0.750 | 0.750 |
| six primes in the wide window | 0.4875 | 0.2708 |

Six primes do not collapse the score to zero: most supported worlds still lift
uniquely, but two development worlds (and two held-out worlds) leave twin curves
sharing all six counts, and the reference abstains on them — 0.4875 development
/ 0.2708 robustness with refusals intact and zero false discoveries. An earlier
record of `0.000` here was wrong (never reproducible); the wide window makes the
prime ladder load-bearing, not decisive on its own. Local debugging numbers, not
frozen benchmark evidence.

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
information budget. All pinned in `tests/test_elliptic_curve_recovery.py`.

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

## 8. 2026-09-08 clean-room first-proposal calibration (post-de-leak)

After the solution recipe was removed from the agent-visible `Task.md`
(commit b725249), an uncontaminated first-proposal draw was run under strict
candidate visibility: only `Task.md`, `solution.py`, `constraints.txt` and the
runner mechanics were read; `verification/` and `references/` stayed unread;
one designed proposal, at most three runner invocations (interface fixes only,
no score-driven tuning).

- **Result: combined_score 0.000, valid 0.** Development evidence efficiency
  0.5848, held-out 0.49375; all eight supported worlds across both splits were
  recovered exactly (intrinsic mechanism 1.0, budgets 5-6 of 8);
  development false-discovery rate 0.0; correct-refusal rate 0.0; robustness
  0.0. The proposal (per-prime residue tables over descending large primes,
  candidate-set filtering, singular-signature detection, medoid tie-breaks for
  the Q-isomorphism twins) solved every supported world without trial and
  error, but its query pattern invalidated all four refusal worlds; the one
  demonstrably safe query (a single `count_points(11)`, as the shipped
  baseline makes) was not rediscovered inside the run allowance.
- **Comparison:** the pre-de-leak wording produced a first proposal at
  0.750/0.750 (recorded in 1a). De-leaking moved the first-proposal combined
  score from tied-with-reference to zero.
- **Reading:** the recovery arithmetic remains implementation-grade for a
  frontier model; after de-leaking, admission pressure rests on (a) navigating
  the disclosed invalidation contract ("overspending or unknown primes
  invalidate the world even when caught") conservatively enough to keep
  refusal worlds valid, and (b) the refusal decision itself. This is a proxy
  draw run on macOS, not the sandboxed frozen-frontier draw the certification
  gate requires; that draw is still pending.

## 9. Scientific correction and fresh audit (2026-09-08)

The earlier refusal generator was scientifically wrong: a squarefree quartic
hyperelliptic model has genus one, its counter omitted affine roots, and it
always added two points at infinity regardless of the leading coefficient.
It is replaced by a monic degree-five polynomial, verified squarefree at every
queryable prime, with every affine root counted once and one point at infinity.
This is the odd-degree genus-two construction in [Sutherland’s definitions](https://math.mit.edu/~drew/Definitions.html).
Direct two-coordinate enumeration tests independently verify the point counter.
The earlier first-proposal observations in section 8 apply to the old, incorrect
refusal worlds and are **not admission evidence for this revision**. The full
reference still needs a fresh frozen model comparison.

The convenience runner now uses the trusted sandbox path. Fractional/bool prime
queries and fractional/bool coefficient claims fail closed; invalid rows no
longer count as discovery attempts. Confidence is checked against response
quality, and held-out rate denominators are published.
