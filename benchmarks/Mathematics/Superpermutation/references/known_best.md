# Superpermutation — shortest known lengths

| n | naive n·n! | shortest known | lower bound | source |
|---|---|---|---|---|
| 7 | 35280 | 5906 (2019) | 5884 | Egan–Houston, 27 Feb 2019; lower bound n!+(n−1)!+(n−2)!+n−3 (anonymous 4chan 2011 / Houston–Pantone–Vatter 2018) |
| 8 | 322560 | 46205 (2018) | 46085 | Greg Egan, Oct 2018, Williams construction n!+(n-1)!+(n-2)!+(n-3)!+n-3; recorded in OEIS A180632 (corrected by Max Alekseyev, Jan 2019). Lower bound n!+(n-1)!+(n-2)!+n-3 = 46085. Gap 120. An earlier draft of this table carried a value one below this, attributed to the Hunter-Raudvere lower-bound artifact; that repository proves 46103 <= S(8) and does not construct any n=8 string, and no source records the smaller value. |

A string shorter than the listed record scores above 1.0. Update this table and
`verification/evaluator.py:SIZES` if a shorter verified superpermutation is published.

Sources:

- https://www.gregegan.net/SCIENCE/Superpermutations/Superpermutations.html
- https://github.com/urdvr/superpermutations-hunter
- arxiv:1408.5108 (Houston, n=6; the conjecture-breaking paper)
- doi:10.1080/00029890.2021.1835384
- https://oeis.org/A180632
