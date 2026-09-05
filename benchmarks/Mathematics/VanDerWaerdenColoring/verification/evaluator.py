"""Frozen oracle for VanDerWaerdenColoring (hidden from the agent).

Van der Waerden's theorem: for any number of colors r and AP length k, there is a smallest n --
the van der Waerden number W(r,k) -- such that every r-coloring of {1,...,n} contains a
monochromatic k-term arithmetic progression. Equivalently: a valid r-coloring of {1,...,n} that
avoids every monochromatic k-term AP can exist only for n < W(r,k), and W(r,k) - 1 is the longest
such coloring's length. Only 9 exact van der Waerden numbers have ever been determined; the rest
are known only as best-known lower bounds, kept current by SAT-solver search. The score here is
uncapped relative to the published exact value: a valid submitted coloring longer than the cited
witness length would mean W(r,k) is larger than currently known -- a real, checkable result, not a
benchmark artifact, since the oracle checks the literal submitted coloring for every arithmetic
progression of the given length directly.
"""
from __future__ import annotations

import numpy as np

# name -> (num_colors r, ap_length k, naive-baseline witness length, published witness length).
# k4r2 and k5r2 use W(2,k)-1 for an exact, primary-sourced W(2,k) (no valid coloring can be
# longer, since W itself is a proven ceiling); k7r2 uses the best-known *lower-bound* witness
# length directly (a real, not-yet-proven-optimal construction, leaving genuine headroom above
# 1.0). See references/known_best.md for the exact citations and this distinction.
SIZES = {
    "k4r2": {"r": 2, "k": 4, "baseline": 6, "sota_ref": 34},
    "k5r2": {"r": 2, "k": 5, "baseline": 8, "sota_ref": 177},
    "k7r2": {"r": 2, "k": 7, "baseline": 12, "sota_ref": 3703},
}
MAX_N_MULTIPLE = 3.0  # reject absurd submissions without doing the expensive AP sweep


def _normalized(value: float, baseline: float, sota: float) -> float:
    denom = sota - baseline
    if denom <= 0:
        return 0.0
    return float(max(0.0, (value - baseline) / denom))


def has_monochromatic_ap(colors: np.ndarray, k: int) -> bool:
    """True iff some k-term arithmetic progression in `colors` (0-indexed positions) is
    monochromatic. Checked by, for each common difference d, comparing the k shifted views of the
    array elementwise -- vectorized, not a per-position Python loop."""
    n = len(colors)
    if k <= 1 or n < k:
        return False
    max_d = (n - 1) // (k - 1)
    for d in range(1, max_d + 1):
        length = n - d * (k - 1)
        if length <= 0:
            break
        base = colors[0:length]
        match = np.ones(length, dtype=bool)
        for j in range(1, k):
            match &= (colors[j * d: j * d + length] == base)
            if not match.any():
                break
        if match.any():
            return True
    return False


def score_size(name: str, ref: dict, construct_coloring) -> dict:
    r, k = ref["r"], ref["k"]
    try:
        raw = construct_coloring(r, k)
    except Exception as exc:  # noqa: BLE001
        return {"size": name, "valid": False, "reason": "raised: %s" % exc, "score": 0.0}
    try:
        colors = np.array([int(x) for x in raw], dtype=np.int64)
    except Exception as exc:  # noqa: BLE001
        return {"size": name, "valid": False, "reason": "not a list of ints: %s" % exc, "score": 0.0}
    n = len(colors)
    if n <= 0 or n > MAX_N_MULTIPLE * ref["sota_ref"]:
        return {"size": name, "valid": False, "reason": "length out of accepted range", "score": 0.0}
    if colors.min(initial=0) < 0 or colors.max(initial=0) >= r:
        return {"size": name, "valid": False, "reason": "colors must be in 0..%d" % (r - 1), "score": 0.0}
    if has_monochromatic_ap(colors, k):
        return {
            "size": name, "valid": False,
            "reason": "contains a monochromatic %d-term arithmetic progression" % k,
            "n": int(n), "score": 0.0,
        }
    base, sota = ref["baseline"], ref["sota_ref"]
    return {
        "size": name, "valid": True, "n": int(n), "sota_ref": sota,
        "score": _normalized(float(n), float(base), float(sota)),
    }


def evaluate(construct_coloring) -> dict:
    per = [score_size(name, ref, construct_coloring) for name, ref in SIZES.items()]
    scores = [r["score"] for r in per]
    n_valid = sum(1 for r in per if r.get("valid"))
    return {
        "combined_score": float(np.mean(scores)) if scores else 0.0,
        "valid": 1.0 if n_valid == len(SIZES) else 0.0,
        "feasibility_rate": n_valid / len(SIZES),
        "beat_sota": bool(any(r.get("score", 0.0) > 1.0 for r in per)),
        "per_size": per,
    }
