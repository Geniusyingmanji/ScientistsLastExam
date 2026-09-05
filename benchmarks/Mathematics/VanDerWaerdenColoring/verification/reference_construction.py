"""Truth-blind reference construction for VanDerWaerdenColoring.

Extends a coloring position by position: at each new position i, tries colors in a randomized
order and accepts the first one that does not complete a monochromatic k-term arithmetic
progression ending at i (checked incrementally against only the positions before i, not by
rescanning the whole array); stops when no color works. Repeats with several random restarts
(different per-position color-preference order), keeping the longest coloring found. This is a
real, standard greedy technique for this problem -- not the SAT-solver search behind the published
records -- and it does not reach the true best-known witness length, leaving headroom for a
smarter search (backtracking, or an actual SAT/ILP-based construction of the kind the cited papers
use).
"""
from __future__ import annotations

import random


def _completes_mono_ap(colors: list[int], i: int, c: int, k: int) -> bool:
    max_d = i // (k - 1)
    for d in range(1, max_d + 1):
        pos = i - d
        ok = True
        for _ in range(k - 1):
            if pos < 0 or colors[pos] != c:
                ok = False
                break
            pos -= d
        if ok:
            return True
    return False


def construct_coloring(r: int, k: int, restarts: int = 30, max_len: int = 15000, seed: int = 0):
    rng = random.Random(seed)
    best: list[int] = []
    for _ in range(restarts):
        colors: list[int] = []
        i = 0
        while i < max_len:
            order = list(range(r))
            rng.shuffle(order)
            placed = False
            for c in order:
                if not _completes_mono_ap(colors, i, c, k):
                    colors.append(c)
                    placed = True
                    break
            if not placed:
                break
            i += 1
        if len(colors) > len(best):
            best = colors
    return best
