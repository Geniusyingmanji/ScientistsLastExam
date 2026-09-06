# FrozenKernelProofFrontier — measured values

Every size here is a count of Hilbert lines replayed by `verification/evaluator.py`.

## Reference — `verification/reference_proofs.py`

Truth-blind: it returns compiled proofs of the four public theorems from the frozen
axiom allowlist. Sorry does not exist. Lean is not involved.

| theorem | compiled size | target size | compiled score |
|---|---:|---:|---:|
| identity | 5 | 3 | 0.833 |
| conjunction_swap | 26 | 14 | 0.593 |
| packed_composition | 35 | 18 | 0.476 |
| modus_ponens_closed | 20 | 11 | 0.661 |
| mean | | | **0.641** |

The reference is capability-complete for these four closed tautologies and
deliberately not at the wave-1 target sizes. Matching the compiled terms scores
about 0.64. A proof at the target sizes would score one; shorter still scores
above one.

## Baseline — `solution.py`

Cap-length valid proofs, score **0**. Construction: five lines proving `goal → goal`,
then a shifted copy of the reference derivation, then repeated modus ponens with that
implication so extra lines stay in the last line's dependency cone.

The first compiled-size lines of the baseline are **not** a proof of the theorem
(they prove `goal → goal`). Taking that prefix scores 0.

## Difficulty ladder

| ablation | combined_score | what was removed |
|---|---:|---|
| shipped baseline (length 64) | 0.000 | any shortening |
| hidden compiled proofs | 0.641 | — |
| prefix of compiled length | 0.000 | last line is not the theorem |

Per instance at the I+reference prefix: identity 0.915 (size 10), conjunction_swap
0.868 (size 31), packed_composition 0.828 (size 40), modus_ponens_closed 0.886
(size 25). Dropping the trailing pad without extracting the middle block does not
reach 1.

## Shortcut probe

Labeled `SHORT` proofs were removed from the visible baseline after review. A
searcher that still extracts the middle reference block (lines 5 through
`5+r-1`) scores 1.0; that is an on-ramp, recorded here, and the first thing the
red team tried after the prefix was hardened. Inventing a still-shorter identity
than SKK would exceed 1 on that instance; this probe did not.

## Model draws

Not run. No `batch_evolve.py --run-role calibration`. The admission line is
untested. A searcher that extracts the middle block would hit 1.0; a searcher
that only trims a prefix of length `r` scores 0.

## Construction errors

The gated design started at Tate-class statements in Lean/mathlib, which this
repository does not vendor. Closure count as `combined_score → ∞` was refused.
An earlier pad put the reference proof in the prefix, so deleting a suffix
recovered size `r` and scored 1; that was hardened to I-first padding. Trailing
unused K axioms were tried and dropped because they made the last line unequal
to the theorem. `padded_preview.json` from that broken pad was deleted.

## Robustness

Twelve malformed submissions — `None`, `{}`, a list, a string, a missing theorem,
`sorry`, an unknown axiom, an out-of-range MP index, a proof longer than the cap,
a float atom, a boolean posing as an axiom name, and a raising callable — all
score 0 with `valid = 0`, and none raises out of the evaluator.
