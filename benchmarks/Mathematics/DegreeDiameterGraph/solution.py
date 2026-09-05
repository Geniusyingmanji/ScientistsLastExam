"""Initial baseline for DegreeDiameterGraph.

Builds the "central-edge double tree": two root vertices joined by one edge, each growing a
(d-1)-ary tree of depth 1 (each root already spends one degree slot on the central edge, leaving
d-1 slots for its own children). Any leaf-to-leaf path crosses: leaf -> its root -> the central
edge -> the other root -> its leaf, exactly 3 hops, so diameter = k = 3 by construction, and every
vertex has degree <= d by construction -- valid with zero search. Vertex count is only 2*d, far
below the published record (which uses a non-trivial algebraic or computer-search construction).
Edit this file to do better -- a real search should grow the graph well past a single tree layer.
"""
from __future__ import annotations


def construct_graph(d: int, k: int):
    """Return an edge list [(u, v), ...] with max degree <= d and diameter <= k.

    Vertex labels must be exactly 0..N-1 for the N vertices used.
    """
    assert k == 3, "this baseline only targets the k=3 sizes this task uses"
    # root_a = 0, root_b = 1; root_a's children are 2..d, root_b's children are d+1..2d-1
    edges = [(0, 1)]
    next_id = 2
    for _ in range(d - 1):
        edges.append((0, next_id))
        next_id += 1
    for _ in range(d - 1):
        edges.append((1, next_id))
        next_id += 1
    return edges
