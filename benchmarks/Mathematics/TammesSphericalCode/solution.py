"""Initial baseline for TammesSphericalCode.

Places the n points using a Fibonacci-sphere spiral (the golden-angle construction): a
simple, standard, deterministic way to spread points roughly evenly over a sphere. It is
not tailored to any specific n, so it leaves real room for a search that optimizes the
minimum angular separation directly. Edit this file to do better.
"""
from __future__ import annotations

import math


def construct_points(n: int):
    """Return a list of n [x, y, z] points on (or near) the unit sphere."""
    points = []
    golden_angle = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        y = 1 - 2 * i / (n - 1)
        radius = math.sqrt(max(0.0, 1 - y * y))
        theta = golden_angle * i
        x = math.cos(theta) * radius
        z = math.sin(theta) * radius
        points.append([x, y, z])
    return points
