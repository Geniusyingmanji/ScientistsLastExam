"""Frozen oracle for TensorRank555 (hidden from the agent).

Fixed-tolerance numerical tensor reconstruction on new sizes only: <5,5,5> and <6,6,6>.
Lower R is better; the score is uncapped relative to the best published exact R, which is
used only as a contextual score anchor and is not certified by this numerical verifier.
"""
from __future__ import annotations

import numpy as np

SIZES = [
    {"mnp": (5, 5, 5), "naive": 125, "sota_ref": 93, "note": "Moosbauer-Poole ISSAC 2025"},
    {"mnp": (6, 6, 6), "naive": 216, "sota_ref": 153, "note": "Moosbauer-Poole ISSAC 2025"},
]
TOL = 1e-7


def _normalized(value: float, baseline: float, sota: float) -> float:
    """0 at baseline, 1 at sota, >1 beyond. `value` is the higher-is-better quantity."""
    denom = sota - baseline
    if denom == 0:
        return 0.0
    return float(max(0.0, (value - baseline) / denom))


def matmul_tensor(m: int, n: int, p: int) -> np.ndarray:
    M = np.zeros((m * n, n * p, m * p))
    for i in range(m):
        for c in range(n):
            for j in range(p):
                M[i * n + c, c * p + j, i * p + j] = 1.0
    return M


def verify_decomposition(U, V, W, m, n, p) -> tuple[bool, int, str]:
    try:
        U = np.asarray(U, dtype=complex)
        V = np.asarray(V, dtype=complex)
        W = np.asarray(W, dtype=complex)
    except Exception as exc:  # noqa: BLE001
        return False, 0, f"non-array: {exc}"
    if U.ndim != 2 or V.ndim != 2 or W.ndim != 2:
        return False, 0, "U,V,W must be 2D"
    R = U.shape[0]
    if U.shape != (R, m * n) or V.shape != (R, n * p) or W.shape != (m * p, R):
        return False, R, f"bad shapes for R={R}"
    if not (np.all(np.isfinite(U)) and np.all(np.isfinite(V)) and np.all(np.isfinite(W))):
        return False, R, "non-finite coefficient"
    recon = np.einsum("ri,rj,kr->ijk", U, V, W)
    if not np.all(np.isfinite(recon)):
        return False, R, "non-finite reconstruction"
    residual = np.abs(recon - matmul_tensor(m, n, p))
    if not np.all(np.isfinite(residual)):
        return False, R, "non-finite reconstruction residual"
    err = float(np.max(residual))
    if err >= TOL:
        return False, R, f"outside numerical tolerance (err={err:.2e})"
    rng = np.random.default_rng(0)
    for _ in range(3):
        A = rng.integers(-4, 5, (m, n)).astype(complex)
        B = rng.integers(-4, 5, (n, p)).astype(complex)
        prods = (U @ A.reshape(-1)) * (V @ B.reshape(-1))
        C = (W @ prods).reshape(m, p)
        if not np.all(np.isfinite(prods)) or not np.all(np.isfinite(C)):
            return False, R, "non-finite functional output"
        if not np.allclose(C, A @ B, atol=1e-6):
            return False, R, "functional mismatch"
    return True, R, "ok"


def score_size(entry: dict, build_algorithm) -> dict:
    m, n, p = entry["mnp"]
    naive, sota = entry["naive"], entry["sota_ref"]
    try:
        packed = build_algorithm(m, n, p)
        U, V, W = packed
    except Exception as exc:  # noqa: BLE001
        return {"mnp": entry["mnp"], "valid": False, "reason": f"raised: {exc}", "score": 0.0}
    ok, R, reason = verify_decomposition(U, V, W, m, n, p)
    if not ok:
        return {"mnp": entry["mnp"], "valid": False, "reason": reason, "R": R, "score": 0.0}
    return {
        "mnp": entry["mnp"], "valid": True, "R": R, "sota_ref": sota,
        "score": _normalized(float(-R), float(-naive), float(-sota)),
    }


def evaluate(build_algorithm) -> dict:
    per = [score_size(e, build_algorithm) for e in SIZES]
    scores = [r["score"] for r in per]
    n_valid = sum(1 for r in per if r.get("valid"))
    return {
        "combined_score": float(np.mean(scores)) if scores else 0.0,
        "valid": 1.0 if n_valid == len(SIZES) else 0.0,
        "feasibility_rate": n_valid / len(SIZES),
        "beat_sota": bool(any(r.get("score", 0.0) > 1.0 for r in per)),
        "per_size": per,
    }
