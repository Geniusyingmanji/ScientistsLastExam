"""Truth-blind reference construction for SchurPartition.

Builds a sum-free k-partition by Schur's classical doubling rule, applied recursively from the
trivial k=1 partition {1}: given a sum-free partition A_1,...,A_k of {1,...,n}, a sum-free
(k+1)-partition of {1,...,3n+1} is formed by adding a brand-new part {n+1,...,2n+1} and replacing
each A_i with A_i union {2n+1+x : x in A_i}. Applied k-1 times starting from {1}, this reaches
1, 4, 13, 40, 121, 364, 1093, ... for k = 1, 2, 3, .... This is a real, self-contained, inductively
provable construction technique -- not the SAT-solver search behind the published records -- and
it matches the true Schur numbers exactly for k <= 3 but falls further behind the real records as
k grows (e.g. 40 vs the true S(4) = 44), leaving real headroom for a smarter search.
"""
from __future__ import annotations


def _grow(parts: list[list[int]]) -> list[list[int]]:
    n = max(x for p in parts for x in p)
    grown = [list(p) + [2 * n + 1 + x for x in p] for p in parts]
    grown.append(list(range(n + 1, 2 * n + 2)))
    return grown


def construct_partition(k: int):
    parts = [[1]]
    while len(parts) < k:
        parts = _grow(parts)
    n = sum(len(p) for p in parts)
    assignment = [0] * n
    for idx, part in enumerate(parts):
        for x in part:
            assignment[x - 1] = idx
    return assignment
