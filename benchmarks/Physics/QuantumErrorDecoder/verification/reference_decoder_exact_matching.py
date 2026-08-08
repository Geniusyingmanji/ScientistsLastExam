"""Stronger truth-blind decoder: exact min-weight defect matching via assignment reduction.

Purpose is fairness auditing, not shipping: it answers whether the PyMatching anchor is
reachable inside the numpy/scipy-only constraint the task imposes on candidates.

Method. Build the matching graph from graphlike error components, weight edges
log((1-p)/p), and add a single virtual boundary. For each shot the defects must be paired
with each other or sent to the boundary -- a minimum-weight T-join. Reduce it to a balanced
assignment problem: with k defects, use a 2k x 2k cost matrix whose top-left block holds
defect-defect shortest paths, whose diagonal blocks hold boundary costs, and whose bottom-right
block is zero. scipy.optimize.linear_sum_assignment then solves it exactly, and a symmetric
optimum always exists because the cost matrix is symmetric.
"""

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

_BIG = 1e9


def _build_graph(problem):
    nd = problem["num_detectors"]
    boundary = nd
    n = nd + 1
    edge_p, edge_obs = {}, {}
    for e in problem["errors"]:
        p = float(e["p"])
        if not (0.0 < p < 1.0):
            continue
        dets = e["dets"]
        if len(dets) == 1:
            u, v = dets[0], boundary
        elif len(dets) == 2:
            u, v = dets[0], dets[1]
        else:
            continue
        key = (min(u, v), max(u, v))
        mask = 0
        for o in e["obs"]:
            mask ^= 1 << o
        if key in edge_p:
            q = edge_p[key]
            if p > q:
                edge_obs[key] = mask
            edge_p[key] = p * (1 - q) + q * (1 - p)
        else:
            edge_p[key] = p
            edge_obs[key] = mask

    rows, cols, wts = [], [], []
    for (u, v), p in edge_p.items():
        w = np.log((1.0 - p) / p)
        if not np.isfinite(w) or w <= 0:
            w = 1e-6
        rows += [u, v]
        cols += [v, u]
        wts += [w, w]
    return csr_matrix((wts, (rows, cols)), shape=(n, n)), edge_obs, boundary, n


def _path_parity(pred_row, src, dst, edge_obs):
    parity, cur, guard = 0, dst, 0
    while cur != src and cur >= 0 and guard < 100000:
        prv = pred_row[cur]
        if prv < 0:
            return 0
        parity ^= edge_obs.get((min(prv, cur), max(prv, cur)), 0)
        cur = prv
        guard += 1
    return parity


def decode(problem, detection_events):
    nobs = problem["num_observables"]
    det = np.asarray(detection_events, dtype=bool)
    shots = det.shape[0]
    graph, edge_obs, boundary, n = _build_graph(problem)

    active = np.flatnonzero(det.any(axis=0))
    nodes = np.concatenate([active, [boundary]]).astype(int)
    dist, pred = dijkstra(graph, directed=False, indices=nodes, return_predecessors=True)
    idx = {int(v): i for i, v in enumerate(nodes)}

    # Precompute pairwise costs and parities once; every shot reuses them.
    par = {}

    def parity(u, v):
        k = (u, v)
        if k not in par:
            par[k] = _path_parity(pred[idx[u]], u, v, edge_obs)
        return par[k]

    out = np.zeros((shots, nobs), dtype=bool)
    for s in range(shots):
        defects = np.flatnonzero(det[s]).astype(int)
        k = defects.size
        if k == 0:
            continue
        if k == 1:
            u = int(defects[0])
            acc = parity(u, boundary)
            for o in range(nobs):
                out[s, o] = bool((acc >> o) & 1)
            continue

        rows = np.array([idx[int(u)] for u in defects])
        # top-left: defect-defect shortest paths
        cost = np.empty((2 * k, 2 * k), dtype=float)
        dd = dist[np.ix_(rows, defects)]
        dd = np.where(np.isfinite(dd), dd, _BIG)
        np.fill_diagonal(dd, _BIG)
        bnd = dist[rows, boundary]
        bnd = np.where(np.isfinite(bnd), bnd, _BIG)
        cost[:k, :k] = dd
        cost[:k, k:] = _BIG
        cost[k:, :k] = _BIG
        np.fill_diagonal(cost[:k, k:], bnd)
        np.fill_diagonal(cost[k:, :k], bnd)
        cost[k:, k:] = 0.0

        r, c = linear_sum_assignment(cost)
        acc = 0
        seen = set()
        for a, b in zip(r, c):
            if a >= k:
                continue
            u = int(defects[a])
            if b >= k:
                acc ^= parity(u, boundary)
            else:
                v = int(defects[b])
                key = (min(u, v), max(u, v))
                if key in seen:
                    continue
                seen.add(key)
                acc ^= parity(u, v)
        for o in range(nobs):
            out[s, o] = bool((acc >> o) & 1)
    return out
