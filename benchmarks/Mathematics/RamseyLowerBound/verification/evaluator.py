"""Frozen oracle for RamseyLowerBound (hidden from the agent).

A 2-coloring of K_n with no red K_s and no blue K_t is a witness that R(s, t) >= n+1.
The oracle checks the coloring and returns n. Larger is better; the score is uncapped
relative to the best published construction order (reaching it = 1.0, beating it > 1.0).
The complete-bipartite coloring with parts of size t-1 is always valid and is the floor.
"""
from __future__ import annotations

import itertools

import numpy as np

# (s, t) -> (baseline n = 2*(t-1), published construction order).
# MAX_N is a checker budget, not a score cap: R(5,5)<=46 and R(4,6)<=41, plus a little headroom.
INSTANCES = {
    (5, 5): {"baseline": 8, "sota_ref": 42, "max_n": 50},   # Exoo 1989: R(5,5) >= 43
    (4, 6): {"baseline": 10, "sota_ref": 35, "max_n": 42},  # Exoo: R(4,6) >= 36
}


def _normalized(value: float, baseline: float, sota: float) -> float:
    """0 at baseline, 1 at sota, >1 beyond. `value` is the higher-is-better quantity."""
    denom = sota - baseline
    if denom == 0:
        return 0.0
    return float(max(0.0, (value - baseline) / denom))


def _contains_clique(adj: np.ndarray, k: int) -> bool:
    n = int(adj.shape[0])
    if k <= 1:
        return n >= k
    if k == 2:
        return bool(np.any(adj))
    masks = [0] * n
    for i in range(n):
        mask = 0
        row = adj[i]
        for j in range(n):
            if row[j]:
                mask |= 1 << j
        masks[i] = mask
    for combo in itertools.combinations(range(n), k):
        ok = True
        for a in range(k):
            mask = masks[combo[a]]
            for b in range(a + 1, k):
                if ((mask >> combo[b]) & 1) == 0:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            return True
    return False


def verify_coloring(raw, s: int, t: int, max_n: int) -> tuple[bool, int, str]:
    try:
        adj = np.asarray(raw)
    except Exception as exc:  # noqa: BLE001
        return False, 0, f"non-array: {exc}"
    if adj.ndim != 2 or adj.shape[0] != adj.shape[1]:
        return False, 0, "coloring must be a square matrix"
    n = int(adj.shape[0])
    if n < 1 or n > max_n:
        return False, n, f"n={n} outside (0, {max_n}] for ({s},{t})"
    if not np.issubdtype(adj.dtype, np.number):
        return False, n, "non-numeric coloring"
    if not np.all(np.isfinite(adj)):
        return False, n, "non-finite coloring"
    if np.any((adj != 0) & (adj != 1)):
        return False, n, "entries must be 0 (red) or 1 (blue)"
    if not np.array_equal(adj, adj.T):
        return False, n, "coloring is not symmetric"
    if np.any(np.diag(adj) != 0):
        return False, n, "diagonal must be 0"
    red = adj == 0
    np.fill_diagonal(red, False)
    blue = adj == 1
    if _contains_clique(red, s):
        return False, n, f"red K_{s} present"
    if _contains_clique(blue, t):
        return False, n, f"blue K_{t} present"
    return True, n, "ok"


def score_pair(s: int, t: int, ref: dict, build_coloring) -> dict:
    try:
        raw = build_coloring(s, t)
    except Exception as exc:  # noqa: BLE001
        return {"s": s, "t": t, "valid": False, "reason": f"raised: {exc}", "score": 0.0}
    ok, n, reason = verify_coloring(raw, s, t, int(ref["max_n"]))
    if not ok:
        return {"s": s, "t": t, "valid": False, "reason": reason, "n": n, "score": 0.0}
    base, sota = ref["baseline"], ref["sota_ref"]
    return {
        "s": s, "t": t, "valid": True, "n": n, "sota_ref": sota,
        "score": _normalized(float(n), float(base), float(sota)),
    }


def evaluate(build_coloring) -> dict:
    per = [score_pair(s, t, ref, build_coloring) for (s, t), ref in INSTANCES.items()]
    scores = [r["score"] for r in per]
    n_valid = sum(1 for r in per if r.get("valid"))
    return {
        "combined_score": float(np.mean(scores)) if scores else 0.0,
        "valid": 1.0 if n_valid == len(INSTANCES) else 0.0,
        "feasibility_rate": n_valid / len(INSTANCES),
        "beat_sota": bool(any(r.get("score", 0.0) > 1.0 for r in per)),
        "per_pair": per,
    }
