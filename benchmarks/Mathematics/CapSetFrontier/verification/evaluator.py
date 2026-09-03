"""Frozen oracle for CapSetFrontier (hidden from the agent).

Same cap-set verifier as Mathematics/CapSet, on the still-open dimensions 7, 8 and 9.
Larger is better; the score is uncapped relative to the best known size. The {0,1}^n
hypercube is always a valid cap of size 2^n and is the floor.
"""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np

SIZES = {
    7: {"baseline": 128, "sota_ref": 236},
    8: {"baseline": 256, "sota_ref": 512},
    9: {"baseline": 512, "sota_ref": 1082},
}
MAX_SIZE = 2500


def _normalized(value: float, baseline: float, sota: float) -> float:
    """0 at baseline, 1 at sota, >1 beyond. `value` is the higher-is-better quantity."""
    denom = sota - baseline
    if denom == 0:
        return 0.0
    return float(max(0.0, (value - baseline) / denom))


def verify_cap(vecs, n: int) -> tuple[bool, int, str]:
    if vecs is None or isinstance(vecs, (str, bytes, Mapping)):
        return False, 0, "expected a non-empty sequence of vectors"
    try:
        rows = list(vecs)
    except Exception as exc:  # noqa: BLE001
        return False, 0, f"not a sequence of vectors: {exc}"
    if not rows:
        return False, 0, "expected a non-empty sequence of vectors"
    S = set()
    for v in rows:
        try:
            coords = tuple(x for x in v)
            t = tuple(int(x) for x in coords)
        except Exception as exc:  # noqa: BLE001
            return False, 0, f"bad vector: {exc}"
        if len(t) != n:
            return False, 0, f"vector length != {n}"
        if any(int(x) != x or int(x) not in (0, 1, 2) for x in coords):
            return False, 0, "entries must be in {0,1,2}"
        S.add(t)
    if len(S) > MAX_SIZE:
        return False, len(S), f"more than {MAX_SIZE} points"
    arr = list(S)
    Sset = set(arr)
    for a in range(len(arr)):
        xa = arr[a]
        for b in range(a + 1, len(arr)):
            yb = arr[b]
            z = tuple((-(xa[i] + yb[i])) % 3 for i in range(n))
            if z in Sset and z != xa and z != yb:
                return False, len(S), "collinear triple found"
    return True, len(S), "ok"


def score_dim(n: int, ref: dict, build_capset) -> dict:
    try:
        vecs = build_capset(n)
    except Exception as exc:  # noqa: BLE001
        return {"n": n, "valid": False, "reason": f"raised: {exc}", "score": 0.0}
    ok, size, reason = verify_cap(vecs, n)
    if not ok:
        return {"n": n, "valid": False, "reason": reason, "size": size, "score": 0.0}
    base, sota = ref["baseline"], ref["sota_ref"]
    return {
        "n": n, "valid": True, "size": size, "sota_ref": sota,
        "score": _normalized(float(size), float(base), float(sota)),
    }


def evaluate(build_capset) -> dict:
    per = [score_dim(n, ref, build_capset) for n, ref in SIZES.items()]
    scores = [r["score"] for r in per]
    n_valid = sum(1 for r in per if r.get("valid"))
    return {
        "combined_score": float(np.mean(scores)) if scores else 0.0,
        "valid": 1.0 if n_valid == len(SIZES) else 0.0,
        "feasibility_rate": n_valid / len(SIZES),
        "beat_sota": bool(any(r.get("score", 0.0) > 1.0 for r in per)),
        "per_dim": per,
    }
