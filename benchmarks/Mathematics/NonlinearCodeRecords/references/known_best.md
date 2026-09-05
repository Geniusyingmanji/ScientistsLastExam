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

## Frontier calibration draw (Opus 5, 2026-09-04)

Three seeds, greedy rewrite, `normal` feedback, budget 3, one calibration run
(`experiments/opus5_nonlinear_code_records_calibration_2026-09-04.json`).

| seed | proposal 1 | proposal 2 | proposal 3 | best |
|---|---|---|---|---|
| 0 | no code | no code | 0.641688 | 0.641688 |
| 1 | no code | no code | 0.383065 | 0.383065 |
| 2 | no code | no code | no code | protocol incomplete |

Two readings of this table are wrong and worth naming, because the second one changed the harness.

**It is not "the model scored zero two thirds of the time."** Every one of the six `no_code` draws
is a reply of 35-37 KB that stops in the middle of a word — the provider's output cap, reached
while the model was still reasoning about hyperplane weight distributions in PG(6,2). The
proposals never got as far as a program. At the time the run was recorded the ledger said
`response_truncated: false` on all six, because that field described the retained diagnostic copy
rather than the model's reply. The harness now records the provider's stop reason and reports
`protocol_incomplete: output_budget_exhausted` for a run in this shape; seed 2 is that run. A
re-draw at a larger `max_output_tokens` is required before any of this counts as model evidence.

**It is not a passed admission bar either.** Seed 0's single valid proposal scored 0.641688 —
key-identical to the reference, to eight digits. Opus 5 rebuilt the greedy parity-check linear
code. The admission bar asks that the first frontier proposal not *reach* the reference, and this
one reaches it exactly. What the draw does establish is the shape of the gap: a valid proposal
lands on the best linear code and stops there, which is the wall the task is about — every
published record at these lengths is held by a nonlinear code. Whether a searcher with room to
answer can get past that wall is unmeasured.

Status therefore stays **candidate**, and the two open items are a re-draw with a larger output
budget and a second searcher.

## Re-draw at a larger output budget (Opus 5, 2026-09-05)

The draw above was run at `max_output_tokens = 16000` and six of its nine proposals ended exactly
at that cap with no code block. Repeating it at 24000 changes the picture completely:

| seed | proposal 1 | proposal 2 | proposal 3 | best | output tokens used |
|---|---|---|---|---|---|
| 0 | 0.026447 | timeout | 0.393174 | 0.393174 | 8968 / 10956 / 10250 |
| 1 | 0.472371 | 0.568003 | 0.472371 | 0.568003 | — |

No proposal came near the new cap, so nothing here is an artefact of it. Two seeds of the three
completed; the third stopped on a transient provider failure and is excluded rather than counted.

**The admission bar passes.** The first valid proposal of each seed - 0.026 and 0.472 - is below the
reference of 0.6417, and so is the best of each run, 0.393 and 0.568. The earlier draw's single
valid proposal that landed key-identical to the reference is not reproduced here, and reads in
hindsight as one draw of a searcher that had almost no room to work in.

Status stays **candidate**: two usable seeds is thin, and a second searcher has still not been run.
