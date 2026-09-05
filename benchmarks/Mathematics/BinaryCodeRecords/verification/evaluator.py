"""Frozen oracle for BinaryCodeRecords (hidden from the agent).

Two classical binary error-correcting-code records, each scored by its own kind:

- "linear_68_15": the largest minimum distance of a binary LINEAR [68,15] code (a 15x68
  generator matrix over GF(2)). Minimum distance of a linear code equals the minimum
  Hamming weight among its 2^15 - 1 nonzero codewords -- exhaustively enumerable and
  exact. Best-known lower bound 24 (codetables.de, Grassl), upper bound 26.
- "general_21_10": the largest binary (possibly non-linear) code of length 21 with
  minimum pairwise Hamming distance >= 10, A(21,10) -- an explicit list of codewords,
  checked pairwise. Best-known lower bound 42 (Kaikkonen, 1989), upper bound 47.

Both are lower bounds without a matching upper-bound proof, so real headroom exists.
"""
from __future__ import annotations

import numpy as np

SIZES = {
    "linear_68_15": {"k": 15, "n": 68, "baseline": 1, "sota_ref": 24},
    "general_21_10": {"n": 21, "d": 10, "baseline": 2, "sota_ref": 42},
}


def _normalized(value: float, baseline: float, sota: float) -> float:
    """0 at baseline, 1 at sota, >1 beyond. `value` is the higher-is-better quantity."""
    denom = sota - baseline
    if denom <= 0:
        return 0.0
    return float(max(0.0, (value - baseline) / denom))


def _min_distance_linear(raw, k: int, n: int) -> tuple[bool, int, str]:
    try:
        g = np.asarray([[int(x) for x in row] for row in raw], dtype=np.uint8)
    except Exception as exc:  # noqa: BLE001
        return False, 0, "not a %dx%d 0/1 matrix: %s" % (k, n, exc)
    if g.shape != (k, n):
        return False, 0, "expected a %dx%d generator matrix" % (k, n)
    if not np.all((g == 0) | (g == 1)):
        return False, 0, "entries must be 0 or 1"
    num = 1 << k
    idx = np.arange(num, dtype=np.uint32)
    bits = ((idx[:, None] >> np.arange(k)[None, :]) & 1).astype(np.uint8)
    codewords = (bits @ g) % 2
    weights = codewords.sum(axis=1)
    weights[0] = n + 1  # exclude the all-zero message
    return True, int(weights.min()), "ok"


def _min_pairwise_distance(raw, n: int, d: int) -> tuple[bool, int, str]:
    try:
        words = [[int(x) for x in row] for row in raw]
    except Exception as exc:  # noqa: BLE001
        return False, 0, "not a list of 0/1 codewords: %s" % exc
    if not words:
        return False, 0, "expected at least one codeword"
    for w in words:
        if len(w) != n:
            return False, 0, "each codeword must have length %d" % n
        if any(b not in (0, 1) for b in w):
            return False, 0, "codeword entries must be 0 or 1"
    arr = np.asarray(words, dtype=np.uint8)
    if len(set(map(tuple, words))) != len(words):
        return False, 0, "duplicate codewords"
    m = len(words)
    for i in range(m):
        for j in range(i + 1, m):
            dist = int(np.count_nonzero(arr[i] != arr[j]))
            if dist < d:
                return False, m, "codewords %d and %d are only %d apart (need >= %d)" % (i, j, dist, d)
    return True, m, "ok"


def score_size(kind: str, ref: dict, construct_code) -> dict:
    try:
        raw = construct_code(kind)
    except Exception as exc:  # noqa: BLE001
        return {"kind": kind, "valid": False, "reason": "raised: %s" % exc, "score": 0.0}
    if kind == "linear_68_15":
        ok, size, reason = _min_distance_linear(raw, ref["k"], ref["n"])
    else:
        ok, size, reason = _min_pairwise_distance(raw, ref["n"], ref["d"])
    if not ok:
        return {"kind": kind, "valid": False, "reason": reason, "score": 0.0}
    base, sota = ref["baseline"], ref["sota_ref"]
    return {
        "kind": kind, "valid": True, "size": size, "sota_ref": sota,
        "score": _normalized(float(size), float(base), float(sota)),
    }


def evaluate(construct_code) -> dict:
    per = [score_size(kind, ref, construct_code) for kind, ref in SIZES.items()]
    scores = [r["score"] for r in per]
    n_valid = sum(1 for r in per if r.get("valid"))
    return {
        "combined_score": float(np.mean(scores)) if scores else 0.0,
        "valid": 1.0 if n_valid == len(SIZES) else 0.0,
        "feasibility_rate": n_valid / len(SIZES),
        "beat_sota": bool(any(r.get("score", 0.0) > 1.0 for r in per)),
        "per_size": per,
    }
