# NonlinearCodeRecords — build a bigger binary code than a linear one can be

## 关系与区别 / How this differs from the nearest tasks in this repository

- **`Mathematics/CapSet` and `Mathematics/CapSetFrontier`** are the closest in shape: construct the
  largest object avoiding a forbidden pattern, scored against a published record, uncapped. They
  live in `Z_3^n` with a three-term line condition; this is `F_2^n` with a pairwise distance
  condition, and the instances are disjoint.
- **`Mathematics/KissingNumber`** also packs points at a minimum separation, but on a continuous
  sphere with a real-valued angle, so its failure modes are numerical rather than combinatorial.
- **`QuantumErrorCorrection/QuantumErrorDecoder`** is about *decoding* a fixed code, not
  constructing one, and it is scored on logical error rate rather than size.
- Nothing in the Frontier-Eng catalogue concerns coding theory.

## The question

`A(n, d)` is the largest number of binary words of length `n` that pairwise differ in at least `d`
positions. It is unknown for most `(n, d)`. Build a code as large as you can, for four `(n, d)`
where the answer is open.

## Why the linear code is not the answer

A parity-check construction gives the largest *linear* code in under a second: grow a column set
over `F_2^r` in which no column is the sum of at most `d-2` of the others, take the smallest `r`
that admits `n` columns, read off the nullspace. It is the reference here, and at these parameters
it stops well short:

| instance | trivial | largest linear | published record | published upper bound |
|---|---|---|---|---|
| A(23, 10) | 4 | 64 | **80** | 150 |
| A(24, 10) | 4 | 64 | **136** | 268 |
| A(25, 10) | 4 | 128 | **192** | 466 |
| A(26, 10) | 4 | 256 | **384** | 836 |

Every record in that column is held by a **nonlinear** code. Linearity is a convenience, not a
constraint of the problem, and giving it up is the task.

It is not a small step. The obvious first attempt — keep the linear code and add cosets `x + C` —
cannot even start at these parameters: a coset is admissible only when its representative sits at
distance at least `d` from all of `C`, and the covering radius of these codes is below `d`, so no
such representative exists. The published constructions come from the Kerdock and Preparata
families and from long computer searches.

## What you implement

```python
def build_code(n, d):
    ...
    return [[0, 1, 1, ...], ...]   # distinct binary rows of length n, pairwise distance >= d
```

### `problem` — the instances you will be called on

`build_code` is called once per instance with `(n, d)`. The four instances and their public
context are in the table above; the oracle also exposes them as:

| key | meaning |
|---|---|
| `instances` | one entry per instance: `n`, `distance`, `trivial_construction_size`, `published_upper_bound` |
| `max_codewords` | at most this many words per submission (40000) |
| `code_contract` | prose: what makes a submission valid |
| `scoring` | prose: where zero and one sit |

### What is checked

Every returned row must be binary, of length `n`, distinct from the others, and at Hamming
distance at least `d` from every other row. The check is a chunked exclusive-or and a popcount, so
a large code costs time but not doubt. A submission that fails any of these scores that instance
zero. It is never an infrastructure failure.

## How you are scored

For each instance, the progress from the block-repetition construction up to the published record:

```
score = (your size - trivial size) / (published record - trivial size)
```

`combined_score` is the mean over the four instances. **The scale is uncapped.** The published
record is the witness worth 1, not a ceiling — these are open cells, and a larger code scores above
one. Two counters are reported beside the score: how many instances beat the trivial construction,
and how many beat the published record.

## What each competence is worth

| strategy | score | A(23,10) | A(24,10) | A(25,10) | A(26,10) |
|---|---|---|---|---|---|
| greedy parity-check linear code (reference) | **0.642** | 64 | 64 | 128 | 256 |
| block-repetition construction (baseline) | 0.000 | 4 | 4 | 4 | 4 |
| published records | 1.000 | 80 | 136 | 192 | 384 |

**Low-dimensional shortcuts get nothing here.** A sweep of 39 strategies — random greedy accretion
at six seeds and two effort levels, and constant-weight codes at every weight from 0 to 26 —
scores **0.000**: at distance 10 a random word is almost never far enough from what you already
have, and no single weight class is big enough. The algebra is the task.

## Rules

- Only edit `solution.py`; keep `build_code(n, d)`.
- NumPy/SciPy only. Deterministic CPU code.
- Do not read `verification/` or `frontier_eval/`.
