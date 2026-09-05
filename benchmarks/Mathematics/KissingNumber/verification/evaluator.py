"""Frozen oracle for KissingNumber (hidden from the agent).

A finite set of nonzero vectors is a valid kissing configuration when the corresponding
unit vectors have pairwise inner product at most 1/2. Integer vectors are checked with
exact integer arithmetic. The score is uncapped relative to the Cohn-table lower bound.
The 2d coordinate axes ±e_i are always valid and are the floor.
"""
from __future__ import annotations

from collections.abc import Mapping
import math

import numpy as np

# dim d -> (baseline 2d, Cohn-table lower bound). Dimension 11 is omitted on purpose (see
# references/known_best.md: recent AI-search claims there are contested).
SIZES = {
    5: {"baseline": 10, "sota_ref": 40},
    6: {"baseline": 12, "sota_ref": 72},
    9: {"baseline": 18, "sota_ref": 306},
    10: {"baseline": 20, "sota_ref": 510},
    12: {"baseline": 24, "sota_ref": 841},
}
MAX_VECTORS = 2500
FLOAT_ATOL = 1e-9


def _normalized(value: float, baseline: float, sota: float) -> float:
    """0 at baseline, 1 at sota, >1 beyond. `value` is the higher-is-better quantity."""
    denom = sota - baseline
    if denom == 0:
        return 0.0
    return float(max(0.0, (value - baseline) / denom))


def _is_integral_vector(v) -> bool:
    return all(abs(x - round(x)) <= 1e-12 for x in v)


def _primitive_int(v: tuple[int, ...]) -> tuple[int, ...]:
    """Divide by gcd so x and 2x are the same ray; keep signs so antipodes stay distinct."""
    g = 0
    for x in v:
        g = math.gcd(g, abs(x))
    if g > 1:
        return tuple(x // g for x in v)
    return v


def verify_kissing(raw, d: int) -> tuple[bool, int, str]:
    if raw is None or isinstance(raw, (str, bytes, Mapping)):
        return False, 0, "expected a non-empty sequence of vectors"
    try:
        rows = list(raw)
    except Exception as exc:  # noqa: BLE001
        return False, 0, f"not a sequence of vectors: {exc}"
    if not rows:
        return False, 0, "expected a non-empty sequence of vectors"
    if len(rows) > MAX_VECTORS:
        return False, 0, f"more than {MAX_VECTORS} vectors"
    cleaned = []
    for item in rows:
        try:
            vec = tuple(float(x) for x in item)
        except Exception as exc:  # noqa: BLE001
            return False, 0, f"bad vector: {exc}"
        if len(vec) != d:
            return False, 0, f"vector length != {d}"
        if not all(np.isfinite(x) for x in vec):
            return False, 0, "non-finite coordinate"
        if all(x == 0.0 for x in vec):
            return False, 0, "zero vector"
        cleaned.append(vec)
    integral = bool(cleaned) and all(_is_integral_vector(v) for v in cleaned)
    if integral:
        rounded = [tuple(int(round(x)) for x in v) for v in cleaned]
        if any(all(x == 0 for x in v) for v in rounded):
            return False, 0, "vector rounds to zero"
        unique = list(dict.fromkeys(_primitive_int(v) for v in rounded))
        ints = unique
    else:
        unique = list(dict.fromkeys(cleaned))
        ints = None
        if any(sum(x * x for x in v) < 1e-24 for v in unique):
            return False, 0, "near-zero vector"
    n = len(unique)
    for i in range(n):
        xi = ints[i] if ints is not None else unique[i]
        n1 = sum(x * x for x in xi)
        for j in range(i + 1, n):
            xj = ints[j] if ints is not None else unique[j]
            dot = sum(a * b for a, b in zip(xi, xj))
            n2 = sum(x * x for x in xj)
            if ints is not None:
                if dot > 0 and 4 * dot * dot > n1 * n2:
                    return False, n, "pair closer than 60 degrees"
            else:
                if not all(math.isfinite(value) for value in (dot, n1, n2)):
                    return False, n, "non-finite norm or inner product"
                prod = math.sqrt(n1) * math.sqrt(n2)
                cosine = dot / prod
                if (
                    not math.isfinite(prod)
                    or prod <= 0.0
                    or not math.isfinite(cosine)
                    or cosine > 0.5 + FLOAT_ATOL
                ):
                    return False, n, "pair closer than 60 degrees"
    return True, n, "ok"


def score_dim(d: int, ref: dict, build_kissing) -> dict:
    try:
        raw = build_kissing(d)
    except Exception as exc:  # noqa: BLE001
        return {"d": d, "valid": False, "reason": f"raised: {exc}", "score": 0.0}
    ok, size, reason = verify_kissing(raw, d)
    if not ok:
        return {"d": d, "valid": False, "reason": reason, "size": size, "score": 0.0}
    base, sota = ref["baseline"], ref["sota_ref"]
    return {
        "d": d, "valid": True, "size": size, "sota_ref": sota,
        "score": _normalized(float(size), float(base), float(sota)),
    }


def evaluate(build_kissing) -> dict:
    per = [score_dim(d, ref, build_kissing) for d, ref in SIZES.items()]
    scores = [r["score"] for r in per]
    n_valid = sum(1 for r in per if r.get("valid"))
    return {
        "combined_score": float(np.mean(scores)) if scores else 0.0,
        "valid": 1.0 if n_valid == len(SIZES) else 0.0,
        "feasibility_rate": n_valid / len(SIZES),
        "beat_sota": bool(any(r.get("score", 0.0) > 1.0 for r in per)),
        "per_dim": per,
    }
