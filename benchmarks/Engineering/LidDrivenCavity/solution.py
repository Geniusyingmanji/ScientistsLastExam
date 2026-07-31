"""Valid weak baseline: stationary interior with consistent wall vorticity."""

import numpy as np


def solve_cavity(Re, N):
    del Re
    n = int(N)
    h = 1.0 / (n - 1)
    streamfunction = np.zeros((n, n), dtype=float)
    vorticity = np.zeros((n, n), dtype=float)
    # Only the moving lid contributes for the zero-interior-flow baseline.
    vorticity[-1, 1:-1] = -2.0 / h
    vorticity[-1, 0] = -1.0 / h
    vorticity[-1, -1] = -1.0 / h
    return streamfunction, vorticity
