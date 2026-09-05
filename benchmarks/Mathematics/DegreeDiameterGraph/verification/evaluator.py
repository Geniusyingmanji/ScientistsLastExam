"""Frozen oracle for DegreeDiameterGraph (hidden from the agent).

The degree/diameter problem asks: given a maximum degree d and a diameter k, what is the largest
graph with max degree <= d and diameter <= k? The Moore bound M(d,k) = 1 + d + d(d-1) + ... +
d(d-1)^(k-1) upper-bounds it; the true largest known graphs at almost every (d, k) fall well short
of that bound and are not proven optimal -- a maintained public table just records "the largest
graph found so far." arXiv:2606.15860 ("New lower bounds for the degree/diameter problem via
interaction with a browser-accessible LLM") reports genuinely new record graphs found this way in
2026, at (d,k) pairs larger than the ones used here. The score below is uncapped relative to the
current published record: a valid submitted graph with more vertices than the cited record is a
real, checkable new lower bound on a problem still open today, not a benchmark artifact.
"""
from __future__ import annotations

from collections import deque

import numpy as np

# (d, k) -> naive-baseline vertex count (see solution.py) and the current best-known vertex count
# (largest graph found so far, not proven optimal at these sizes). See references/known_best.md.
SIZES = {
    "d4k3": {"d": 4, "k": 3, "baseline": 8, "sota_ref": 41},
    "d5k3": {"d": 5, "k": 3, "baseline": 10, "sota_ref": 72},
    "d6k3": {"d": 6, "k": 3, "baseline": 12, "sota_ref": 111},
}
MAX_N_MULTIPLE = 5.0  # reject absurd submissions without doing the expensive BFS sweep


def _normalized(value: float, baseline: float, sota: float) -> float:
    denom = sota - baseline
    if denom <= 0:
        return 0.0
    return float(max(0.0, (value - baseline) / denom))


def _diameter_or_none(adj: list[list[int]], n: int, k_limit: int) -> int | None:
    """BFS eccentricity from every vertex; returns the diameter, or None if disconnected or any
    eccentricity exceeds k_limit (short-circuits early, since the caller only needs a pass/fail
    against k_limit, not the exact diameter of a graph that already fails)."""
    worst = 0
    for src in range(n):
        dist = [-1] * n
        dist[src] = 0
        q = deque([src])
        seen = 1
        while q:
            u = q.popleft()
            if dist[u] > k_limit:
                return None
            for v in adj[u]:
                if dist[v] == -1:
                    dist[v] = dist[u] + 1
                    seen += 1
                    q.append(v)
        if seen != n:
            return None
        ecc = max(dist)
        if ecc > k_limit:
            return None
        worst = max(worst, ecc)
    return worst


def score_size(name: str, ref: dict, construct_graph) -> dict:
    d, k = ref["d"], ref["k"]
    try:
        raw = construct_graph(d, k)
    except Exception as exc:  # noqa: BLE001
        return {"size": name, "valid": False, "reason": "raised: %s" % exc, "score": 0.0}
    try:
        edges = [(int(u), int(v)) for u, v in raw]
    except Exception as exc:  # noqa: BLE001
        return {"size": name, "valid": False, "reason": "not a list of (u, v) pairs: %s" % exc, "score": 0.0}
    if any(u == v for u, v in edges):
        return {"size": name, "valid": False, "reason": "self-loop", "score": 0.0}
    edge_set = set(frozenset(e) for e in edges)
    if len(edge_set) != len(edges):
        return {"size": name, "valid": False, "reason": "duplicate edge", "score": 0.0}
    vertices = set()
    for u, v in edges:
        vertices.add(u)
        vertices.add(v)
    n = len(vertices)
    if n < 2 or vertices != set(range(n)):
        return {"size": name, "valid": False, "reason": "vertex labels must be exactly 0..N-1 with no gaps", "score": 0.0}
    if n > MAX_N_MULTIPLE * ref["sota_ref"]:
        return {"size": name, "valid": False, "reason": "vertex count out of accepted range", "score": 0.0}
    adj: list[list[int]] = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    max_deg = max(len(a) for a in adj)
    if max_deg > d:
        return {"size": name, "valid": False, "reason": "max degree %d exceeds d=%d" % (max_deg, d), "score": 0.0}
    diam = _diameter_or_none(adj, n, k)
    if diam is None:
        return {"size": name, "valid": False, "reason": "disconnected or diameter exceeds k=%d" % k, "score": 0.0}
    base, sota = ref["baseline"], ref["sota_ref"]
    return {
        "size": name, "valid": True, "n_vertices": n, "diameter": diam, "sota_ref": sota,
        "score": _normalized(float(n), float(base), float(sota)),
    }


def evaluate(construct_graph) -> dict:
    per = [score_size(name, ref, construct_graph) for name, ref in SIZES.items()]
    scores = [r["score"] for r in per]
    n_valid = sum(1 for r in per if r.get("valid"))
    return {
        "combined_score": float(np.mean(scores)) if scores else 0.0,
        "valid": 1.0 if n_valid == len(SIZES) else 0.0,
        "feasibility_rate": n_valid / len(SIZES),
        "beat_sota": bool(any(r.get("score", 0.0) > 1.0 for r in per)),
        "per_size": per,
    }
