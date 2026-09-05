"""Frozen oracle for SchurPartition (hidden from the agent).

The Schur number S(k) is the largest n such that {1,...,n} can be partitioned into k sum-free
sets -- sets containing no a, b, c (a, b, c need not be distinct, so a=b is allowed) with
a + b = c. Only S(1) through S(5) are known exactly (S(5)=160 was the last, settled in 2017 by a
SAT-solver proof, "Schur Number Five"); S(6) and S(7) are known only as best-known lower bounds,
kept current by dedicated search. The score here is uncapped relative to the published witness: a
valid submitted partition longer than the cited witness length would be a real, checkable new
result on a problem still open today (for k=6, k=7) or would contradict a proven theorem (for
k=4) -- this task uses one proven-exact size and two genuinely open lower-bound sizes, and
discloses which is which (see references/known_best.md).
"""
from __future__ import annotations

import numpy as np

# k -> (naive-baseline witness length, published witness length). k=4 is a proven exact S(4);
# k=6 and k=7 are best-known lower bounds (not proven exact). See references/known_best.md.
SIZES = {
    4: {"baseline": 15, "sota_ref": 44},
    6: {"baseline": 63, "sota_ref": 536},
    7: {"baseline": 127, "sota_ref": 1696},
}
MAX_N_MULTIPLE = 3.0  # reject absurd submissions without doing the expensive sum-free sweep


def _normalized(value: float, baseline: float, sota: float) -> float:
    denom = sota - baseline
    if denom <= 0:
        return 0.0
    return float(max(0.0, (value - baseline) / denom))


def _is_sum_free(members: np.ndarray, n: int) -> bool:
    """True iff no a, b, c in `members` (1-indexed values, a=b allowed) satisfy a + b = c.
    Checked via convolution: mask[i] is True iff value i+1 is in the part; convolving mask with
    itself gives, at index i+j, the number of (a,b) pairs (1-indexed a=i+1, b=j+1) with a+b =
    i+j+2; a nonzero count at an index whose corresponding sum value is itself in the part is a
    violation."""
    if members.size == 0:
        return True
    mask = np.zeros(n + 1, dtype=bool)
    mask[members] = True
    conv = np.convolve(mask[1:].astype(np.int64), mask[1:].astype(np.int64))
    # conv[i] = count of (a,b), a=ia+1, b=ib+1, ia+ib=i -> a+b = i+2
    sums_hit = np.nonzero(conv > 0)[0] + 2
    sums_hit = sums_hit[sums_hit <= n]
    return not mask[sums_hit].any()


def score_size(k: int, ref: dict, construct_partition) -> dict:
    try:
        raw = construct_partition(k)
    except Exception as exc:  # noqa: BLE001
        return {"k": k, "valid": False, "reason": "raised: %s" % exc, "score": 0.0}
    try:
        parts = [int(x) for x in raw]
    except Exception as exc:  # noqa: BLE001
        return {"k": k, "valid": False, "reason": "not a list of ints: %s" % exc, "score": 0.0}
    n = len(parts)
    if n <= 0 or n > MAX_N_MULTIPLE * ref["sota_ref"]:
        return {"k": k, "valid": False, "reason": "length out of accepted range", "score": 0.0}
    if any(p < 0 or p >= k for p in parts):
        return {"k": k, "valid": False, "reason": "part index must be in 0..%d" % (k - 1), "score": 0.0}
    arr = np.asarray(parts, dtype=np.int64)
    for p in range(k):
        members = np.nonzero(arr == p)[0] + 1  # 1-indexed element values
        if not _is_sum_free(members, n):
            return {
                "k": k, "valid": False,
                "reason": "part %d is not sum-free (a + b = c within the part)" % p,
                "n": n, "score": 0.0,
            }
    base, sota = ref["baseline"], ref["sota_ref"]
    return {
        "k": k, "valid": True, "n": n, "sota_ref": sota,
        "score": _normalized(float(n), float(base), float(sota)),
    }


def evaluate(construct_partition) -> dict:
    per = [score_size(k, ref, construct_partition) for k, ref in SIZES.items()]
    scores = [r["score"] for r in per]
    n_valid = sum(1 for r in per if r.get("valid"))
    return {
        "combined_score": float(np.mean(scores)) if scores else 0.0,
        "valid": 1.0 if n_valid == len(SIZES) else 0.0,
        "feasibility_rate": n_valid / len(SIZES),
        "beat_sota": bool(any(r.get("score", 0.0) > 1.0 for r in per)),
        "per_size": per,
    }
