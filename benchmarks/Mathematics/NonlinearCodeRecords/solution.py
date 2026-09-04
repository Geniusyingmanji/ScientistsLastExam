"""Weak but valid baseline for NonlinearCodeRecords.

Split the coordinates into blocks of `d` and repeat one bit across each block. Two words either
agree everywhere or differ across a whole block, so the distance is at least `d` by construction
and the code has 2^(n//d) words - four of them at these lengths, against published records in the
hundreds. It is the answer that needs no idea, and it earns nothing.
"""
from __future__ import annotations

import numpy as np


def build_code(n, d):
    blocks = n // d
    words = np.zeros((1 << blocks, n), dtype=np.uint8)
    for mask in range(1 << blocks):
        for block in range(blocks):
            if mask >> block & 1:
                words[mask, block * d : (block + 1) * d] = 1
    return words.tolist()
