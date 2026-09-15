# LyapunovDecayCertificate — scientific admission hold

## Reference

`verification/reference_lyapunov.py` uses only public modes. It searches a finite
catalog of 3-by-3 rational Gram matrices (identity, diagonals, pairwise shears,
two-off-diagonal shears, cyclic-symmetric Grams, and a handful of full 5-DOF
shears) and, for each Gram that is a common Lyapunov function at rate 0,
maximizes alpha by exact rational bisection to the public numerator/denominator
cap. The trace of each Hurwitz mode is a public upper bound. The returned rate
cannot be increased by 1e-4 while keeping the same Gram feasible.

Current in-process reference score: **0.437715**, all four instances valid.
Proven rates: plant 56471/111111; cascade 32237/111111; mixed 74541/250000;
sparse 13563/62500. Wall time 1.03 s. Catalog size 119, of which 7 are cyclic
(`p11=p22=p33` and `p12=p13=p23≠0`).

The catalog is a competent Boyd-style witness and is deliberately not a 5-DOF
exhaustive search. Adding the cyclic line does not close that leftover: those
seven Grams do not raise the shipped score on this family.

## Baseline

The identity Gram at alpha=1/10000 is legal on every instance and scores exactly zero.

## Ablation ladder

In-process substitutions of the reference catalog / rate search, same evaluator:

| witness | combined |
|---|---|
| identity Gram, exact bisection of alpha | 0.265909 |
| diagonal Grams only, exact bisection | 0.337760 |
| full catalog including cyclic Grams, exact bisection (shipped reference) | **0.437715** |
| same certificates dumped as floats | 0.000000 |

Exact arithmetic is not cosmetic: the float dump of a valid witness scores zero.
Diagonals are worth 0.072 over identity bisection; the remaining catalog terms
(pairwise and two-plane shears) are worth another 0.100. The cyclic-symmetric
subset does not move the shipped score.

## Shortcut probes

These are maintainer measurements on the real scoring path (in-process
`evaluate`, same oracle as `python -m sle eval`). The 2-parameter family is
`P = [[1, b, 0], [b, d, 0], [0, 0, 1]]`. The cyclic probe first C3-averages a
Gram to `aI + b(J−I)` and then searches the remaining scalar on the 14-point
line `P = I + c(J−I)`, `c = k/10` for `k = -4,…,9`.

| probe | scale / wall | combined | vs reference |
|---|---|---|---|
| baseline `solution.py` | — | **0.000000** | 0.00× |
| padded September 9 constant `p11=1, p12=-3/5, p22=1, p13=p23=0, p33=1, alpha=59/100` | 0 search | **0.000000** (infeasible on every instance) | 0.00× |
| identity Gram, exact bisection of alpha | 4 bisections | 0.265909 | 0.61× |
| **group-average then 1-D cyclic line, 14 Grams** | **14×4, 0.07 s** | **0.265200** | **0.61×** |
| **2-param grid `b,d` step 1/10, 725 Grams, rational bisection** | **725×4, 1.5 s** | **0.299867** | **0.69×** |
| **reference** (119 Grams including 7 cyclic, public-cap bisection) | **1.03 s** | **0.437715** | 1.00× |

Checkpoint 12 is a pass on this family: the cheap group-average / cyclic line
scores 0.61× the reference, below 0.8×, and does not beat identity bisection.
Beating the old 2-parameter block-diagonal probe is not the bar; the cyclic
line is the probe that used to score 1.34× on the permutation-orbit family.

`references/constant_probe.py`, `references/grid_probe.py` and
`references/cyclic_probe.py` reproduce the constant, 2-param and cyclic rows.
`tests/test_lyapunov_decay_certificate.py` pins that all three stay below the
reference and that the cyclic line is below 0.8× reference.

## Frontier draw

None. `calibration_runs` is empty and `long_horizon.status` is `not_tested`.
This is a candidate, not a certified exam item.

## Construction errors

The previous 2-by-2 family had only two free Gram parameters after homogeneity.
A 0.1-second (b, d) grid scored 0.799867 against a coarse-rate reference of
0.749867, and an instance-blind constant scored 0.786533. Enlarging to 3-by-3
permutation-switched plants (braid, cycle, twist, cross) killed that 2-parameter
grid (0.206533 = 0.56×) but left a 1-parameter cyclic line: every mode set was
a permutation-conjugate orbit of one Hurwitz matrix, C3 averaging reduced `P`
to `aI + b(J−I)`, and a 14-point scan scored 0.491533 = 1.34× the catalog,
which had structurally excluded that line (0 of 112 Grams cyclic).

The instances are now four switched plants (plant, cascade, mixed, sparse)
whose modes are independent rational Hurwitz matrices with pairwise distinct
characteristic polynomials, hence not permutation-conjugate. No shared
warehouse matrix is the whole family. The cyclic line now scores 0.61×; the
catalog includes the cyclic-symmetric Grams and still sits above them.

## Robustness and limits

Floats and malformed certificates fail closed. A 2-by-2 key set without
`p13`/`p23`/`p33` scores zero. Numerically found 3-by-3 matrices converted to
exact rational witnesses are not inherently forbidden; that is the intended
scientific work. A larger rational catalog or an SDP-plus-reconstruction can
still beat the shipped 119-Gram witness; that leftover is catalog headroom,
not a cyclic-line exploit. The PR remains Draft; no model calibration or
long-horizon evidence was created.

## September 12 sandbox replay

The cyclic and block-grid candidates are now self-contained. Their exact-arithmetic
helpers are embedded from the public-input reference; sibling `verification/` files are
not mounted into a candidate sandbox. The old cyclic import failed in the sandbox,
so the old in-process table alone did not establish replayability.

Current Linux sandbox: complete reference **0.437715**, 14-point cyclic line
**0.26519975**, block-diagonal grid **0.2998665**; all four instances are valid for each.
An isolated-file regression verifies both probes without sibling files. The exact search
algorithms and mode family were not changed by this repair. This establishes separation
for these declared controls on this head, not external/model or long-horizon qualification.
Historical 0.491533 belongs to a different head and is not a current measurement.
