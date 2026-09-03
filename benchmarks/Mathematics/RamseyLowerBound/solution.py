"""Initial baseline for RamseyLowerBound (complete bipartite, parts of size t-1).

Red edges run between the two parts, blue edges fill each part. The red graph is bipartite
(so clique number 2) and each blue clique has size t-1, so the coloring is a valid
(s, t)-Ramsey coloring for any s >= 3. It is far from the published records. Edit this
file to emit a larger coloring — cyclic, Paley, simulated annealing, SAT, or better.
"""
import numpy as np


def build_coloring(s: int, t: int):
    """Return an n x n array. 0 = red, 1 = blue, diagonal 0, symmetric."""
    part = int(t) - 1
    n = 2 * part
    adj = np.ones((n, n), dtype=np.int8)
    adj[:part, part:] = 0
    adj[part:, :part] = 0
    np.fill_diagonal(adj, 0)
    return adj
