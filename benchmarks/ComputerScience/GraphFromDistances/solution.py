"""Baseline: read every queried distance as a direct edge.

This is the misconception the task is about. A short distance between two nodes does not mean
they are adjacent - it may be a two-hop path whose legs happen to be short - and telling the two
apart is the whole problem. Valid by construction and deliberately weak.
"""


def reconstruct(problem, distance):
    n = problem["nodes"]
    edges = []
    for u in range(n):
        for v in range(u + 1, n):
            d = distance(u, v)
            if d is None:
                return {"edges": edges}
            edges.append((u, v, d))
    return {"edges": edges}
