"""Truth-blind reference construction for ZarankiewiczMatrix.

A randomized greedy filler: visit cells (i, j) in a random order, tentatively set the cell to 1,
and keep it unless doing so creates an s x t (here 3x3) all-ones submatrix -- checked
incrementally by testing only the row-triples that involve the row just touched (since every
other triple was already valid before this cell was set), which is far cheaper than re-checking
the whole matrix from scratch. Repeats this with several random cell orders, keeping the densest
valid matrix found across all restarts. This is a real, standard greedy construction technique --
not an exhaustive or SAT-based search -- and it does not reach the true (published) record,
leaving headroom for a smarter search (better cell ordering, local search / swaps after the greedy
pass, or an actual evolutionary/SAT-based search of the kind the cited papers used).
"""
from __future__ import annotations

import random
from itertools import combinations


def _violates(rowmasks: list[int], i: int, s: int, t: int) -> bool:
    """After tentatively updating row i, check only s-row combinations that include i."""
    m = len(rowmasks)
    others = [r for r in range(m) if r != i]
    for combo in combinations(others, s - 1):
        mask = rowmasks[i]
        for idx in combo:
            mask &= rowmasks[idx]
            if mask == 0:
                break
        if bin(mask).count("1") >= t:
            return True
    return False


def _one_pass(m: int, n: int, s: int, t: int, rng: random.Random) -> list[int]:
    rowmasks = [0] * m
    cells = [(i, j) for i in range(m) for j in range(n)]
    rng.shuffle(cells)
    for i, j in cells:
        rowmasks[i] |= (1 << j)
        if _violates(rowmasks, i, s, t):
            rowmasks[i] &= ~(1 << j)
    return rowmasks


def construct_matrix(m: int, n: int, s: int, t: int, restarts: int = 40, seed: int = 0):
    rng = random.Random(seed)
    best = None
    for _ in range(restarts):
        rowmasks = _one_pass(m, n, s, t, rng)
        ones = sum(bin(r).count("1") for r in rowmasks)
        if best is None or ones > best[0]:
            best = (ones, rowmasks)
    _, rowmasks = best
    return [[1 if (mask >> j) & 1 else 0 for j in range(n)] for mask in rowmasks]
