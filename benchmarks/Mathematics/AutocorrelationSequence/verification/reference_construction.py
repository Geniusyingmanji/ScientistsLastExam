"""Truth-blind reference construction for AutocorrelationSequence.

Randomized coordinate hill-climbing: starts from a triangular (tent-shaped) window plus
random jitter, then repeatedly perturbs one entry by a shrinking random offset and keeps
the move only when it strictly lowers the autoconvolution ratio; several random restarts,
keeping the best sequence found. A tapered window is a real, standard starting point for
minimizing autoconvolution/sidelobe energy, but this plain local search does not reach
either published bound, leaving real headroom for a smarter search.
"""
from __future__ import annotations

import random

import numpy as np


def _ratio(values: np.ndarray) -> float:
    n = len(values)
    conv = np.convolve(values, values)
    total = values.sum()
    return float(2 * n * conv.max() / (total ** 2))


def _one_run(n: int, nonneg: bool, iters: int, rng: random.Random) -> tuple[float, np.ndarray]:
    x = np.linspace(-1.0, 1.0, n)
    values = (1.0 - np.abs(x)) + 0.1 * np.array([rng.uniform(-1, 1) for _ in range(n)])
    if nonneg:
        values = np.clip(values, 0.01, None)
    current = _ratio(values)
    step = 0.3
    for it in range(iters):
        i = rng.randrange(n)
        old = values[i]
        values[i] = old + rng.uniform(-step, step)
        if nonneg and values[i] < 0:
            values[i] = old
            continue
        candidate = _ratio(values)
        if candidate < current:
            current = candidate
        else:
            values[i] = old
        if it % 1500 == 1499:
            step *= 0.7
    return current, values


def construct_sequence(signed: bool, iters: int = 8000, restarts: int = 6, seed: int = 0):
    n = 20 if signed else 100
    rng = random.Random(seed)
    best_score, best_values = None, None
    for _ in range(restarts):
        score, values = _one_run(n, not signed, iters, rng)
        if best_score is None or score < best_score:
            best_score, best_values = score, values
    return best_values.tolist()
