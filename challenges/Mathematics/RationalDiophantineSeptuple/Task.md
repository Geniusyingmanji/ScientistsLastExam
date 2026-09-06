# Positive Rational Diophantine Septuple

Find **seven distinct positive rational numbers** such that the product of any
two distinct entries plus 1 is the square of a rational number. Only the 21
off-diagonal pairs are constrained. This is a binary research-object challenge,
separate from the continuous-score SLE inventory.

Submit a JSON list containing exactly seven strings. Each string must contain
an ASCII decimal integer `p` or fraction `p/q`, with positive `p` and `q`.
Decimal points, exponents, signs, whitespace inside a string, formulas, floating
point values, and nonfinite values are rejected. Leading zeros and unreduced
fractions are accepted, but uniqueness is checked after exact reduction, so
`"1/2"` and `"2/4"` cannot both occur. Zero is forbidden: adding zero to a
sextuple would make every new product-plus-one equal 1 without answering the
research question.

Resource limits are checked before expensive arithmetic: each raw string has at
most 1,235 characters, each raw numerator and denominator has at most 2,048 bits
(before fraction reduction), and the CLI reads at most 32,768 bytes. These are
submission limits, not bounds on all possible mathematical solutions.

Run the data-only verifier from this directory:

```bash
python verify.py submission.json
```

Omit the path or use `-` to read JSON from stdin. Submitted text is never
evaluated, executed, or imported. For each pair the checker reduces `ai*aj + 1`
as an exact `Fraction`, then checks whether both numerator and denominator are
integer squares using `isqrt`.

Output reports `schema_valid`, `success`, `pairs_satisfied`, `total_pairs`,
`status`, and `reason`. Exit 0 means success; exit 1 means valid seven-entry
schema with at least one nonsquare pair; exit 2 means invalid input. Pair counts
are diagnostics: **20/21 is failure, not 95% of a discovery**. There is no
combined score, partial scientific success, or discovery label.

`examples/sextuple.json` is a sourced positive six-entry control. It satisfies
all 15 pairs, but cannot pass the seven-entry CLI. The Python function
`verify(data, expected_count=...)` permits smaller counts solely to verify known
controls; the CLI always requires seven.

[Epoch's background](https://epoch.ai/frontiermath/open-problems/diophantine-septuple)
uses positive rationals, while its actual prompt allows distinct nonzero
rationals. This package explicitly adopts the positive variant. The existence
of a seven-entry example is unknown in the checked sources; no seven-entry
witness is supplied. A model or bounded search failing to find one cannot prove
impossibility. See `references.md` for provenance and checked controls.
