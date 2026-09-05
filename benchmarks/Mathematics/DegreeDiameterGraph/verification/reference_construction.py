"""Truth-blind reference construction for DegreeDiameterGraph.

Searches circulant graphs: vertices 0..n-1, each vertex i connected to i+s and i-s (mod n) for
every "step" s in a chosen set S. A circulant graph is vertex-transitive, so its diameter can be
measured with a single BFS from vertex 0 rather than one BFS per vertex -- a real efficiency this
construction exploits to search many (n, S) combinations. For each candidate n (scanned upward
from just past the baseline), several random step sets of the right size to make the graph exactly
d-regular are tried (an even d uses d/2 "full" steps, each contributing 2 to every vertex's
degree; an odd d additionally uses the single "half step" s = n/2, which only exists when n is
even and contributes 1 to every vertex's degree); the search keeps the largest n for which some
trial's circulant graph has diameter <= k. Circulant graphs are a standard, real technique in
degree/diameter research, not the literal algebraic/computer-search construction behind the
published record, and this randomized search does not reach it -- real headroom is left for a
proper voltage-graph or computer-search construction of the kind the cited papers use.
"""
from __future__ import annotations

import random
from collections import deque


def _circulant_diameter(n: int, steps: list[int], k_limit: int) -> int | None:
    adj_steps = set()
    for s in steps:
        adj_steps.add(s % n)
        adj_steps.add((-s) % n)
    adj_steps.discard(0)
    dist = [-1] * n
    dist[0] = 0
    q = deque([0])
    seen = 1
    worst = 0
    while q:
        u = q.popleft()
        if dist[u] > k_limit:
            return None
        for ds in adj_steps:
            v = (u + ds) % n
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                seen += 1
                q.append(v)
    if seen != n:
        return None
    worst = max(dist)
    return worst if worst <= k_limit else None


def _try_step_set(n: int, d: int, rng: random.Random) -> list[int] | None:
    if d % 2 == 0:
        pool = list(range(1, (n - 1) // 2 + 1))
        if len(pool) < d // 2:
            return None
        rng.shuffle(pool)
        return pool[: d // 2]
    if n % 2 != 0:
        return None
    pool = list(range(1, n // 2))
    if len(pool) < (d - 1) // 2:
        return None
    rng.shuffle(pool)
    return pool[: (d - 1) // 2] + [n // 2]


def construct_graph(d: int, k: int, trials_per_n: int = 60, max_n_multiple: float = 4.5, seed: int = 0):
    rng = random.Random(seed)
    best_n, best_steps = d + 1, None
    n = d + 1
    max_n = int(max_n_multiple * (2 * d))  # generous search ceiling relative to the trivial baseline
    while n <= max_n:
        found = None
        for _ in range(trials_per_n):
            steps = _try_step_set(n, d, rng)
            if steps is None:
                break
            if _circulant_diameter(n, steps, k) is not None:
                found = steps
                break
        if found is not None:
            best_n, best_steps = n, found
        n += 1
    if best_steps is None:
        # fall back to the double-tree baseline shape if no circulant beat it (should not happen
        # for the (d, k=3) sizes this task uses, but keeps this file valid standalone).
        edges = [(0, 1)]
        nxt = 2
        for _ in range(d - 1):
            edges.append((0, nxt))
            nxt += 1
        for _ in range(d - 1):
            edges.append((1, nxt))
            nxt += 1
        return edges
    adj_steps = set()
    for s in best_steps:
        adj_steps.add(s % best_n)
        adj_steps.add((-s) % best_n)
    adj_steps.discard(0)
    edges = set()
    for i in range(best_n):
        for ds in adj_steps:
            j = (i + ds) % best_n
            edges.add(frozenset((i, j)))
    return [tuple(e) for e in edges]
