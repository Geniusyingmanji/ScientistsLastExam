"""Initial baseline for ConstantWeightCode.

Partitions {0,...,28} into disjoint 5-element blocks: {0..4}, {5..9}, {10..14}, {15..19},
{20..24} (5 blocks, points 25-28 unused). Disjoint blocks trivially share no point, let
alone a pair, so this is valid by construction with zero search -- but far short of the
published record. Edit this file to do better.
"""
from __future__ import annotations


def construct_blocks():
    """Return a list of 5-element subsets of {0,...,28}, no pair of points shared by two
    blocks."""
    return [list(range(5 * i, 5 * i + 5)) for i in range(5)]
