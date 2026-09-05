# BinaryCodeRecords — beat two classical binary code records

## Scientific setting

Two real, currently-open binary error-correcting-code records:

- **`linear_68_15`**: the largest minimum distance of a binary *linear* `[68,15]` code (a
  15-dimensional linear code of length 68 over GF(2), given as a generator matrix). The
  minimum distance of a linear code equals the minimum Hamming weight among its
  `2^15 - 1` nonzero codewords -- exhaustively enumerable and exact. Best-known lower bound
  24 (Grassl's maintained table, `codetables.de`), upper bound 26.
- **`general_21_10`**: the largest binary (possibly non-linear) code of length 21 with
  minimum pairwise Hamming distance `>= 10` -- an explicit list of codewords, checked
  pairwise. Best-known lower bound 42 (Kaikkonen, 1989), upper bound 47.

Neither is proven optimal; real headroom exists at both.

## Your task

Implement:

```python
def construct_code(kind: str) -> list:
    """kind == "linear_68_15": return a 15x68 0/1 generator matrix.
    kind == "general_21_10": return a list of 0/1 codewords, each length 21."""
```

You will be called with both `kind` values. For `linear_68_15`, return exactly a `15x68`
matrix of `0`/`1` entries. For `general_21_10`, return any number of length-21 `0`/`1`
codewords with pairwise Hamming distance `>= 10` and no duplicates. Anything else -- wrong
shape, non-binary entries, a violated distance constraint -- scores that call zero. Never
an infrastructure failure.

## Evaluation

`score = (your_value - baseline) / (sota_ref - baseline)`, clipped below at 0 and
**unbounded above**:

| kind | metric | baseline (naive, always valid) | published record |
|---|---|---|---|
| `linear_68_15` | minimum distance | 1 (`[I_15 \| 0]`) | 24 |
| `general_21_10` | number of codewords | 2 (two complementary codewords) | 42 |

`combined_score` is the mean over both kinds. Matching the published record scores 1.0; a
better result (larger minimum distance, or more codewords) scores above 1.0 -- a real,
checkable new record, since the oracle checks your literal submitted matrix or codeword
list directly, not a recalled number.

## Available tools and resources

NumPy and the standard library are available. For `linear_68_15`, a standard, effective
technique: random binary generator matrices typically come close to the Gilbert-Varshamov
bound -- try several and keep the one with the largest exactly-computed minimum distance
(enumerate all `2^15` codewords via `bits @ G mod 2`, vectorized). For `general_21_10`, a
standard technique: a randomized greedy code construction -- visit candidate codewords in a
random order and keep each one that stays at distance `>= 10` from every codeword already
kept, with several random restarts. Neither reaches the published record, leaving real
headroom for a smarter search. Candidate execution is networkless and cannot look anything
up.

## Rules and scope

- Only edit `solution.py`; keep `construct_code(kind)`.
- `linear_68_15`: exactly a `15x68` `0`/`1` matrix. `general_21_10`: any number of distinct
  length-21 `0`/`1` codewords, pairwise distance `>= 10`.
- Deterministic CPU code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

References: M. Grassl, "Bounds on the minimum distance of linear codes and quantum codes"
(online database, `codetables.de`), entry `[68,15]`; M. K. Kaikkonen, "A new
four-error-correcting code of length 20," *IEEE Trans. Inform. Theory* 35 (1989), 1344
(`A(21,10) >= 42`); D. Gijswijt, H. Mittelmann, A. Schrijver, semidefinite programming
bound `A(21,10) <= 47` (`https://aeb.win.tue.nl/codes/binary-1.html`).
