"""Initial baseline for HeilbronnTrianglePacking.

Places the n points at the vertices of a regular n-gon inscribed in the unit square's
largest inscribed circle (center (0.5, 0.5), radius 0.5) -- motivated by Goldberg's
conjecture that optimal Heilbronn configurations for small n are affine images of regular
n-gons (true only for n=6, but a reasonable starting point for other n). Valid by
construction (every vertex lies on the circle, hence inside the square), but leaves real
room: the true optimal configurations for these n are known to look meaningfully different
from a regular polygon. Edit this file to do better.
"""
from __future__ import annotations

import math


def construct_points(n: int):
    """Return a list of n [x, y] points in the unit square [0, 1]^2."""
    points = []
    for i in range(n):
        theta = 2.0 * math.pi * i / n
        x = 0.5 + 0.5 * math.cos(theta)
        y = 0.5 + 0.5 * math.sin(theta)
        points.append([x, y])
    return points
