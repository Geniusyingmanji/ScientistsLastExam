"""Initial baseline for SchurPartition.

Extends a partition element by element: for each new integer x = 1, 2, ..., tries parts in a
fixed round-robin order and places x in the first part where it does not complete a sum-free
violation (a, b already in that part, a=b allowed, with a + b = x); stops when no part works for
the next integer. A real, simple, self-contained technique -- but a single greedy pass with no
backtracking gets stuck early and falls well short of what a smarter construction (or the true
published records) achieves. Edit this file to do better.
"""
from __future__ import annotations


def _completes_violation(parts_sets: list[set], p: int, x: int) -> bool:
    part = parts_sets[p]
    half = x // 2
    for a in range(1, half + 1):
        if a in part and (x - a) in part:
            return True
    return False


def construct_partition(k: int):
    """Return a list of part indices (0..k-1), one per element 1..n, for the n this greedy pass
    reaches."""
    parts_sets: list[set] = [set() for _ in range(k)]
    assignment: list[int] = []
    x = 1
    while True:
        placed = False
        for p in range(k):
            if not _completes_violation(parts_sets, p, x):
                parts_sets[p].add(x)
                assignment.append(p)
                placed = True
                break
        if not placed:
            break
        x += 1
    return assignment
