# TensorRank555 — exact records used as numerical score anchors

New sizes only. `<2,2,2>`, `<3,3,3>` and `<4,4,4>` live in `Algorithm/MatrixMultiplicationRank`.

| size (m×n×p) | naive | published exact R | field | source |
|---|---|---|---|---|
| 5×5×5 | 125 | 93 | arbitrary / ℤ | Moosbauer–Poole, ISSAC 2025, arXiv:2502.04514 |
| 6×6×6 | 216 | 153 | arbitrary / ℤ | Moosbauer–Poole, ISSAC 2025, arXiv:2502.04514 |

The evaluator uses these counts only to normalize a fixed-tolerance numerical score. A
numerically accepted decomposition with `R` below a listed count scores above 1.0, but that
does not establish a smaller exact tensor rank over the listed field. Any record claim needs
an exact rational, integer, or independently checkable symbolic certificate before this table
or `verification/evaluator.py:SIZES` is updated.

Source: https://arxiv.org/abs/2502.04514
