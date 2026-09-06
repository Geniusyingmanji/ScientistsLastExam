# ShannonCapacityCertificate — certify the interval, do not quote it

## Scientific setting

Shannon asked in 1956 for the zero-error capacity of a noisy channel: the rate at which you can
transmit with *no* errors, ever, not merely with vanishing probability. For a channel whose
confusability graph is the five-cycle he could not answer it. Lovász answered it in 1979 by
inventing `theta`, a semidefinite quantity that is multiplicative under the strong product and
therefore bounds the capacity from above; for `C_5` it is tight.

For every odd cycle from the seven onwards it is not tight, or at least nobody knows that it is,
and the capacity is unknown. What is known is an interval, and the interval is still moving. For
`C_7` the lower end went `3.2271` (2002) → `3.2578` (2018) → `3.2580` and then `3.2588` in July
2026, three times in one month; the upper end has been `theta(C_7) = 3.31767` since 1979 and no
one has ever proved *any* better upper bound for any odd cycle beyond the fifth.

Every one of those lower-end improvements is an explicit finite object: an independent set in a
strong product power, which is a zero-error code. Every one of them was found by computer search
over an algebraic family, not by local search from nothing.

## What is scored

Not a capacity. **A certified interval.**

For each cycle in the suite you submit two objects.

**Below.** One or more zero-error codes: a set `S` of `k`-tuples over `Z_n`, no two of which are
adjacent in `C_n^{box k}` — that is, no two of which agree-or-differ-by-one in *every* coordinate.
Such a set proves

```
Theta(C_n)  >=  |S| ** (1/k)
```

The oracle checks it as a membership test, not a search: for each codeword, none of the `3^k - 1`
shifts by `{0, +1, -1}` may also be a codeword. Nothing about how you found `S` matters. You may
submit several codes at several powers; the best certified bound is the one that counts. The power
is capped per instance so that verification and the candidate sandbox both stay bounded.

**Above.** A rational matrix. For any symmetric real `A` with `A[i][i] = 1` and `A[i][j] = 1` at
every *non-adjacent* pair, `lambda_max(A) >= theta(C_n) >= Theta(C_n)`; free entries sit exactly on
the edges. A rational `A` together with a rational `b` proves `Theta(C_n) <= b` as soon as
`b*I - A` is positive definite, which the oracle decides by exact rational elimination with no
tolerance. Entries are integers or `[numerator, denominator]` pairs; **a float is rejected, not
rounded**, because a numerical eigenvalue is not a proof.

Your score is how far the width `b - |S|**(1/k)` moves from the free interval toward the published
one.

## Why this is not a solver call

**Local search stops early and stops in the same place.** From a random start, the standard
plateau walk on `C_7^{box 5}` reaches 337 of the 367 codewords that are known to exist there, and
every restart reaches 337 again. Composing the best small-power codes gives 330. The linear codes
over `GF(7)` give 343, and they are maximal — no vertex can be added and no swap improves them.
None of those beat the free bound. What moves the number is a different construction entirely.

**The upper side is exact or it is nothing.** The optimal `A` for an odd cycle is irrational.
Rounding it to rationals and keeping `b*I - A` positive definite, without giving back more in `b`
than the rounding saves, is the whole difficulty — the same difficulty as in the sum-of-squares
tasks in this benchmark, in its smallest possible setting.

**The scale is uncapped.** The published target is a witness worth exactly 1, not a ceiling. A
score above 1 means a code larger than anything published at a power this task allows, which for
`C_7` at power 5 would be the first improvement since 2018.

## Instances

| instance | cycle | power cap | free bound (score 0) | published target (score 1) | `theta` |
|---|---:|---:|---:|---:|---:|
| `C7` | 7 | 5 | 3.2237098 | 3.258805369885 | 3.317667207394 |
| `C13` | 13 | 4 | 6.2449980 | 6.302455083464 | 6.404168562937 |
| `C19` | 19 | 3 | 9.2195445 | 9.357192705918 | 9.434771374446 |
| `C23` | 23 | 3 | 11.2249722 | 11.328224257774 | 11.446193611907 |

The free bound is not a citation. It is an explicit set shipped in `references/free_sets.json`,
which the oracle's own independence test accepts: 108 codewords at power 4 for `C7`, and the
classical two-coordinate sets `floor(n(n-1)/4)` for the others, squared into power 4 where the cap
allows. Matching it scores exactly zero. The published target is the best lower bound on the
capacity as of 2026-09-06, quoted verbatim from arXiv:2607.29681, and is worth exactly 1 — none of
the four was reached in the literature at a power this task allows.

`C7` is the rung that guarantees a competent submission has somewhere to stand: it is the cycle
everyone has worked on, and the largest published set at power 5 has stood since 2018. `C19` and
`C23` are the other end — their targets come from constructions at power 6 and beyond, and the
classical two-coordinate value is a much stronger floor there than it is for `C7`.

## Scoring

Per instance, linear in the width of the interval you certify, and uncapped above:

```
width  = your_upper_bound - your_best_lower_bound
score  = (theta - free_bound - width) / (theta - free_bound - (theta - target))
```

which is 0 when you certify exactly the free interval, 1 when you certify the published one, and
more than 1 beyond it. The combined score is the mean over the four instances. An instance whose
certificates do not verify scores 0 for that instance and never raises out of the oracle.

Because no upper bound better than `theta` is known for any odd cycle beyond the fifth, the top of
the interval is the same for you as for the literature, and the score is driven by the bottom. The
upper certificate is still load-bearing: a sloppy `b` widens your interval and costs you score, and
an invalid one scores the instance zero.
