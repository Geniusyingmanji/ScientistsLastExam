"""Truth-blind reference: triangle-inequality tightness. Calibration only.

The standard idea. A pair (u, v) is a direct edge exactly when no intermediate node w gives
d(u,w) + d(w,v) == d(u,v) with both legs shorter - that is, when the shortest path between them
cannot be decomposed. With a full distance matrix this recovers every visible edge; with a
partial one it recovers what the queried submatrix determines, so the strategy is to spend the
budget on a connected core and decide only within it.

It never sees the graph. It reads only what a candidate reads.
"""

from __future__ import annotations


def reconstruct(problem, distance):
    n = problem["nodes"]
    budget = problem["query_budget"]

    # Spend the budget on the largest complete submatrix the budget affords: with k nodes that is
    # k(k-1)/2 queries, and decomposition can only be checked inside it.
    k = n
    while k > 2 and k * (k - 1) // 2 > budget:
        k -= 1
    core = list(range(k))

    d = {}
    for i in range(k):
        for j in range(i + 1, k):
            value = distance(core[i], core[j])
            if value is None:
                break
            d[(core[i], core[j])] = value
        else:
            continue
        break

    def get(u, v):
        if u == v:
            return 0.0
        return d.get((min(u, v), max(u, v)))

    edges = []
    for i in range(k):
        for j in range(i + 1, k):
            direct = get(core[i], core[j])
            if direct is None:
                continue
            decomposable = False
            for m in range(k):
                if m in (i, j):
                    continue
                left, right = get(core[i], core[m]), get(core[m], core[j])
                if left is None or right is None:
                    continue
                if abs(left + right - direct) < 1e-9 and left > 0 and right > 0:
                    decomposable = True
                    break
            if not decomposable:
                edges.append((core[i], core[j], direct))
    return {"edges": edges}
