"""Truth-blind reference construction for BinaryCodeRecords.

"linear_68_15": tries several random binary 15x68 generator matrices and keeps the one with
the largest minimum distance (checked exactly by enumerating all 2^15 codewords). Random
linear codes are a real, standard technique in coding theory -- they typically come close
to the Gilbert-Varshamov bound -- but this small a search does not reach the published
record, leaving real headroom.

"general_21_10": a randomized greedy code construction -- visits candidate codewords (as
integers 0..2^21-1) in a random order and keeps each one that stays at Hamming distance
>= 10 from every codeword already kept; repeats with several random orders, keeping the
largest code found. A real, standard greedy technique, far from exhaustive, and it does
not reach the published record either.
"""
from __future__ import annotations

import random

import numpy as np


def _min_distance_linear(g: np.ndarray, k: int, n: int) -> int:
    num = 1 << k
    idx = np.arange(num, dtype=np.uint32)
    bits = ((idx[:, None] >> np.arange(k)[None, :]) & 1).astype(np.uint8)
    codewords = (bits @ g) % 2
    weights = codewords.sum(axis=1)
    weights[0] = n + 1
    return int(weights.min())


def _linear_68_15(trials: int = 30, seed: int = 0) -> list[list[int]]:
    rng = np.random.default_rng(seed)
    best_d, best_g = -1, None
    for _ in range(trials):
        g = rng.integers(0, 2, size=(15, 68), dtype=np.uint8)
        d = _min_distance_linear(g, 15, 68)
        if d > best_d:
            best_d, best_g = d, g
    return best_g.tolist()


def _general_21_10(trials: int = 8, seed: int = 0) -> list[list[int]]:
    rng = random.Random(seed)
    n, d = 21, 10

    def hamming(a: int, b: int) -> int:
        return bin(a ^ b).count("1")

    best_code: list[int] = []
    for _ in range(trials):
        order = list(range(1 << n))
        rng.shuffle(order)
        code: list[int] = []
        for x in order:
            if all(hamming(x, y) >= d for y in code):
                code.append(x)
        if len(code) > len(best_code):
            best_code = code
    return [[(x >> b) & 1 for b in range(n)] for x in best_code]


def construct_code(kind: str):
    if kind == "linear_68_15":
        return _linear_68_15()
    if kind == "general_21_10":
        return _general_21_10()
    raise ValueError("unknown kind: %r" % kind)
