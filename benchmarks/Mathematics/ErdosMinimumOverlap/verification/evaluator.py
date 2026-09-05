"""Frozen oracle for ErdosMinimumOverlap (hidden from the agent).

Partition {1, ..., 2n} into two sets A, B of size n each. For every integer shift k, let
M_k be the number of pairs (a, b) with a in A, b in B and a - b = k. Erdos' minimum
overlap problem asks for M(n) := min over partitions of max_k M_k. The asymptotic constant
c = lim M(n)/n is the subject of ongoing research -- AlphaEvolve (2025), TTT-Discover
(2026) and SimpleTES (2026) have each nudged its published upper bound (arXiv:2506.13131;
see references/known_best.md). For n <= 15, M(n) itself has been determined exactly by
exhaustive search (see the "Minimum overlap problem" record table); this task uses three
of those proven exact values as its score = 1.0 witnesses. Because they are proven exact,
no valid partition can beat them -- this is disclosed rather than hidden.
"""
from __future__ import annotations

import numpy as np

# n -> (naive-baseline max-overlap, proven-exact M(n)). See references/known_best.md.
SIZES = {
    8: {"baseline": 8, "sota_ref": 4},
    11: {"baseline": 11, "sota_ref": 5},
    15: {"baseline": 15, "sota_ref": 6},
}


def max_overlap(labels: np.ndarray, n: int) -> int:
    """labels has length 2n; labels[i]==0 means value i+1 is in A, ==1 means in B.
    Returns max_k of the number of pairs (a in A, b in B) with a - b = k, computed by
    cross-correlating the two indicator arrays (exact integer arithmetic, no sampling)."""
    ia = (labels == 0).astype(np.int64)
    ib = (labels == 1).astype(np.int64)
    corr = np.correlate(ia, ib, mode="full")
    return int(corr.max())


def _normalized_overlap_score(value: float, baseline: float, sota: float) -> float:
    """0 at the baseline max-overlap, 1 at the proven-exact minimum, unbounded beyond it.

    Lower max-overlap is better here, the mirror image of this codebase's usual
    `_normalized` convention (higher value, baseline < sota) -- named differently on
    purpose, matching Mathematics/NarrowAdmissibleTuple's `_normalized_diameter_score`,
    so a generic cross-task check for `_normalized(value, baseline, sota)` with
    higher-is-better semantics does not mistake this inverted convention for that one."""
    denom = baseline - sota
    if denom <= 0:
        return 0.0
    return float(max(0.0, (baseline - value) / denom))


def score_size(n: int, ref: dict, construct_partition) -> dict:
    try:
        raw = construct_partition(n)
    except Exception as exc:  # noqa: BLE001
        return {"n": n, "valid": False, "reason": "raised: %s" % exc, "score": 0.0}
    try:
        labels = [int(x) for x in raw]
    except Exception as exc:  # noqa: BLE001
        return {"n": n, "valid": False, "reason": "not a list of ints: %s" % exc, "score": 0.0}
    if len(labels) != 2 * n:
        return {"n": n, "valid": False, "reason": "expected exactly 2*n=%d labels, got %d" % (2 * n, len(labels)), "score": 0.0}
    if any(v not in (0, 1) for v in labels):
        return {"n": n, "valid": False, "reason": "labels must be 0 (in A) or 1 (in B)", "score": 0.0}
    if sum(1 for v in labels if v == 0) != n or sum(1 for v in labels if v == 1) != n:
        return {"n": n, "valid": False, "reason": "A and B must each have exactly n elements", "score": 0.0}
    m = max_overlap(np.asarray(labels), n)
    base, sota = ref["baseline"], ref["sota_ref"]
    return {
        "n": n, "valid": True, "max_overlap": m, "sota_ref": sota,
        "score": _normalized_overlap_score(float(m), float(base), float(sota)),
    }


def evaluate(construct_partition) -> dict:
    per = [score_size(n, ref, construct_partition) for n, ref in SIZES.items()]
    scores = [r["score"] for r in per]
    n_valid = sum(1 for r in per if r.get("valid"))
    return {
        "combined_score": float(np.mean(scores)) if scores else 0.0,
        "valid": 1.0 if n_valid == len(SIZES) else 0.0,
        "feasibility_rate": n_valid / len(SIZES),
        "beat_sota": bool(any(r.get("score", 0.0) > 1.0 for r in per)),
        "per_size": per,
    }
