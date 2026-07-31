# MatrixMultiplicationRank — known-best scalar-multiplication counts

| size (m×n×p) | naive | best known | source | date |
|---|---|---|---|---|
| 2×2×2 | 8 | 7 | Strassen | 1969 |
| 3×3×3 | 27 | 23 | Laderman | 1976 |
| 4×4×4 | 64 | 49 (real) / 48 (ℂ) | Strassen²; AlphaEvolve | 1969 / 2025 |

`sota_ref` in the evaluator uses the real-coefficient bests as the score=1.0 anchor
(2×2=7, 3×3=23, 4×4=48 — AlphaEvolve 2025, over ℂ). Recursive Strassen (49) scores 0.9375 on 4×4; beating 48 scores >1.0.
Update this table and `verification/evaluator.py:SIZES` if a better count is verified.
