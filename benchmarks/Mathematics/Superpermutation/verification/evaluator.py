"""Frozen oracle for Superpermutation (hidden from the agent).

A string over {1..n} is a superpermutation when every n-permutation appears as a contiguous
substring. Lower length is better; the score is uncapped relative to the shortest published
string. Concatenating all n! permutations is always valid and is the floor.
"""
from __future__ import annotations

import itertools
from functools import lru_cache

import numpy as np

SIZES = {
    7: {"naive": 7 * 5040, "sota_ref": 5906},     # 35280 vs Egan/Houston 5906
    8: {"naive": 8 * 40320, "sota_ref": 46205},    # 322560 vs Egan 2018 (Williams construction), OEIS A180632
}
MAX_LEN = {7: 40000, 8: 400000}


def _normalized(value: float, baseline: float, sota: float) -> float:
    """0 at baseline, 1 at sota, >1 beyond. `value` is the higher-is-better quantity."""
    denom = sota - baseline
    if denom == 0:
        return 0.0
    return float(max(0.0, (value - baseline) / denom))


@lru_cache(maxsize=None)
def _all_perms(n: int) -> set[str]:
    alphabet = "".join(str(i) for i in range(1, n + 1))
    return {"".join(p) for p in itertools.permutations(alphabet)}


def verify_superpermutation(raw, n: int) -> tuple[bool, int, str]:
    if not isinstance(raw, str):
        return False, 0, "not a string"
    cap = MAX_LEN[n]
    if len(raw) > cap:
        return False, len(raw), f"length {len(raw)} exceeds checker cap {cap}"
    alphabet = set(str(i) for i in range(1, n + 1))
    if any(ch not in alphabet for ch in raw):
        return False, len(raw), "character outside 1..n"
    need = _all_perms(n)
    found: set[str] = set()
    for i in range(0, len(raw) - n + 1):
        w = raw[i:i + n]
        if w in need:
            found.add(w)
            if len(found) == len(need):
                break
    if found != need:
        return False, len(raw), f"missing {len(need) - len(found)} permutations"
    return True, len(raw), "ok"


def score_n(n: int, ref: dict, build_superpermutation) -> dict:
    try:
        raw = build_superpermutation(n)
    except Exception as exc:  # noqa: BLE001
        return {"n": n, "valid": False, "reason": f"raised: {exc}", "score": 0.0}
    ok, length, reason = verify_superpermutation(raw, n)
    if not ok:
        return {"n": n, "valid": False, "reason": reason, "length": length, "score": 0.0}
    naive, sota = ref["naive"], ref["sota_ref"]
    return {
        "n": n, "valid": True, "length": length, "sota_ref": sota,
        "score": _normalized(float(-length), float(-naive), float(-sota)),
    }


def evaluate(build_superpermutation) -> dict:
    per = [score_n(n, ref, build_superpermutation) for n, ref in SIZES.items()]
    scores = [r["score"] for r in per]
    n_valid = sum(1 for r in per if r.get("valid"))
    return {
        "combined_score": float(np.mean(scores)) if scores else 0.0,
        "valid": 1.0 if n_valid == len(SIZES) else 0.0,
        "feasibility_rate": n_valid / len(SIZES),
        "beat_sota": bool(any(r.get("score", 0.0) > 1.0 for r in per)),
        "per_n": per,
    }
