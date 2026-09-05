"""Truth-blind reference construction for CoveringDesignBlocks.

A max-gain greedy set cover: at each step, picks the 7-subset covering the most currently-
uncovered 4-subsets (not just the first one that helps at all, unlike solution.py's weak
greedy), until every 4-subset is covered. This is the standard greedy algorithm for set
cover -- a real, well-known technique, not the exhaustive/algebraic search behind the
published record -- and it does not reach that record, leaving real headroom.
"""
from __future__ import annotations

from itertools import combinations

V, K, T = 13, 7, 4


def construct_blocks():
    all_quads = list(combinations(range(V), T))
    quad_index = {q: i for i, q in enumerate(all_quads)}
    all_blocks = list(combinations(range(V), K))
    block_coverage = [
        [quad_index[q] for q in combinations(b, T)] for b in all_blocks
    ]
    uncovered = set(range(len(all_quads)))
    chosen = []
    while uncovered:
        best_idx, best_gain = None, -1
        for bi, cov in enumerate(block_coverage):
            gain = len(uncovered.intersection(cov))
            if gain > best_gain:
                best_gain = gain
                best_idx = bi
        chosen.append(all_blocks[best_idx])
        uncovered -= set(block_coverage[best_idx])
    return [list(b) for b in chosen]
