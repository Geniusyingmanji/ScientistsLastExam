# CapSetFrontier — known-best cap sizes in open dimensions

Dimensions 4–6 are proven maxima and live in `Mathematics/CapSet`. This task is n=7,8,9.

| dim n | baseline {0,1}^n = 2^n | best known | status | source |
|---|---|---|---|---|
| 7 | 128 | 236 | best known, unproven | Calderbank–Fishburn, doi:10.1007/BF01388452 |
| 8 | 256 | 512 | FunSearch 2023 | Romera-Paredes et al., Nature 2023, doi:10.1038/s41586-023-06924-6 |
| 9 | 512 | 1082 | best known, unproven | FunSearch companion PDF, Figure C.5, doi:10.1038/s41586-023-06924-6 |

A cap larger than the listed size scores above 1.0. Update this table and
`verification/evaluator.py:SIZES` if a larger verified cap is found.

Sources:

- doi:10.1038/s41586-023-06924-6
- doi:10.1007/BF01388452
- doi:10.4007/annals.2017.185.1.8
