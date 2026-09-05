"""Truth-blind reference construction for HeilbronnTrianglePacking.

Randomized coordinate hill-climbing: starts from several random point sets in the unit
square, then repeatedly perturbs one randomly-chosen point by a random offset (shrinking
the offset size over time, a simple annealed step size) and keeps the move only if it
strictly increases the minimum triangle area; otherwise the point snaps back. Repeats with
many random restarts, keeping the best point set found. This is a real, standard technique
for this kind of geometric packing problem -- not the certified global-optimization or
computer-assisted-proof methods behind the cited records -- and it does not reach any of
the three published records here, leaving real headroom for a smarter search.
"""
from __future__ import annotations

import random
from itertools import combinations


def _min_triangle_area(points: list[list[float]]) -> float:
    n = len(points)
    best = None
    for i, j, k in combinations(range(n), 3):
        x1, y1 = points[i]
        x2, y2 = points[j]
        x3, y3 = points[k]
        area = abs(x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)) / 2.0
        if best is None or area < best:
            best = area
    return best


def _one_run(n: int, iters: int, rng: random.Random) -> tuple[float, list[list[float]]]:
    points = [[rng.random(), rng.random()] for _ in range(n)]
    current = _min_triangle_area(points)
    step = 0.3
    for it in range(iters):
        i = rng.randrange(n)
        old = points[i][:]
        points[i][0] = min(1.0, max(0.0, points[i][0] + rng.uniform(-step, step)))
        points[i][1] = min(1.0, max(0.0, points[i][1] + rng.uniform(-step, step)))
        candidate = _min_triangle_area(points)
        if candidate > current:
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
        if best_score is None or score > best_score:
            best_score, best_points = score, points
    return best_points
