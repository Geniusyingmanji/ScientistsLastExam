# Sources and exact controls

Sources checked on 2026-09-06:

- [Andrej Dujella, *Diophantine m-tuples — Introduction*](https://web.math.pmf.unizg.hr/~duje/intro.html)
  explicitly gives Gibbs's positive sextuple
  `{11/192,35/192,155/27,512/27,1235/48,180873/16}`, used verbatim in
  `examples/sextuple.json`. The same page gives Fermat's `{1,3,8,120}` control.
- [Dujella, *Rational Diophantine m-tuples*, Section 5.2](https://web.math.pmf.unizg.hr/~duje/ratio.html)
  discusses known sextuples, unknown septuple existence, and the positive
  “almost septuple” used as a negative control below.
- [Epoch AI, *A Rational Diophantine Septuple*](https://epoch.ai/frontiermath/open-problems/diophantine-septuple)
  motivates exact verification and explicitly warns that the object may not
  exist. Its background definition requires positivity; its submitted prompt
  requires only nonzero rationals. Our positivity constraint is deliberate.

The classic sextuple passes all 15 exact pair checks. An independent SymPy
`Rational` / symbolic `sqrt` check reports rational roots for all 15 pairs;
in lexicographic pair order they are
`193/192,83/72,13/9,151/96,815/32,103/72,19/9,229/96,1453/32,283/27,439/36,1019/4,199/9,463,8629/16`.
Squaring these roots reconstructs each product-plus-one exactly. SymPy is used
only for independent development verification, not by the shipped checker.
Fermat's quadruple passes
all 6 off-diagonal checks, with square roots `2,3,11,5,19,31` in pair order.

The seven positive values
`243/560,1147/5040,1100/63,7820/567,95/112,38269/6480,196/45`
from Dujella's Section 5.2 satisfy 20 of 21 pairs. The verifier must still return
`success: false`, `status: not_found`, and CLI exit 1. This existing near-example
shows why the pair fraction is not a measure of progress toward a discovery.

The source status is not a proof of nonexistence. No successful septuple test,
current record score, empirical model difficulty, or continuous scientific
score is claimed. The integer-bit and document-size limits constrain the local
verifier, so rejection at a resource limit is also not mathematical refutation.
