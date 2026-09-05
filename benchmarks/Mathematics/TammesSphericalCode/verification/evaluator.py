"""Frozen oracle for TammesSphericalCode (hidden from the agent).

The Tammes problem: place n points on the unit sphere S^2 to maximize the minimum angular
separation between any two of them -- equivalently, minimize the maximum pairwise dot
product (cosine of angle) among the n unit vectors. n=14 was proven optimal by Musin and
Tarasov (2015); n=15 remains open, and the best-known configuration (Cohn et al.'s
Spherical Codes database) is not proven optimal, so real headroom exists above it.

The score is uncapped relative to that best-known configuration: a valid submitted point
set with a smaller maximum pairwise dot product (larger minimum angle) is a real, checkable
new record.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np

# n -> (naive-baseline max pairwise dot product, best-known max pairwise dot product).
# Lower is better (smaller max dot product = larger minimum angular separation).
SIZES = {
    15: {
        "baseline": 0.8571428571428572,  # Fibonacci-sphere spiral (see solution.py), measured
        "sota_ref": 0.59260590292507377809642492233276,
    },
}


def _normalized_angle_score(value: float, baseline: float, sota: float) -> float:
    """0 at the baseline max-dot-product, 1 at the best-known minimum, unbounded beyond it.

    Smaller max-dot-product is better here (larger minimum angle), the mirror image of this
    codebase's usual `_normalized` convention -- named differently on purpose, matching
    Mathematics/NarrowAdmissibleTuple's `_normalized_diameter_score`."""
    denom = baseline - sota
    if denom <= 0:
        return 0.0
    return float(max(0.0, (baseline - value) / denom))


def max_pairwise_dot(points: np.ndarray) -> float:
    n = len(points)
    norms = np.linalg.norm(points, axis=1)
    unit = points / norms[:, None]
    best = -1.0
    for i, j in combinations(range(n), 2):
        dot = float(np.dot(unit[i], unit[j]))
        if dot > best:
            best = dot
    return best


def score_size(n: int, ref: dict, construct_points) -> dict:
    try:
        raw = construct_points(n)
    except Exception as exc:  # noqa: BLE001
        return {"n": n, "valid": False, "reason": "raised: %s" % exc, "score": 0.0}
    try:
        pts = np.asarray([[float(c) for c in p] for p in raw], dtype=np.float64)
    except Exception as exc:  # noqa: BLE001
        return {"n": n, "valid": False, "reason": "not a list of (x, y, z) points: %s" % exc, "score": 0.0}
    if pts.shape != (n, 3):
        return {"n": n, "valid": False, "reason": "expected exactly %d (x, y, z) points" % n, "score": 0.0}
    if not np.all(np.isfinite(pts)):
        return {"n": n, "valid": False, "reason": "coordinates must be finite", "score": 0.0}
    norms = np.linalg.norm(pts, axis=1)
    if np.any(norms < 1e-9):
        return {"n": n, "valid": False, "reason": "a point is (near) the origin and cannot be normalized", "score": 0.0}
    max_dot = max_pairwise_dot(pts)
    base, sota = ref["baseline"], ref["sota_ref"]
    return {
        "n": n, "valid": True, "max_dot_product": max_dot, "sota_ref": sota,
        "score": _normalized_angle_score(max_dot, float(base), float(sota)),
    }


def evaluate(construct_points) -> dict:
    per = [score_size(n, ref, construct_points) for n, ref in SIZES.items()]
    scores = [r["score"] for r in per]
    n_valid = sum(1 for r in per if r.get("valid"))
    return {
        "combined_score": float(np.mean(scores)) if scores else 0.0,
        "valid": 1.0 if n_valid == len(SIZES) else 0.0,
        "feasibility_rate": n_valid / len(SIZES),
        "beat_sota": bool(any(r.get("score", 0.0) > 1.0 for r in per)),
        "per_size": per,
    }
