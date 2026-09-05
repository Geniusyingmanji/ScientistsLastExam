# BinaryCodeRecords — reference results and anchor confidence

Every score below is produced by running code in this directory.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate solution.py --metrics-out /tmp/baseline.json
python3 frontier_eval/run_eval.py --candidate verification/reference_construction.py --metrics-out /tmp/reference.json
```

## The anchors (maintained tables, independently re-confirmed)

| kind | metric | value | status | source |
|---|---|---|---|---|
| `linear_68_15` | min distance | 24 | best-known, not proven optimal (upper bound 26) | M. Grassl, codetables.de, independently re-fetched 2026-09-06 |
| `general_21_10` | codewords | 42 | best-known, not proven optimal (upper bound 47) | M. K. Kaikkonen (1989); upper bound via Gijswijt-Mittelmann-Schrijver SDP |

Both are lower bounds without a matching upper-bound proof: real headroom exists for a
candidate to find either a `[68,15]` code with distance `>= 25`, or a length-21,
distance-10 code with `>= 43` codewords.

## Baseline — `solution.py`

`linear_68_15`: `[I_15 | 0]` (identity padded with zeros) -- valid (rank 15), but minimum
distance only 1 (each of the first 15 unit-weight rows is itself a codeword).
`general_21_10`: two complementary codewords (all-zeros, all-ones), trivially at distance 21.

| kind | value | score |
|---|---|---|
| `linear_68_15` | 1 | 0.0000 |
| `general_21_10` | 2 | 0.0000 |

## Reference — `verification/reference_construction.py`

`linear_68_15`: 30 random binary `15x68` generator matrices, keeping the one with the
largest exactly-computed minimum distance. `general_21_10`: a randomized greedy code
construction with 8 random restarts, visiting candidate codewords in a random order and
keeping each one that stays at distance `>= 10` from every codeword already kept.

| kind | value | score |
|---|---|---|
| `linear_68_15` | 19 | 0.7826 |
| `general_21_10` | 22 | 0.5000 |

`combined_score = 0.6413`. Measured directly by running
`verification/reference_construction.py` through the oracle above (runtime approx 16s for
both kinds together). Random linear codes are a real, standard technique that typically
comes close to the Gilbert-Varshamov bound, and randomized greedy is a real, standard
packing technique -- neither reaches its published record, leaving real headroom.

## What this task is not

This task scores the exact, finite, self-contained combinatorial object (a generator
matrix's exhaustively-enumerated minimum distance, or an explicit codeword list's pairwise
Hamming distances, both computed directly). It does not ask for, and does not check, the
algebraic or semidefinite-programming machinery behind the published upper bounds (26, 47)
-- that is separate, already-published mathematics this task does not re-derive or
re-check.
