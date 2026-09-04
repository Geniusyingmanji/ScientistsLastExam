# NonlinearCodeRecords — reference results

Every number here is produced by running code in this directory, except the published records,
which are read from Brouwer's table and recorded in `references/anchors.json` with their source.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_parity_check_linear.py \
    --metrics-out /tmp/metrics.json
```

## The instances

| instance | trivial | largest linear | published lower | published upper | source |
|---|---|---|---|---|---|
| A(23, 10) | 4 | 64 | 80 | 150 | Brouwer's table, retrieved 2026-09-04 |
| A(24, 10) | 4 | 64 | 136 | 268 | same |
| A(25, 10) | 4 | 128 | 192 | 466 | same |
| A(26, 10) | 4 | 256 | 384 | 836 | same |

All four are open: the lower and upper entries disagree. The lower entries are held by nonlinear
codes.

## Reference — `verification/reference_parity_check_linear.py`

Truth-blind: it reads only `n` and `d`.

| metric | value |
|---|---|
| combined score | **0.642** |
| A(23,10) | 64 of 80 → 0.789 |
| A(24,10) | 64 of 136 → 0.455 |
| A(25,10) | 128 of 192 → 0.660 |
| A(26,10) | 256 of 384 → 0.663 |
| wall time | 2.4 s |

A code has minimum distance at least `d` exactly when every `d-1` columns of its parity check are
independent, so the construction grows a column set over `F_2^r` in which no column is a sum of at
most `d-2` of the others, taking the smallest `r` that admits `n` columns.

**The reference is deliberately not at the ceiling, and the gap is structural rather than a matter
of effort.** Every published record here is held by a nonlinear code. The obvious way to leave
linearity — keep the linear code `C` and add cosets `x + C` — was implemented and measured, and it
finds **zero** admissible cosets at all four instances: a coset representative must sit at distance
at least `d` from all of `C`, and the covering radius of these codes is below `d`, so no such point
exists. That negative result is why the reference is the linear code and not something cleverer.

## Baseline — `solution.py`

Block repetition: split the coordinates into blocks of `d`, repeat one bit across each. Distance
`d` by construction, `2^(n//d)` words, which is four at every instance here.

| metric | value |
|---|---|
| combined score | **0.0000** |
| code size | 4 at every instance |

## Shortcut probe

39 low-dimensional strategies: random greedy accretion at six seeds and two effort levels (300 and
3000 candidate words), and constant-weight codes at every weight from 0 to 26.

| family | strategies | best score |
|---|---|---|
| random greedy accretion | 12 | 0.000 |
| constant-weight | 27 | 0.000 |
| reference | — | 0.642 |
| published records | — | 1.000 |

At distance 10 a random word is almost never far enough from the words already chosen, and no
single weight class in `F_2^24` is large enough to matter. Nothing here is reachable by turning a
knob.

## Why there is no certificate half

This task was first built as a two-sided sandwich: submit a code for the lower bound *and* a
Delsarte linear-programming certificate for the upper bound, on the theory that a construction plus
a proof of near-optimality is the shape of a real result — the shape the 2026 zeta-zero result had.
Measuring it killed the idea at these parameters. A fifty-line linear program produces:

| instance | Delsarte LP | published upper bound |
|---|---|---|
| A(23,10) | 151.9 | 150 |
| A(18,4) | 6553.6 | 6552 |
| A(19,4) | 13107.2 | 13104 |
| A(20,4) | 26214.4 | 26168 |

For binary codes the published upper bound essentially *is* the linear program, so the certificate
half would have measured whether a candidate can call `scipy.optimize.linprog`. The checker itself
was validated first — on seven `(n, d)` where `A(n, d)` is known exactly, the certified bound was
sound in every case and tight in four — so this is a fact about the field rather than a bug in the
implementation. A certificate task needs a cell where the standard relaxation is *not* already
tight; Bell-inequality bounds under the NPA hierarchy are the candidate.

## Robustness

- Twelve malformed submissions — raising, `None`, a string, an empty list, ragged rows, non-binary
  entries, wrong length, duplicated words, two words at distance 1, more than the word cap, a
  one-dimensional return and a three-dimensional one — all score zero with `valid = 0`, and none
  raises out of the evaluator.
- Two consecutive evaluations of the reference are key-identical.
