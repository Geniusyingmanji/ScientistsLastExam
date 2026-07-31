"""Frozen oracle for CirclePacking (hidden from the agent).

Pack N non-overlapping unit circles inside the smallest possible square. The score is the
inverse of the achieved square side length, normalized against the best-known packing from
Packomania (E. Specht) and a trivial grid baseline. Packing problems have no known closed-form
solution for most N; the best-known values are conjectured optima from computational search.
"""

from __future__ import annotations

import numpy as np

# (N, best_known_side_length) from Packomania / Specht database.
# These are the smallest known square side for N unit circles (radius 1).
INSTANCES = [
    {"n": 7, "best_side": 5.7321, "note": "known optimal"},
    {"n": 10, "best_side": 6.7474, "note": "Packomania"},
    {"n": 13, "best_side": 7.6274, "note": "Packomania"},
]


def check_packing(n: int, centers, side: float) -> dict:
    try:
        pts = np.asarray(centers, dtype=float)
    except Exception as exc:
        return {"valid": False, "reason": f"bad centers: {exc}"}
    if pts.shape != (n, 2):
        return {"valid": False, "reason": f"expected ({n},2), got {pts.shape}"}
    if not np.all(np.isfinite(pts)):
        return {"valid": False, "reason": "non-finite"}
    if side <= 2.0:
        return {"valid": False, "reason": f"side {side} too small for any circle"}
    # Check all circles inside [0, side] x [0, side] with radius 1
    for i in range(n):
        x, y = pts[i]
        if x < 1.0 or x > side - 1.0 or y < 1.0 or y > side - 1.0:
            return {"valid": False, "reason": f"circle {i} at ({x:.3f},{y:.3f}) outside box"}
    # Check no overlap (min distance >= 2.0 between centers)
    for i in range(n):
        for j in range(i + 1, n):
            d = np.linalg.norm(pts[i] - pts[j])
            if d < 2.0 - 1e-9:
                return {"valid": False, "reason": f"overlap {i}-{j} dist={d:.6f}"}
    return {"valid": True}


def grid_baseline_side(n: int) -> float:
    import math
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    return max(2.0 * cols, 2.0 * rows)


def score_instance(entry: dict, pack_circles) -> dict:
    n = entry["n"]
    best_side = entry["best_side"]
    baseline_side = grid_baseline_side(n)
    try:
        centers, side = pack_circles(n)
    except Exception as exc:
        return {"n": n, "valid": False, "reason": f"raised: {exc}", "score": 0.0}
    side = float(side)
    r = check_packing(n, centers, side)
    if not r["valid"]:
        return {"n": n, "valid": False, "reason": r["reason"], "side": side, "score": 0.0}
    # Score: how much of the gap from baseline to best-known is closed
    # Lower side is better, so: progress = (baseline - achieved) / (baseline - best)
    if baseline_side <= best_side:
        score = 1.0 if side <= best_side else 0.0
    else:
        progress = (baseline_side - side) / (baseline_side - best_side)
        score = float(min(1.0, max(0.0, progress)))
    return {"n": n, "valid": True, "side": round(side, 4), "best_known": best_side,
            "baseline_side": baseline_side, "score": score}


def evaluate(pack_circles) -> dict:
    per = [score_instance(e, pack_circles) for e in INSTANCES]
    scores = [r["score"] for r in per]
    n_valid = sum(1 for r in per if r.get("valid"))
    return {
        "combined_score": float(np.mean(scores)) if scores else 0.0,
        "valid": 1.0 if n_valid == len(INSTANCES) else 0.0,
        "feasibility_rate": n_valid / len(INSTANCES),
        "per_instance": per,
    }
