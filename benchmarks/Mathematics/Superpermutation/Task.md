# Superpermutation — shorter strings that contain every permutation

## Scientific background

A superpermutation on `n` symbols is a string over `{1, …, n}` that contains every permutation
of those symbols as a contiguous substring. Minimal lengths are known through `n = 5`; for
`n = 6`, 872 is the shortest published construction but has not been proved minimal. For
`n = 7` the shortest known string has length 5906 (Egan–Houston, February 2019) against the
anonymous-4chan lower bound of 5884 — a gap of 22 symbols. For `n = 8` the current best-known
upper bound is 46205, found by Greg Egan in October 2018 via the Williams construction (OEIS A180632),
against the same-style lower bound 46085 — a gap of 119. There is **no required string**. One symbol
shorter than the record is a paper; the score is built to keep climbing.

## Your task

Edit **`solution.py`** so it defines:

```python
def build_superpermutation(n: int) -> str:
    """Return a string over the characters '1'..str(n) that contains every n-permutation
    as a contiguous substring."""
```

The evaluator calls it for `n = 7` and `n = 8`, **checks that all `n!` permutations appear as
substrings**, and reads off the length `L`. Shorter valid strings score higher.

## Scoring

For each `n`, with `naive = n · n!` (concatenate every permutation) and `sota` the shortest
known length:

```
score(n) = max(0, (naive − L) / (naive − sota))      # UNCAPPED above
```

So the concatenation baseline scores 0, matching the published record scores 1.0, and **beating
it scores above 1.0**. `combined_score` is the mean over `n`. An invalid string (wrong
alphabet, missing a permutation, or longer than the checker cap) scores 0 for that `n`.

## Rules

- Only edit `solution.py`; keep the `build_superpermutation(n)` signature and string output.
- Characters must be the digits `1` through `n` (n is 7 or 8, so no two-digit symbols).
- `numpy`/stdlib only, CPU. Do not read anything under `verification/` or `frontier_eval/`.
