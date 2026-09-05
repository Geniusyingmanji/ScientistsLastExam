"""Initial baseline for BinaryCodeRecords.

"linear_68_15": the identity-padded generator matrix [I_15 | 0] -- valid (rank 15, so 2^15
distinct codewords), but its minimum distance is only 1 (each of the first 15 unit-weight
rows is itself a codeword).

"general_21_10": just two complementary codewords (all-zeros and all-ones), trivially at
Hamming distance 21 >= 10, but only 2 codewords.

Edit this file to do better.
"""
from __future__ import annotations


def construct_code(kind: str):
    if kind == "linear_68_15":
        g = [[0] * 68 for _ in range(15)]
        for i in range(15):
            g[i][i] = 1
        return g
    if kind == "general_21_10":
        return [[0] * 21, [1] * 21]
    raise ValueError("unknown kind: %r" % kind)
