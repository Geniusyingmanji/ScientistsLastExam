"""Initial baseline for CoveringDesignBlocks.

A weak randomized greedy: visits candidate 7-subsets of {0,...,12} in a random order and
keeps the first one that covers at least one currently-uncovered 4-subset (rather than
searching for the block covering the *most* uncovered 4-subsets); repeats until every
4-subset is covered. This "first improvement" rule is a real, simple technique, but far
less effective than a max-gain greedy -- edit this file to do better.
"""
from __future__ import annotations

import random
from itertools import combinations

V, K, T = 13, 7, 4


def construct_blocks(seed: int = 0):
    """Return a list of 7-element subsets of {0,...,12} covering every 4-element subset."""
    rng = random.Random(seed)
    all_quads = list(combinations(range(V), T))
    quad_index = {q: i for i, q in enumerate(all_quads)}
    all_blocks = list(combinations(range(V), K))
    order = list(range(len(all_blocks)))
    rng.shuffle(order)

    def covered_by(block):
        return {quad_index[q] for q in combinations(block, T)}

    uncovered = set(range(len(all_quads)))
    chosen = []
    ptr = 0
    while uncovered and ptr < len(order):
        block = all_blocks[order[ptr]]
        ptr += 1
        gain = uncovered & covered_by(block)
        if gain:
            chosen.append(block)
            uncovered -= gain
    return [list(b) for b in chosen]
