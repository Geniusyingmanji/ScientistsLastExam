# ShannonCapacityCertificate — what is known, and what this package reaches

## The literature

`Theta(C_n)` is unknown for every odd `n >= 7`. What exists is an interval whose top has not moved
since 1979 and whose bottom moved three times in July 2026.

| instance | free bound (score 0) | best published (score 1) | `theta` (top of the interval) |
|---|---|---|---|
| `C7`, power <= 5 | 3.2237098 | 3.258805369885 | 3.317667207394 |
| `C13`, power <= 4 | 6.2449980 | 6.302455083464 | 6.404168562937 |
| `C19`, power <= 3 | 9.2195445 | 9.357192705918 | 9.434771374446 |
| `C23`, power <= 3 | 11.2249722 | 11.328224257774 | 11.446193611907 |

The four published lower bounds are quoted verbatim from the abstract of Buys, Polak and Zuiddam,
*Lean-verified lower bounds for the Shannon capacity of odd cycles*, arXiv:2607.29681 (31 July
2026). `theta` is Lovász's closed form for the odd cycle. **No upper bound better than `theta` is
known for any odd cycle beyond `C5`**, which is why the top of the certified interval is the same
for a submission as for the literature, and why this task scores the bottom.

None of the four targets was reached at a power this task allows: the constructions behind them run
to power 6 and beyond, and for `C7` to power 200 by recursion. The scale is uncapped above.

## The seven-cycle, as a shape of the problem

| year | bound | how |
|---|---|---|
| 1971 | 3.2075 (`33^(1/3)`) | independent set in the third strong power |
| 2002 | 3.2271 (`350^(1/5)`) | Vesel and Žerovnik, genetic search in the fifth power |
| 2019 | 3.2578 (`367^(1/5)`) | Polak and Schrijver, circular graph `C_{108,382}` and the cyclic code `{t·(1,7,49,343,2401)}` |
| 2026 | 3.258020 (`134753^(1/10)`) | Itty, Rosin, Carstensen, Reichman |
| 2026 | 3.2587891539 | recursion from the 367-codeword set out to power 200 |
| 2026 | 3.258805369885 | Buys, Polak and Zuiddam |

Every step is an explicit finite object found by search over an algebraic family. None came from
local search on the strong power. That is the whole content of the task.

## The free bound is a witness, not a citation

`references/free_sets.json` holds the four zero-of-the-scale sets, and each one passes the oracle's
own independence test:

| instance | witness | size | bound |
|---|---|---|---|
| `C7` | power 4 | 108 | 3.2237098 |
| `C13` | power 2, squared to power 4 | 39 → 1521 | 6.2449980 |
| `C19` | power 2 | 85 | 9.2195445 |
| `C23` | power 2 | 126 | 11.2249722 |

The three two-coordinate values are `floor(n(n-1)/4)`, the classical value for the strong product of
two cycles, and three restarts of a two-million-draw plateau walk re-find all three in about five
seconds. The `C7` witness of 108 at power 4 matches the published power-4 value (Vesel and Žerovnik
2002) and was found here independently: of six iterated-local-search seeds, three reached 108 and
three stalled at 106.

## What this package measures

Measured on this package, not quoted:

| construction | `C7` at power 5 | as a capacity bound |
|---|---|---|
| best of ten random greedy | 246 | 2.9932 |
| plateau walk from random starts, five restarts of two minutes | 337 | 3.1975 |
| composition of the best power-2 and power-3 codes | 330 | 3.1841 |
| linear codes over `GF(7)`, dimension 3 | 343 | 3.2088 |
| quotient by a cyclic code, plateau on the 2401-coset graph | 343 | 3.2088 |
| **circular code, pruned** | **355** | **3.2363** |
| **circular code, pruned, extended, plateau** | **366** | **3.2561** |

The first five all score **exactly zero**: every one of them lands below the free bound of
3.2237098, which the power-4 set already proves. The linear `GF(7)` codes are the sharpest illusion
in the list — they are maximal, no vertex can be added and no `(1,1)` swap improves them, and they
are still worth nothing.

The circular-code sweep is what moves the number. It is not told where to look: it enumerates
`(modulus, multiplier)` over a window and rediscovers Polak and Schrijver's `(382, 7)` in about
fifteen seconds.

## The upper certificate

`theta` is not read from a table. For the odd cycle the Lovász matrix can be taken circulant, which
collapses the semidefinite program to one free variable: the eigenvalues are `n - 2 + 2x` and
`2(x-1)cos(2*pi*k/n)`, and the best `x` is where the largest of them cross. The reference bisects
that crossing on rationals with a capped denominator and then bisects `b` upward until `b*I - A`
passes the exact positive-definiteness test. It lands about `1.5e-6` above the closed form on all
four cycles — which is, incidentally, the check that the closed form is right.

## Reference

| instance | codewords | power | lower | upper | score | build |
|---|---:|---:|---:|---:|---:|---:|
| `C7` | 366 | 5 | 3.2560886 | 3.3176690 | 0.922539 | 228 s |
| `C13` | 245 | 3 | 6.2573247 | 6.4041700 | 0.214513 | 6 s |
| `C19` | 807 | 3 | 9.3101750 | 9.4347730 | 0.658410 | 17 s |
| `C23` | 1433 | 3 | 11.2741047 | 11.4461950 | 0.475837 | 39 s |

**Combined 0.567825**, valid on all four, 290 s end to end against a 720 s evaluation timeout. The
reference also submits the free set on every instance, so a bad sweep can only fail to improve on
the zero of the scale, never fall below it - visible above as the two codes per instance in the
build log, `(4, 100)` and `(5, 366)` for `C7`.

`C7` is the instance a recalled parameter carries: 0.92 of it. `C13` is the other end - the sweep
beats the squared two-coordinate set by twelve thousandths of a capacity unit and no more. That
spread across four cycles is the point of the suite.

The reference is deterministic: fixed sweep windows, a fixed iteration count for every local
search, a fixed seed, and no step reads the clock.
