"""Frozen oracle for DifferenceBasisRatio (hidden from the agent).

For a natural number n, let Delta(n) be the size of the smallest set B of integers such
that every k in {1,...,n} is expressible as |a-b| for some a, b in B ("a difference basis
for {1,...,n}"). Define C(n) := Delta(n)^2 / n and C := inf_{n>=1} C(n). This constant's
published upper bound has been pushed down repeatedly in 2025-2026 -- 2.6571 -> 2.6390 by
AlphaEvolve (arXiv:2511.02864) -- each improvement a genuine, explicit difference basis at
some n, not merely an existence argument. This task asks for exactly that object: a
difference basis for a self-chosen n, scored by how close its ratio |B|^2/n comes to (or
beats) the published bound.

Three "hint" sizes are used only to seed a reasonable search scale; a candidate may return
any n and any valid basis for it, and is scored on the ratio it actually achieves.
"""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np

SOTA_RATIO = 2.6390  # published upper bound on C = inf_n Delta(n)^2/n (AlphaEvolve, 2025)
MAX_SPAN_MULTIPLE = 5.0  # basis span (max-min) may not exceed this multiple of n

# hint n -> naive-baseline ratio (see solution.py), all scored against the same global
# constant SOTA_RATIO since it is defined as an infimum over every n.
SIZES = {
    500: {"baseline": 12.168},
    2000: {"baseline": 12.168},
    10000: {"baseline": 12.3201},
}


def _normalized_ratio_score(value: float, baseline: float, sota: float) -> float:
    """0 at the baseline ratio, 1 at the published bound, unbounded beyond it. Smaller ratio
    is better here, the mirror image of this codebase's usual `_normalized` convention --
    named differently on purpose, matching Mathematics/NarrowAdmissibleTuple's
    `_normalized_diameter_score`."""
    denom = baseline - sota
    if denom <= 0:
        return 0.0
    return float(max(0.0, (baseline - value) / denom))


def covers_all_differences(basis: list[int], n: int) -> bool:
    lo, hi = min(basis), max(basis)
    span = hi - lo
    mask = np.zeros(span + 1, dtype=np.int64)
    mask[[x - lo for x in basis]] = 1
    conv = np.convolve(mask, mask[::-1])
    # conv[span + d] counts pairs (a, b) in basis with a - b = d
    window = conv[span + 1: span + n + 1]
    if len(window) < n:
        return False
    return bool(np.all(window > 0))


def score_size(hint_n: int, ref: dict, construct_basis) -> dict:
    try:
        raw = construct_basis(hint_n)
    except Exception as exc:  # noqa: BLE001
        return {"hint_n": hint_n, "valid": False, "reason": "raised: %s" % exc, "score": 0.0}
    if isinstance(raw, Mapping):
        n_val = raw.get("n", hint_n)
        basis_raw = raw.get("basis")
    else:
        n_val, basis_raw = hint_n, raw
    try:
        n = int(n_val)
        basis = [int(x) for x in basis_raw]
    except Exception as exc:  # noqa: BLE001
        return {"hint_n": hint_n, "valid": False, "reason": "not an (n, basis) result: %s" % exc, "score": 0.0}
    if n <= 0:
        return {"hint_n": hint_n, "valid": False, "reason": "n must be positive", "score": 0.0}
    if len(basis) != len(set(basis)):
        return {"hint_n": hint_n, "valid": False, "reason": "basis entries must be distinct", "score": 0.0}
    if len(basis) < 2:
        return {"hint_n": hint_n, "valid": False, "reason": "basis needs at least 2 elements", "score": 0.0}
    if max(basis) - min(basis) > MAX_SPAN_MULTIPLE * n:
        return {"hint_n": hint_n, "valid": False, "reason": "basis span too large relative to n", "score": 0.0}
    if not covers_all_differences(basis, n):
        return {"hint_n": hint_n, "valid": False, "reason": "does not cover every difference 1..n", "score": 0.0}
    ratio = (len(basis) ** 2) / n
    base = ref["baseline"]
    return {
        "hint_n": hint_n, "valid": True, "n": n, "basis_size": len(basis), "ratio": ratio,
        "sota_ref": SOTA_RATIO,
        "score": _normalized_ratio_score(ratio, float(base), SOTA_RATIO),
    }


def evaluate(construct_basis) -> dict:
    per = [score_size(hint_n, ref, construct_basis) for hint_n, ref in SIZES.items()]
    scores = [r["score"] for r in per]
    n_valid = sum(1 for r in per if r.get("valid"))
    return {
        "combined_score": float(np.mean(scores)) if scores else 0.0,
        "valid": 1.0 if n_valid == len(SIZES) else 0.0,
        "feasibility_rate": n_valid / len(SIZES),
        "beat_sota": bool(any(r.get("score", 0.0) > 1.0 for r in per)),
        "per_size": per,
    }
