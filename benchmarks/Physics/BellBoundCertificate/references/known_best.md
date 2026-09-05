# BellBoundCertificate — measured values

All numbers here were produced by `verification/` in this package and are reproducible from it.

## Anchors (published, not measured here)

| quantity | value | source |
|---|---|---|
| I3322 classical bound | 0 | arXiv:2607.14755 §3.1 |
| I3322 NPA level 1 | 0.37500001 | arXiv:2607.14755 §3.1 |
| I3322 NPA level 2 | 0.25102173 | arXiv:2607.14755 §3.1 |
| I3322 best known quantum value | 0.25087538 | arXiv:2607.14755 §3.1, at NPA4 or higher |
| I3322 two-qubit maximum | 1/4 | Pál & Vértesi, arXiv:1006.3032 |
| CHSH quantum maximum | 2√2 | Tsirelson (1980) |

## The transcription trap, and how it was caught

arXiv:2607.14755 eq. (18) is introduced as "the correlator representation", and read that way its
coefficients give a classical bound of **8**, not the 0 the same paragraph states. It is the
Collins–Gisin *probability* form. Substituting `P(A_i B_j) = (1 + a_i + b_j + c_ij)/4` and
`P(A_i) = (1 + a_i)/2` gives a ±1 correlator functional whose classical bound, by exhaustive
enumeration over all 64 deterministic strategies, is exactly 0.

Three independent checks then confirm the converted form is the right one:

| check | expected | measured here |
|---|---|---|
| classical bound | 0 | 0 |
| level-1 relaxation | 0.37500001 | 0.37500000 |
| two-qubit maximum | 0.25 | 0.250000000 |

The two-qubit check is the sharpest: I3322's qubit maximum being exactly 1/4 — strictly below the
0.2508754 that needs higher dimensions — is a published fact that a mis-transcribed functional
would not reproduce to nine digits.

## Baseline and reference

| | chsh | i3322_k12 | i3322_k24 | i3322_k40 | mean |
|---|---|---|---|---|---|
| baseline bound | 4.0 | 2.0 | 2.0 | 2.0 | |
| baseline score | 0.000 | 0.000 | 0.000 | 0.000 | **0.000000** |
| reference bound | 2.8284271389 | 0.3638022212 | 0.2512382622 | 0.2509552200 | |
| reference score | 0.5236 | 0.0140 | 0.8653 | 1.0899 | **0.623217** |

The baseline is the triangle inequality written as squares: valid on every instance, proving
exactly the algebraic bound, scoring exactly zero. That is the point of it — the recallable content
of this task ("the answer is about 0.2508754") is worth nothing, because what is scored is a
certificate at a budget and no table contains one.

The reference beats the published NPA level-2 bound on the largest budget (0.25095522 against
0.25102173) and therefore scores above 1 there. That is the uncapped scale working as intended, not
an error: the certificate is checked in exact rational arithmetic, so the bound is a proof, and a
40-word basis with two-letter words is richer in some directions than the level-2 moment matrix.

`i3322_k12` at 0.014 is the hard rung. Twelve words is below the sixteen of the "almost quantum"
level, and the greedy shortest-first basis the reference uses gets almost nothing out of the budget.
This is the instance where the moment-selection result of arXiv:2607.14755 — a non-monotone
landscape with real synergy between moments — should bite hardest.

## Where the headroom is

The reference is deliberately the obvious procedure, and each of its four steps is beatable:

1. **Basis selection is greedy.** Shortest-first is exactly the strategy the exhaustive enumeration
   in arXiv:2607.14755 beats. This is the largest single source of headroom, and it is a
   combinatorial problem sitting on top of the numerical one.
2. **The numerical solve is a quasi-Newton method on `Q = RᵀR` with a penalty.** A real
   interior-point method, or one exploiting the structure of this affine set, converges closer to
   the boundary.
3. **Rounding is uniform at 1e-9.** Denominator choice per entry, or lattice reduction, does better.
4. **Feasibility is repaired with a diagonal shift**, which is charged straight to the bound. A
   repair that moves within the null space of the constraints costs less.

## Discarded designs

**A 100-word budget.** Cut because exact verification of a *submitted matrix* at that size is
unbounded in cost — rational elimination grows entries with the input's values, not its size, so a
well-formed submission could hold the grader indefinitely. The fix was representational rather than
dimensional: the certificate is now submitted as the squares, positive semidefiniteness is free,
and the oracle's work is `MAX_SQUARES × max_basis²` multiplications with capped entries — 0.28 s
measured at the largest instance.

**A tilted-CHSH instance.** The closed form recalled for its quantum value, `√(8 + 2α²)`, did not
match an independent level-1 solve for any `α > 0` (3.354 against 2.915 at `α = 1/2`). Either the
formula or the level's tightness was misremembered, and no primary source was on hand to settle it,
so the instance was dropped rather than shipped on a number nobody had checked.

**Alternating projections as the reference solver.** Dykstra converges sublinearly at the cone
boundary: 40 000 iterations still left a residual of 7e-5 at the true CHSH bound, and the resulting
certificate landed 4e-2 above 2√2. The factored quasi-Newton solve reaches 1e-7 on the same basis in
under a second. Kept as a fallback for bases where the factored solve finds nothing feasible.

## Robustness

Eighteen degenerate and adversarial submissions — floats for weights, floats for vector entries,
negative weights, all-zero vectors, the identity-only basis, duplicated words, an unreduced word
`A₀A₀`, an over-budget basis, a 5000-digit rational aimed at the verifier's running time, a zero
denominator, a boolean posing as an integer, an out-of-range setting index, a callable that always
raises, mismatched vector lengths, an empty basis, an empty square list, `None`, and `{}` — all
score 0.000000 with `valid = 0`, and none raises out of the evaluator.

The float rejection is load-bearing. Accepting floats and rounding them would have turned the task
into "call an SDP solver", which is the failure that killed the certificate half of
`Mathematics/NonlinearCodeRecords`.
