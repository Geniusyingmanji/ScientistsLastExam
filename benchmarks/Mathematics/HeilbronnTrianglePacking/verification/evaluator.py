"""Frozen oracle for HeilbronnTrianglePacking (hidden from the agent).

The Heilbronn triangle problem: place n points in the closed unit square [0,1]^2 to
maximize the minimum area of any triangle formed by 3 of them. This is a real, actively
worked problem -- Erich's Packing Center maintains the record table for every n up to 16;
only n=5 through n=9 have been *proven* optimal by computer-assisted proof (most recently
n=9, by Sudermann-Merx in March 2026), and n>=10 remain best-known-only, with real headroom
above them. AlphaEvolve (arXiv:2506.13131) found new records on several *variants* of this
problem (different regions) in 2026 but did not beat the classic unit-square records used
here, underscoring how hard even a few extra points still are.

The score is uncapped relative to the cited record: a valid submitted point set with a
larger minimum triangle area than the record is a real, checkable improvement, scoring
above 1.0 at n=10 and n=11 (best-known only); at n=8 (proven optimal) exceeding 1.0 is
mathematically impossible, disclosed rather than hidden.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np

# n -> (naive-baseline min-triangle-area, best-known/proven min-triangle-area). n=8 is proven
# optimal; n=10, 11, 12 are best-known only. See references/known_best.md.
SIZES = {
    8: {"baseline": 0.051776695296636845, "sota_ref": 0.07237642431844414},   # (sqrt(13)-1)/36
    10: {"baseline": 0.028064248536224072, "sota_ref": 0.04654},
    11: {"baseline": 0.02145620494458457, "sota_ref": 0.037037037037037035},   # 1/27
    12: {"baseline": 0.016746824526945148, "sota_ref": 0.0325988586918197},
}
COORD_ATOL = 1e-9  # small slack for floating-point boundary placement


def _normalized(value: float, baseline: float, sota: float) -> float:
    """0 at baseline, 1 at sota, >1 beyond. `value` is the higher-is-better quantity."""
    denom = sota - baseline
    if denom <= 0:
        return 0.0
    return float(max(0.0, (value - baseline) / denom))


def min_triangle_area(points: np.ndarray) -> float:
    n = len(points)
    best = None
    for i, j, k in combinations(range(n), 3):
        x1, y1 = points[i]
        x2, y2 = points[j]
        x3, y3 = points[k]
        area = abs(x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)) / 2.0
        if best is None or area < best:
            best = area
    return float(best)


def score_size(n: int, ref: dict, construct_points) -> dict:
    try:
        raw = construct_points(n)
    except Exception as exc:  # noqa: BLE001
        return {"n": n, "valid": False, "reason": "raised: %s" % exc, "score": 0.0}
    try:
        pts = np.asarray([[float(c) for c in p] for p in raw], dtype=np.float64)
    except Exception as exc:  # noqa: BLE001
        return {"n": n, "valid": False, "reason": "not a list of (x, y) pairs: %s" % exc, "score": 0.0}
    if pts.shape != (n, 2):
        return {"n": n, "valid": False, "reason": "expected exactly %d (x, y) points" % n, "score": 0.0}
    if not np.all(np.isfinite(pts)):
        return {"n": n, "valid": False, "reason": "coordinates must be finite", "score": 0.0}
    if pts.min() < -COORD_ATOL or pts.max() > 1.0 + COORD_ATOL:
        return {"n": n, "valid": False, "reason": "all coordinates must lie in [0, 1]", "score": 0.0}
    pts = np.clip(pts, 0.0, 1.0)
    area = min_triangle_area(pts)
    base, sota = ref["baseline"], ref["sota_ref"]
    return {
        "n": n, "valid": True, "min_triangle_area": area, "sota_ref": sota,
        "score": _normalized(area, float(base), float(sota)),
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
