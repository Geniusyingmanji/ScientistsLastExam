# FrozenKernelProofFrontier — proof-size search in a frozen propositional kernel

## Status and claim boundary

This is a **first-wave conversion** of FormalResearchProof. Lean, mathlib, and any
statement whose library is not frozen in this repository (Tate, Birch–Tate, FLT,
Poincaré) stay gated. Closures of a kernel are not `combined_score → ∞`. The
continuous score here is **proof-term size** against a frozen axiom allowlist.

## Scientific setting

The kernel is a classical Hilbert system for implication and conjunction on three
atoms `A`, `B`, `C`. The only axioms are schemas `K`, `S`, `ANDI`, `ANDEL`,
`ANDER`. The only rule is modus ponens. There is no `sorry`.

Four closed tautologies, all library-ready and not number-theoretic:

| name | theorem | reference size |
|---|---|---:|
| `identity` | `A → A` | 5 |
| `conjunction_swap` | `(A ∧ B) → (B ∧ A)` | 26 |
| `packed_composition` | `((A→B) ∧ ((B→C) ∧ A)) → C` | 35 |
| `modus_ponens_closed` | `((A→B) ∧ A) → B` | 20 |

The shipped baseline is a valid proof of each, length 64. It starts by proving
`goal → goal`, then a longer derivation, then repeated MP so extra lines stay in
the last line's dependency cone. The first `reference_size` lines are not a proof
of the theorem. Returning the baseline scores zero. Shorter valid proofs score
more. A proof shorter than the reference scores above one.

## Your task

Implement:

```python
def build_proofs(problem):
    """Return {theorem_name: [line, ...]}."""
```

`problem` contains:

| key | value |
|---|---|
| `size_cap` | 64 |
| `axiom_names` | `["K", "S", "ANDI", "ANDEL", "ANDER"]` |
| `atoms` | `["A", "B", "C"]` |
| `theorems` | list of `{name, theorem, size_cap, axiom_names, atoms, reference_size}` |

Each `theorem` is a nested list: an atom, or `["imp", left, right]`, or
`["and", left, right]`.

A proof line is either

```text
{"axiom": "K"|"S"|"ANDI"|"ANDEL"|"ANDER", "subst": {"X": formula, "Y": formula, "Z": formula?}}
```

or

```text
{"mp": [antecedent_index, implication_index]}
```

`S` needs `Z`. Indices refer to earlier lines (0-based). The last line must equal
the theorem. Proofs longer than `size_cap` are rejected.

K is `X → (Y → X)`. S is `(X → (Y → Z)) → ((X → Y) → (X → Z))`.
ANDI is `X → (Y → (X ∧ Y))`. ANDEL / ANDER project a conjunction.

## Scoring

For a valid proof of size `n` and reference size `r`,

```text
(size_cap - n) / (size_cap - r)
```

Mean over the four theorems. Invalid proofs score zero on that theorem.

## Difficulty ladder

Measured on this package:

| ablation | combined_score |
|---|---:|
| baseline, length 64 | 0.000 |
| drop trailing MP only (keep I plus the inner derivation) | 0.874 |
| hidden reference proofs | 1.000 |
| take the first `reference_size` lines of the baseline | 0.000 |

The inner derivation is not a prefix. Extracting it still scores one; that is a
known on-ramp, not a frontier result.

## Tools and scope

- Standard library only is enough. NumPy/SciPy are available.
- Only edit `solution.py`; keep `build_proofs(problem)`.
- Do not read `verification/` or `frontier_eval/`.
- Do not claim this is a Lean kernel or a proof of an open conjecture.

## Relation to nearby tasks

- FormalResearchProof on Tate-class statements stays gated: no frozen Lean/mathlib
  here, and closure count is the wrong score.
- Bell and sphere-packing certificates are analytic SOS / Cohn–Elkies identities,
  not Hilbert proof size.
