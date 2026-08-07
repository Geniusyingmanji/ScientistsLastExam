"""Truth-blind reference decoder for QuantumErrorDecoder, numpy/scipy only.

MWPM-style: build a weighted matching graph from the graphlike error model, compute all-pairs
shortest paths with observable parity, then greedily match defects. Used only to verify that
the task is solvable within the declared constraints and to measure headroom.
"""

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra


def _build_graph(problem):
    nd = problem["num_detectors"]
    boundary = nd  # single virtual boundary node
    n = nd + 1
    # combine parallel error components: p_tot = p1(1-p2) + p2(1-p1)
    edge_p = {}
    edge_obs = {}
    for e in problem["errors"]:
        p = float(e["p"])
        if p <= 0.0 or p >= 1.0:
            continue
        dets = e["dets"]
        if len(dets) == 1:
            u, v = dets[0], boundary
        elif len(dets) == 2:
            u, v = dets[0], dets[1]
        else:
            continue
        key = (min(u, v), max(u, v))
        obs_mask = 0
        for o in e["obs"]:
            obs_mask ^= (1 << o)
        if key in edge_p:
            q = edge_p[key]
            edge_p[key] = p * (1 - q) + q * (1 - p)
            # keep the parity of the more likely mechanism
            if p > q:
                edge_obs[key] = obs_mask
        else:
            edge_p[key] = p
            edge_obs[key] = obs_mask

    rows, cols, wts = [], [], []
    for (u, v), p in edge_p.items():
        w = np.log((1.0 - p) / p)
        if not np.isfinite(w) or w <= 0:
            w = 1e-6
        rows += [u, v]
        cols += [v, u]
        wts += [w, w]
    graph = csr_matrix((wts, (rows, cols)), shape=(n, n))
    return graph, edge_obs, boundary, n


def _all_pairs(graph, nodes, n):
    dist, pred = dijkstra(graph, directed=False, indices=nodes, return_predecessors=True)
    return dist, pred


def _path_parity(pred_row, src, dst, edge_obs):
    parity = 0
    cur = dst
    guard = 0
    while cur != src and cur >= 0 and guard < 10000:
        prv = pred_row[cur]
        if prv < 0:
            return None
        key = (min(prv, cur), max(prv, cur))
        parity ^= edge_obs.get(key, 0)
        cur = prv
        guard += 1
    return parity if cur == src else None


def decode(problem, detection_events):
    nobs = problem["num_observables"]
    shots = detection_events.shape[0]
    graph, edge_obs, boundary, n = _build_graph(problem)

    det = np.asarray(detection_events, dtype=bool)
    active = np.flatnonzero(det.any(axis=0))
    nodes = np.concatenate([active, [boundary]]) if active.size else np.array([boundary])
    dist, pred = _all_pairs(graph, nodes, n)
    idx_of = {int(v): i for i, v in enumerate(nodes)}

    # cache parities between node pairs
    par_cache = {}

    def parity(u, v):
        key = (u, v)
        if key not in par_cache:
            par_cache[key] = _path_parity(pred[idx_of[u]], u, v, edge_obs) or 0
        return par_cache[key]

    out = np.zeros((shots, nobs), dtype=bool)
    for s in range(shots):
        defects = np.flatnonzero(det[s])
        if defects.size == 0:
            continue
        remaining = list(int(d) for d in defects)
        acc = 0
        # greedy: repeatedly take the globally cheapest available pairing (incl. boundary)
        while remaining:
            best = None
            for i, u in enumerate(remaining):
                du = dist[idx_of[u]]
                # to boundary
                cb = du[boundary]
                if best is None or cb < best[0]:
                    best = (cb, i, None)
                for j in range(i + 1, len(remaining)):
                    v = remaining[j]
                    c = du[v]
                    if c < best[0]:
                        best = (c, i, j)
            cost, i, j = best
            u = remaining[i]
            if j is None:
                acc ^= parity(u, boundary)
                remaining.pop(i)
            else:
                v = remaining[j]
                acc ^= parity(u, v)
                for k in sorted((i, j), reverse=True):
                    remaining.pop(k)
        for o in range(nobs):
            out[s, o] = bool((acc >> o) & 1)
    return out
