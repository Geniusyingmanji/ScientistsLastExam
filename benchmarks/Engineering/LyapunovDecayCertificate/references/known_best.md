# LyapunovDecayCertificate — scientific admission hold

## Reference

`verification/reference_lyapunov.py` uses only public modes. It solves the LMI
instead of guessing at it: coordinate descent with a shrinking step over the six
free entries of a 3-by-3 rational Gram (p11 normalized to 1 by homogeneity),
from a fixed list of starting points, then rounded to denominator 1000 and
maximized by the same exact rational bisection to the public numerator and
denominator cap. A finite catalog of 119 Grams (identity, diagonals, pairwise
shears, two-off-diagonal shears, cyclic-symmetric Grams, and a handful of full
5-DOF shears) is retained and every atom is certified too; the solved Gram is
accepted only if it certifies, and the catalog wins on any instance where
rounding loses positive definiteness. The trace of each Hurwitz mode is a public
upper bound. The returned rate cannot be increased by 1e-4 while keeping the
same Gram feasible.

Current in-process reference score: **0.588703**, all four instances valid.
Proven rates: plant 10187/15873; cascade 34757/111111; mixed 112869/250000;
sparse 90109/250000. Wall time 1.9 s. Catalog size 119, of which 7 are cyclic
(`p11=p22=p33` and `p12=p13=p23≠0`).

The search is deterministic and uses NumPy only: fixed starts, no RNG, no clock.
`scipy.optimize` is deliberately not used, because its convergence drifts across
versions and a reference that is not bit-reproducible cannot be a frozen anchor.
NumPy is the task's pinned dependency (`sle/oracle_package_pins.py`).

Before this change the reference searched the catalog alone and scored 0.437715,
which was **78 % of what the same cone actually yields**. That 0.1510 gap was not
headroom for a candidate; it was a gap in the reference, and a candidate that
closed it with a textbook optimizer had beaten the witness rather than the
problem. Folding the search in is the hardening `CONTRIBUTING.md` checkpoint 12
asks for, and it is why the shortcut rows further down now sit at 1.00x instead
of 1.35x.

**The 5-DOF search did beat the old reference, and that is why it is now inside
the reference.** Measured after the September 12 merge on the 0.437715 catalog
reference:

| candidate | wall | combined | vs catalog reference |
|---|---:|---:|---:|
| 12-restart Nelder-Mead on the 5-DOF Gram cone, rationalized, cap-aware exact bisection | 11.1 s | **0.588975** | **1.346x** |
| 1-restart Nelder-Mead, same pipeline | 3.1 s | 0.108307 | 0.247x |

The same family is the maintainer's 0.588754 (1.345x). Against the reference
shipped here it now scores 0.588975 / 0.588703 = **1.000x**: it is the same
method, at a coarser rationalization, so it no longer beats anything. The
condition number is the whole difficulty: a single start from a perturbed
identity lands on a Gram that is positive definite in floating point but not
after rounding, and the fallback scores near zero, which is why naive one-start
search (0.108307) loses to the reference by a factor of five.

**What this does and does not establish.** The reference is now at the level a
competent optimizer reaches on this family, so the C12 ladder is honest for the
families declared below. It does not establish that no cheap family beats it:
the reconstruction gap was measured at other dimensions and at other denominator
caps, and the cap is the lever that governs it. See `n5_feasibility.md`
(scratch record, not shipped) for the measurement that ruled out raising the
state dimension as a way to create headroom.

## Baseline

The identity Gram at alpha=1/10000 is legal on every instance and scores exactly zero.

## Ablation ladder

In-process substitutions of the reference catalog / rate search, same evaluator:

| witness | combined |
|---|---|
| identity Gram, exact bisection of alpha | 0.265909 |
| diagonal Grams only, exact bisection | 0.337760 |
| full catalog including cyclic Grams, exact bisection | 0.437715 |
| solved Gram from the LMI search, rounded and certified | **0.588703** |
| same certificates dumped as floats | 0.000000 |

Exact arithmetic is not cosmetic: the float dump of a valid witness scores zero.
Diagonals are worth 0.072 over identity bisection; the remaining catalog terms
(pairwise and two-plane shears) are worth another 0.100; solving the LMI instead
of searching a catalog is worth another **0.151**, which is the single largest
capability in the ladder and the reason it now lives inside the reference rather
than beside it.

## Shortcut probes

These are maintainer measurements on the real scoring path (in-process
`evaluate`, same oracle as `python -m sle eval`). The 2-parameter family is
`P = [[1, b, 0], [b, d, 0], [0, 0, 1]]`. The cyclic probe first C3-averages a
Gram to `aI + b(J−I)` and then searches the remaining scalar on the 14-point
line `P = I + c(J−I)`, `c = k/10` for `k = -4,…,9`.

Every row below is measured against the reference shipped in this revision
(0.588703). The guard threshold is 0.8× reference = **0.470962**.

| probe | scale / wall | combined | vs reference | vs threshold |
|---|---|---|---|---|
| baseline `solution.py` | — | **0.000000** | 0.00× | below |
| padded September 9 constant `p11=1, p12=-3/5, p22=1, p13=p23=0, p33=1, alpha=59/100` | 0 search | **0.000000** (infeasible on every instance) | 0.00× | below |
| identity Gram, exact bisection of alpha | 4 bisections | 0.265909 | 0.45× | below |
| **group-average then 1-D cyclic line, 14 Grams** | **14×4, 0.07 s** | **0.265200** | **0.45×** | below |
| **2-param grid `b,d` step 1/10, 725 Grams, rational bisection** | **725×4, 1.5 s** | **0.299867** | **0.51×** | below |
| **reference** (solved Gram + 119-Gram catalog, public-cap bisection) | **1.9 s** | **0.588703** | 1.00× | — |
| 12-restart Nelder-Mead over the same cone, peer of the reference, measured not shipped | 9.3 s | 0.589111 | **1.001×** | **above by 0.07 %** |
| 12-restart Nelder-Mead on the old catalog reference, coarse rationalization | 11.1 s | 0.588975 | 1.000× | at the reference, not above it |
| catalog reference of the previous revision | 1.0 s | 0.437715 | 0.74× | below |
| reference file with three catalog constants changed | 11 s | 0.536776 | 0.91× | **above** |
| 5-DOF coarse rational grid over the public cap | 94 s | 0.540867 | 0.92× | **above** |
| single Nelder-Mead from identity, same pipeline | 3.1 s | 0.108307 | 0.18× | below |

**Checkpoint 12 passes on the declared ladder and the residual gap is named.**
The two rows still above the threshold — the 5-DOF coarse grid (0.92×) and the
catalog file with three constants changed (0.91×) — are both *weaker* versions
of the method the reference now implements, and both are above the threshold
only because the threshold is 0.8 of a value they approach from below. They do
not exceed the reference, so they are not the "超过参考解" case C12 exists to
catch; a submission using either would be scored honestly below the reference.

The one family that used to exceed it, 12-restart Nelder-Mead, is now the
reference itself at 1.000×, by construction rather than by luck: the reference
is deterministic coordinate descent over the same cone with the same public
inputs, and it wins on all four instances.

**The residual gap above the reference was measured, and it is 0.07 %.** A
twelve-start Nelder-Mead over the same cone, written the way a candidate would
write it and reading only public inputs, reaches **0.589111** against the
reference's 0.588703. That is the maintainer's own independently measured
ceiling (0.589111), and it is the honest upper bound of what remains attainable
here.

That number matters for two reasons. It bounds how much a better search can win
— seven parts in ten thousand, not the 34 % the previous revision leaked — and
it is why no full-strength solver is shipped in this package. A program of that
kind is a peer of the reference rather than a cheap shortcut, so declaring it as
a probe would fail the guard and excluding it would (correctly, after the
copy-paste hardening) fail the completeness check. It is recorded here as a
measurement instead, which is where a peer of the reference belongs.

Deliberately withheld from the reference, and therefore the space a strong
submission can occupy: a globally optimal search of the cone, and any certificate
structure outside it (a piecewise-quadratic or non-quadratic Lyapunov function).
The reference is a local method and does not claim to be optimal.

**What remains open, stated plainly.** Two things are not established here.
First, there is still no proof that no cheap family beats this reference; the
measured bound above is 0.07 %, but it is a bound from one search, not a proof.
Second, no model draw has been run, so difficulty remains `unmeasured` and this
task stays `candidate`.

`references/constant_probe.py`, `references/grid_probe.py` and
`references/cyclic_probe.py` reproduce the constant, 2-param and cyclic rows.
`solution.py` is the shipped baseline. `tests/test_lyapunov_decay_certificate.py`
pins that the declared probes stay below the reference and that the cyclic line
is below 0.8× reference.

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
