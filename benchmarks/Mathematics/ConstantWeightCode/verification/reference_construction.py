"""Truth-blind reference construction for ConstantWeightCode.

Randomized greedy: visits all C(29,5) candidate 5-subsets in a random order, keeping each
one whose pairs are all still unused so far; repeats with several random orders, keeping
the largest code found. A real, standard greedy technique for this kind of "packing"
problem -- not the algebraic/computer-search construction behind the published record --
and it does not reach that record, leaving real headroom.
"""
from __future__ import annotations

import random
from itertools import combinations

N, W = 29, 5


def construct_blocks(trials: int = 20, seed: int = 0):
    rng = random.Random(seed)
    all_blocks = list(combinations(range(N), W))
    best: list[tuple[int, ...]] = []
    for _ in range(trials):
        order = list(range(len(all_blocks)))
        rng.shuffle(order)
        used_pairs: set[tuple[int, int]] = set()
        chosen: list[tuple[int, ...]] = []
        for bi in order:
            block = all_blocks[bi]
            pairs = list(combinations(block, 2))
            if all(p not in used_pairs for p in pairs):
                chosen.append(block)
                used_pairs.update(pairs)
        if len(chosen) > len(best):
            best = chosen
    return [list(b) for b in best]
