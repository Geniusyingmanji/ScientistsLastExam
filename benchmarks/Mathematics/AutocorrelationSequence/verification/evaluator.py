"""Frozen oracle for AutocorrelationSequence (hidden from the agent).

The (unsigned) autocorrelation constant C = inf_f max_t (f*f)(t) / (integral f)^2, over
non-negative functions f supported on [-1/4, 1/4]; the signed variant C' drops the
non-negativity requirement. Discretizing f into N equal-width step heights a_0..a_{N-1}
turns this into a finite, exactly-checkable object: the discrete ratio is
2*N*max(convolve(a,a)) / (sum(a))^2 (a Riemann-sum approximation of the continuous
definition). Current published upper bounds: C <= 1.5028503020710076 (a fixed benchmark
certificate) and C' <= 1.4545548626983325 (Together AI, 2026, superseding a 2010 bound of
1.4581) -- both real, currently-open records with genuine headroom above them.
"""
from __future__ import annotations

import numpy as np

# kind -> (min N required, allow negative values, naive-baseline ratio, published upper bound)
SIZES = {
    "unsigned": {"nonneg": True, "min_n": 100, "baseline": 2.0, "sota_ref": 1.5028503020710076},
    "signed": {"nonneg": False, "min_n": 10, "baseline": 2.0, "sota_ref": 1.4545548626983325},
}


def _normalized_ratio_score(value: float, baseline: float, sota: float) -> float:
    """0 at baseline, 1 at the published bound, unbounded beyond it. Smaller ratio is better
    here, the mirror image of this codebase's usual `_normalized` convention."""
    denom = baseline - sota
    if denom <= 0:
        return 0.0
    return float(max(0.0, (baseline - value) / denom))


def autoconvolution_ratio(values: np.ndarray) -> float:
    n = len(values)
    conv = np.convolve(values, values)
    total = values.sum()
    return float(2 * n * conv.max() / (total ** 2))


def score_size(kind: str, ref: dict, construct_sequence) -> dict:
    try:
        raw = construct_sequence(kind == "signed")
    except Exception as exc:  # noqa: BLE001
        return {"kind": kind, "valid": False, "reason": "raised: %s" % exc, "score": 0.0}
    if isinstance(raw, dict):
        raw = raw.get("values")
    try:
        values = np.asarray([float(x) for x in raw], dtype=np.float64)
    except Exception as exc:  # noqa: BLE001
        return {"kind": kind, "valid": False, "reason": "not a list of floats: %s" % exc, "score": 0.0}
    n = len(values)
    if n < ref["min_n"]:
        return {"kind": kind, "valid": False, "reason": "at least %d intervals required" % ref["min_n"], "score": 0.0}
    if not np.all(np.isfinite(values)):
        return {"kind": kind, "valid": False, "reason": "values must be finite", "score": 0.0}
    if ref["nonneg"] and np.any(values < 0):
        return {"kind": kind, "valid": False, "reason": "values must be non-negative for the unsigned constant", "score": 0.0}
    if values.sum() == 0:
        return {"kind": kind, "valid": False, "reason": "sum of values must be nonzero", "score": 0.0}
    ratio = autoconvolution_ratio(values)
    base, sota = ref["baseline"], ref["sota_ref"]
    return {
        "kind": kind, "valid": True, "n": n, "ratio": ratio, "sota_ref": sota,
        "score": _normalized_ratio_score(ratio, float(base), float(sota)),
    }


def evaluate(construct_sequence) -> dict:
    per = [score_size(kind, ref, construct_sequence) for kind, ref in SIZES.items()]
    scores = [r["score"] for r in per]
    n_valid = sum(1 for r in per if r.get("valid"))
    return {
        "combined_score": float(np.mean(scores)) if scores else 0.0,
        "valid": 1.0 if n_valid == len(SIZES) else 0.0,
        "feasibility_rate": n_valid / len(SIZES),
        "beat_sota": bool(any(r.get("score", 0.0) > 1.0 for r in per)),
        "per_size": per,
    }
