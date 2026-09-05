"""Initial baseline for ErdosMinimumOverlap.

Splits {1, ..., 2n} into the first half A = {1,...,n} and second half B = {n+1,...,2n}.
Valid by construction (exactly n elements each), but naive: it does not try to spread the
differences a - b across many values of k, so the overlap concentrates and max_k M_k = n,
the worst a partition can realistically do. Edit this file to do better -- distributing A
and B so that no single difference k is hit too often is the actual technique the cited
constructions use.
"""
from __future__ import annotations


def construct_partition(n: int):
    """Return a list of 2n labels (0 = in A, 1 = in B), n of each."""
    return [0] * n + [1] * n
