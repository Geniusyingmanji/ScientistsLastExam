# CapSet — known-best cap sizes

| dim n | baseline {0,1}^n = 2^n | best known max | status |
|---|---|---|---|
| 4 | 16 | 20 | proven max |
| 5 | 32 | 45 | proven max |
| 6 | 64 | 112 | proven max |
| 7 | 128 | 236 | best known |
| 8 | 256 | 512 | FunSearch 2023 |

`sota_ref` in the evaluator uses these as the score=1.0 anchor. Exceeding a best-known size
(only open for n>=7) scores >1.0. Update this table and `verification/evaluator.py:SIZES`
if a larger verified cap is found, and consider adding n>=7 to push the open frontier.

## Sources

The three anchors the evaluator scores against (n = 4, 5, 6) are proven optimal, not merely best
known, so a score above 1.0 there would refute a proof and should be treated as a bug until shown
otherwise. The n = 7 and n = 8 rows are context only and are not scored by this task.

- OEIS A090245, maximal size of a cap in AG(n, 3): https://oeis.org/A090245 (the sequence
  1, 2, 4, 9, 20, 45, 112 for n = 0..6, each proven).
- n = 4, 20: G. Pellegrino, *Sul massimo ordine delle calotte in S_{4,3}*, Matematiche 25 (1971).
- n = 5, 45: Y. Edel, S. Ferret, I. Landjev, L. Storme, *The classification of the largest caps
  in AG(5,3)*, J. Combin. Theory Ser. A 99 (2002), doi:10.1006/jcta.2002.3261.
- n = 6, 112: A. Potechin, *Maximal caps in AG(6,3)*, Des. Codes Cryptogr. 46 (2008),
  doi:10.1007/s10623-007-9132-z.
- n = 8, 512: B. Romera-Paredes et al., *Mathematical discoveries from program search with large
  language models*, Nature 625 (2023), doi:10.1038/s41586-023-06924-6 (FunSearch).
