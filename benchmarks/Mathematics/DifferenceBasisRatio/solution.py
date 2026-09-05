"""Initial baseline for DifferenceBasisRatio.

A "two-level" difference basis: {0,...,k-1} (covers every small difference 1..k-1 directly),
its negatives {-(k-1),...,-1} and the multiples {0,k,2k,...} up to n (covers every
difference that is a multiple of k, or a multiple of k plus a small remainder, by combining
one element from each part). Choosing k ~= sqrt(2n) balances the two parts' sizes. This is a
real, simple, standard technique for this problem, but is not tuned or pruned in any way --
edit this file to do better.
"""
from __future__ import annotations

import math


def construct_basis(n: int):
    """Return {"n": n, "basis": [...]}: a difference basis covering every k in 1..n."""
    k = max(1, round(math.sqrt(2 * n)))
    basis = set(range(0, k)) | set(range(-(k - 1), 0)) | set(range(0, n + 1, k))
    return {"n": n, "basis": sorted(basis)}
