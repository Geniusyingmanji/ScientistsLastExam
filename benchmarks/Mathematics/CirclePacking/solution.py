"""Initial baseline for CirclePacking (weak but valid).

Places N unit circles on a regular grid — valid but far from tight. Edit this file to do
better (simulated annealing, force-directed, billiard-style algorithms, ...).
"""

import math


def pack_circles(n: int):
    """Return (centers, side_length) where centers is an (n,2) list of circle centers
    and side_length is the square side. Circles have radius 1."""
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    side = max(2.0 * cols, 2.0 * rows)
    centers = []
    for i in range(n):
        r, c = divmod(i, cols)
        centers.append((1.0 + 2.0 * c, 1.0 + 2.0 * r))
    return centers, side
