"""Truth-blind reference construction for DifferenceBasisRatio.

Improves on the two-level baseline two ways: first, searches over a range of block sizes
k for the two-level construction ({0,...,k-1}, its negatives, and multiples of k up to n)
and keeps the smallest valid basis found; second, prunes the result by repeatedly trying to
remove each element and keeping the removal whenever the basis still covers every
difference 1..n, until no further removal helps. This is a real, standard two-stage
technique -- not the Fourier-analytic optimization behind the published 2.6390 bound -- and
it does not reach that bound, leaving real headroom for a smarter search.
"""
from __future__ import annotations

import random

import numpy as np


def _covers_all(basis: list[int], n: int) -> bool:
    lo, hi = min(basis), max(basis)
    span = hi - lo
    mask = np.zeros(span + 1, dtype=np.int64)
    mask[[x - lo for x in basis]] = 1
    conv = np.convolve(mask, mask[::-1])
    window = conv[span + 1: span + n + 1]
    return len(window) >= n and bool(np.all(window > 0))


def _two_level(n: int, k: int) -> list[int]:
    basis = set(range(0, k)) | set(range(-(k - 1), 0)) | set(range(0, n + 1, k))
    return sorted(basis)


def _best_two_level(n: int) -> list[int]:
    best = None
    lo_k = max(2, round((2 * n) ** 0.5) - 30)
    hi_k = round((2 * n) ** 0.5) + 30
    for k in range(lo_k, hi_k + 1):
        basis = _two_level(n, k)
        if _covers_all(basis, n):
            if best is None or len(basis) < len(best):
                best = basis
    return best if best is not None else _two_level(n, round((2 * n) ** 0.5))


def _prune(basis: list[int], n: int, rng: random.Random, max_rounds: int = 3) -> list[int]:
    basis = list(basis)
    for _ in range(max_rounds):
        rng.shuffle(basis)
        changed = False
        for x in list(basis):
            trial = [b for b in basis if b != x]
            if len(trial) >= 2 and _covers_all(trial, n):
                basis = trial
                changed = True
        if not changed:
            break
    return basis


def construct_basis(n: int, seed: int = 0):
    rng = random.Random(seed)
    basis = _best_two_level(n)
    basis = _prune(basis, n, rng)
    return {"n": n, "basis": basis}
