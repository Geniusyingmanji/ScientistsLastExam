# RamseyLowerBound — known-best construction orders

A 2-coloring of `K_n` with no red `K_s` and no blue `K_t` proves `R(s, t) ≥ n + 1`.
`sota_ref` is that `n`, not the Ramsey number itself.

| pair (s, t) | baseline n = 2(t−1) | published n | implies | source |
|---|---|---|---|---|
| (5, 5) | 8 | 42 | R(5,5) ≥ 43 | Exoo, J. Graph Theory 13 (1989) 97–98. DOI 10.1002/jgt.3190130114 |
| (4, 6) | 10 | 35 | R(4,6) ≥ 36 | Exoo; see Radziszowski Dynamic Survey DS1 |

Upper bound (not a scoring anchor): `R(5, 5) ≤ 46` (Angeltveit–McKay 2024); `R(4, 6) ≤ 41`.
A coloring with n > 42 on (5, 5) or n > 35 on (4, 6) scores above 1.0. The checker caps
n at 50 and 42 respectively so a K_6 scan cannot explode. Update this table and
`verification/evaluator.py:INSTANCES` if a larger verified coloring is published.

Sources:

- https://www.combinatorics.org/ojs/index.php/eljc/article/view/DS1
- doi:10.1002/jgt.3190130114
