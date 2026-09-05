"""Truth-blind reference construction for MeritFactorSequence.

Randomized bit-flip hill-climbing: starts from several random +/-1 sequences of length 100,
then repeatedly flips one randomly-chosen sign and keeps the flip only if it strictly
raises the merit factor; otherwise the sign flips back. Repeats with many random restarts,
keeping the best sequence found. This is a real, standard local-search technique for this
problem -- not the algebraic construction (based on Barker-like arrays) behind the
published record -- and it does not reach that record, leaving real headroom for a smarter
search.
"""
from __future__ import annotations

import random

import numpy as np


def _merit_factor(a: np.ndarray) -> float:
    n = len(a)
    conv = np.correlate(a, a, mode="full")
    mid = n - 1
    total = float(np.sum(conv[mid + 1:] ** 2))
    return n * n / (2 * total) if total > 0 else float("inf")


def construct_sequence(n: int = 100, iters: int = 20000, restarts: int = 8, seed: int = 0):
    rng = random.Random(seed)
    best_mf, best_seq = None, None
    for _ in range(restarts):
        seq = np.array([rng.choice([-1.0, 1.0]) for _ in range(n)])
        current = _merit_factor(seq)
        for _it in range(iters):
            i = rng.randrange(n)
            seq[i] = -seq[i]
            candidate = _merit_factor(seq)
            if candidate > current:
                current = candidate
            else:
                seq[i] = -seq[i]
        if best_mf is None or current > best_mf:
            best_mf, best_seq = current, seq.copy()
    return best_seq.tolist()
