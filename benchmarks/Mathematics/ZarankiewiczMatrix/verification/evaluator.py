"""Frozen oracle for ZarankiewiczMatrix (hidden from the agent).

The Zarankiewicz number z(m,n;s,t) is the maximum number of 1-entries a 0/1 matrix with m rows
and n columns can have while containing no s x t all-ones submatrix -- i.e. no choice of s rows
and t columns (not necessarily contiguous) that are all 1 simultaneously. Equivalently: the
maximum number of edges a bipartite graph with parts of size m and n can have while containing no
complete bipartite subgraph K_{s,t}.

This is exactly the object arXiv:2605.01120 ("New Bounds for Zarankiewicz Numbers via Reinforced
LLM Evolutionary Search") and arXiv:2608.26603 ("Five improved lower bounds for Zarankiewicz
numbers z(m,n;3,3)") report new results for using OpenEvolve -- an LLM-guided evolutionary search
backend this repository natively supports (`--algorithm openevolve`). The score here is uncapped
relative to the most recent published lower bound: a valid submitted matrix with more 1-entries
than the cited record is a real, checkable, exact improvement on a problem still open today (these
are lower bounds without a matching upper-bound proof), not a benchmark artifact.
"""
from __future__ import annotations

import numpy as np

# (m, n, s, t) -> naive-baseline ones (see solution.py) and the most recent published lower-bound
# record. All s=t=3. See references/known_best.md for exactly which paper each record comes from.
SIZES = {
    "13x19": {"m": 13, "n": 19, "s": 3, "t": 3, "baseline": 26, "sota_ref": 118},
    "14x19": {"m": 14, "n": 19, "s": 3, "t": 3, "baseline": 28, "sota_ref": 126},
    "16x18": {"m": 16, "n": 18, "s": 3, "t": 3, "baseline": 32, "sota_ref": 136},
}
MAX_ONES_MULTIPLE = 5.0  # reject absurd submissions without doing the combinatorial check


def _has_forbidden_submatrix(rows: list[int], m: int, n: int, s: int, t: int) -> bool:
    """rows[i] is a bitmask (bit j set means matrix[i][j] == 1). True iff some s rows share t+
    common set columns, i.e. an s x t all-ones submatrix exists."""
    from itertools import combinations

    for combo in combinations(range(m), s):
        mask = rows[combo[0]]
        for idx in combo[1:]:
            mask &= rows[idx]
            if mask == 0:
                break
        if bin(mask).count("1") >= t:
            return True
    return False


def _normalized(value: float, baseline: float, sota: float) -> float:
    denom = sota - baseline
    if denom <= 0:
        return 0.0
    return float(max(0.0, (value - baseline) / denom))


def score_size(name: str, ref: dict, construct_matrix) -> dict:
    m, n, s, t = ref["m"], ref["n"], ref["s"], ref["t"]
    try:
        raw = construct_matrix(m, n, s, t)
    except Exception as exc:  # noqa: BLE001
        return {"size": name, "valid": False, "reason": "raised: %s" % exc, "score": 0.0}
    try:
        mat = [[int(x) for x in row] for row in raw]
    except Exception as exc:  # noqa: BLE001
        return {"size": name, "valid": False, "reason": "not a matrix of ints: %s" % exc, "score": 0.0}
    if len(mat) != m or any(len(row) != n for row in mat):
        return {"size": name, "valid": False, "reason": "expected shape %dx%d" % (m, n), "score": 0.0}
    if any(v not in (0, 1) for row in mat for v in row):
        return {"size": name, "valid": False, "reason": "entries must be 0 or 1", "score": 0.0}
    ones = sum(sum(row) for row in mat)
    if ones <= 0 or ones > MAX_ONES_MULTIPLE * ref["sota_ref"]:
        return {"size": name, "valid": False, "reason": "ones count out of accepted range", "score": 0.0}
    rowmasks = [int("".join(str(v) for v in row), 2) for row in mat]
    if _has_forbidden_submatrix(rowmasks, m, n, s, t):
        return {
            "size": name, "valid": False,
            "reason": "contains a %dx%d all-ones submatrix" % (s, t),
            "ones": ones, "score": 0.0,
        }
    base, sota = ref["baseline"], ref["sota_ref"]
    return {
        "size": name, "valid": True, "ones": ones, "sota_ref": sota,
        "score": _normalized(float(ones), float(base), float(sota)),
    }


def evaluate(construct_matrix) -> dict:
    per = [score_size(name, ref, construct_matrix) for name, ref in SIZES.items()]
    scores = [r["score"] for r in per]
    n_valid = sum(1 for r in per if r.get("valid"))
    return {
        "combined_score": float(np.mean(scores)) if scores else 0.0,
        "valid": 1.0 if n_valid == len(SIZES) else 0.0,
        "feasibility_rate": n_valid / len(SIZES),
        "beat_sota": bool(any(r.get("score", 0.0) > 1.0 for r in per)),
        "per_size": per,
    }
