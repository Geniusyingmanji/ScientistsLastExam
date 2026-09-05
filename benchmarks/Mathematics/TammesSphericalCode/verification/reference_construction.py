"""Truth-blind reference construction for TammesSphericalCode.

Randomized hill-climbing on the sphere: starts from several random point sets (normalized
to the unit sphere), then repeatedly perturbs one randomly-chosen point by a shrinking
random offset (re-normalizing back onto the sphere afterward) and keeps the move only if it
strictly lowers the maximum pairwise dot product; otherwise the point snaps back. Repeats
with many random restarts, keeping the best point set found. This is a real, standard
technique for this kind of spherical-code optimization -- not the certified global-
optimization methods behind the cited record -- and it does not reach the published
best-known configuration, leaving real headroom for a smarter search.
"""
from __future__ import annotations

import random

import numpy as np


def _max_pairwise_dot(points: np.ndarray) -> float:
    unit = points / np.linalg.norm(points, axis=1)[:, None]
    gram = unit @ unit.T
    np.fill_diagonal(gram, -1.0)
    return float(gram.max())


def _one_run(n: int, iters: int, rng: random.Random) -> tuple[float, np.ndarray]:
    points = np.array([[rng.gauss(0, 1) for _ in range(3)] for _ in range(n)])
    points /= np.linalg.norm(points, axis=1)[:, None]
    current = _max_pairwise_dot(points)
    step = 0.6
    for it in range(iters):
        i = rng.randrange(n)
        old = points[i].copy()
        perturbed = old + np.array([rng.uniform(-step, step) for _ in range(3)])
        norm = np.linalg.norm(perturbed)
        if norm < 1e-9:
            continue
        points[i] = perturbed / norm
        candidate = _max_pairwise_dot(points)
        if candidate < current:
            current = candidate
        else:
            points[i] = old
        if it % 2500 == 2499:
            step *= 0.6
    return current, points


def construct_points(n: int, iters: int = 15000, restarts: int = 25, seed: int = 0):
    rng = random.Random(seed)
    best_score, best_points = None, None
    for _ in range(restarts):
        score, points = _one_run(n, iters, rng)
        if best_score is None or score < best_score:
            best_score, best_points = score, points
    return best_points.tolist()
