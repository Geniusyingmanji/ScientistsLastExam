"""Frozen oracle for MatrixMultiplicationRank (hidden from the agent).

A bilinear algorithm for multiplying an (m,n) by an (n,p) matrix is a rank-R decomposition
(U, V, W) of the matmul tensor: the algorithm forms R scalar products
    P_r = (sum_i U[r,i] a_i) * (sum_j V[r,j] b_j),
then C_k = sum_r W[k,r] P_r, where a = vec(A), b = vec(B), c = vec(C). R is the number of
scalar multiplications. The oracle verifies exactness against the true matmul tensor (so a
near-miss decomposition is rejected) and returns R. Lower R is better; the score is uncapped
relative to the best published R (reaching it = 1.0, beating it > 1.0).

Flattening convention (documented to the agent in Task.md):
    a[i*n + c] = A[i, c],  b[c*p + j] = B[c, j],  c[i*p + j] = C[i, j].
"""

from __future__ import annotations

import numpy as np

# (m, n, p): naive R = m*n*p (score 0); sota_ref = best published scalar-mult count (score 1).
SIZES = [
    {"mnp": (2, 2, 2), "naive": 8,  "sota_ref": 7,  "note": "Strassen 1969"},
    {"mnp": (3, 3, 3), "naive": 27, "sota_ref": 23, "note": "Laderman 1976"},
    {"mnp": (4, 4, 4), "naive": 64, "sota_ref": 48, "note": "AlphaEvolve 2025 (48 over C); recursive Strassen=49"},
]
TOL = 1e-7


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
    err = float(np.max(np.abs(recon - matmul_tensor(m, n, p))))
    if err >= TOL:
        return False, R, f"not exact (err={err:.2e})"
    # Redundant functional check on random integer matrices (guards indexing mistakes).
    rng = np.random.default_rng(0)
    for _ in range(3):
        A = rng.integers(-4, 5, (m, n)).astype(complex)
        B = rng.integers(-4, 5, (n, p)).astype(complex)
        prods = (U @ A.reshape(-1)) * (V @ B.reshape(-1))
        C = (W @ prods).reshape(m, p)
        if not np.allclose(C, A @ B, atol=1e-6):
            return False, R, "functional mismatch"
    return True, R, "ok"


def score_size(entry: dict, build_algorithm) -> dict:
    m, n, p = entry["mnp"]
    naive, sota = entry["naive"], entry["sota_ref"]
    try:
        U, V, W = build_algorithm(m, n, p)
    except Exception as exc:  # noqa: BLE001
        return {"mnp": entry["mnp"], "valid": False, "reason": f"raised: {exc}", "score": 0.0}
    ok, R, reason = verify_decomposition(U, V, W, m, n, p)
    if not ok:
        return {"mnp": entry["mnp"], "valid": False, "reason": reason, "R": R, "score": 0.0}
    progress = (naive - R) / (naive - sota)          # 0 at naive, 1 at sota, >1 beyond
    return {"mnp": entry["mnp"], "valid": True, "R": R, "sota_ref": sota,
            "score": float(max(0.0, progress))}      # uncapped above


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
