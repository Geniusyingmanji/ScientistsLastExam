# ConstantWeightCode — reference results and anchor confidence

Every score below is produced by running code in this directory.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate solution.py --metrics-out /tmp/baseline.json
python3 frontier_eval/run_eval.py --candidate verification/reference_construction.py --metrics-out /tmp/reference.json
```

## The anchor (best-known, genuinely open)

`A(29,8,5) >= 36` -- I. Bluskov, "New Constant Weight Codes and Packing Numbers,"
*Electron. Notes Discrete Math.* 65 (2018), 31-36, an explicit construction, summarized in
A. Brouwer's maintained constant-weight-code table (upper bound 39). Not proven optimal:
a candidate that finds a valid code with 37 or more blocks would be a genuine, new,
checkable record.

## Baseline — `solution.py`

Disjoint partition of `{0,...,28}` into 5-element blocks: `{0..4}, {5..9}, {10..14},
{15..19}, {20..24}` (5 blocks; points 25-28 unused). Disjoint blocks trivially share no
pair.

| num_blocks | score |
|---|---|
| 5 | 0.0000 |

## Reference — `verification/reference_construction.py`

Randomized greedy: 20 random orders over all `C(29,5)` candidate blocks, keeping each block
whose pairs are all still unused, keeping the largest code found across restarts.

| num_blocks | score |
|---|---|
| 28 | 0.7419 |

Measured directly by running `verification/reference_construction.py` through the oracle
above (runtime approx 2s). A real, standard greedy packing technique -- not the algebraic
or computer-search construction behind the published record -- and it does not reach that
record, leaving real headroom.

## What this task is not

This task scores the exact, finite, self-contained combinatorial object (a set of 5-blocks
and the pairwise-sharing constraint, checked directly). It does not ask for, and does not
check, the construction technique behind the published record or the upper-bound proof
(39) -- those are separate, already-published results this task does not re-derive or
re-check.
