"""Frozen oracle for LennardJonesCluster (hidden from the agent).

Computes the Lennard-Jones energy of a candidate configuration and normalizes against
catalogued putative global minima (Cambridge Cluster Database / Wales & Doye 1997,
reduced units ε = σ = 1). The non-interacting limit (E = 0) is the natural baseline,
so gap_closed(n) = clip(E_found / E_min, 0, 1).
"""

from __future__ import annotations

import numpy as np

# Putative global minima, reduced LJ units (energy of the global-minimum geometry).
GLOBAL_MINIMA = {
    5: -9.103852,
    6: -12.712062,
    7: -16.505384,
    8: -19.821489,
    13: -44.326801,
    19: -72.659782,
    38: -173.928427,
}

# Expert-level test set. N=38 is the classic double-funnel LJ cluster that separates
# local basin hopping from generic local relaxation.
TEST_SIZES = [13, 19, 38]
HARDCORE = 0.3  # distances below this are physically impossible


def lj_energy(coords: np.ndarray) -> float:
    coords = np.asarray(coords, dtype=float)
    n = coords.shape[0]
    if n < 2:
        return 0.0
    diff = coords[:, None, :] - coords[None, :, :]
    r2 = np.sum(diff * diff, axis=-1)
    iu = np.triu_indices(n, k=1)
    r2 = r2[iu]
    r2 = np.maximum(r2, 1e-12)
    inv6 = r2 ** -3
    inv12 = inv6 * inv6
    return float(np.sum(4.0 * (inv12 - inv6)))


def min_pair_distance(coords: np.ndarray) -> float:
    coords = np.asarray(coords, dtype=float)
    n = coords.shape[0]
    if n < 2:
        return np.inf
    diff = coords[:, None, :] - coords[None, :, :]
    r2 = np.sum(diff * diff, axis=-1)
    iu = np.triu_indices(n, k=1)
    return float(np.sqrt(np.min(r2[iu])))


def score_configuration(n: int, coords) -> dict:
    """Return per-size validity, energy, and gap-closed score in [0, 1]."""
    try:
        arr = np.asarray(coords, dtype=float)
    except Exception as exc:  # noqa: BLE001
        return {"n": n, "valid": False, "reason": f"non-array: {exc}", "score": 0.0}
    if arr.shape != (n, 3) or not np.all(np.isfinite(arr)):
        return {"n": n, "valid": False, "reason": "bad shape or non-finite", "score": 0.0}
    if min_pair_distance(arr) < HARDCORE:
        return {"n": n, "valid": False, "reason": "atoms inside hard core", "score": 0.0}
    e = lj_energy(arr)
    if not np.isfinite(e):
        return {"n": n, "valid": False, "reason": "non-finite energy", "score": 0.0}
    e_min = GLOBAL_MINIMA[n]
    score = e / e_min  # both negative near optimum -> in (0, 1]
    score = float(min(1.0, max(0.0, score)))
    return {"n": n, "valid": True, "energy": e, "e_min": e_min, "score": score}


def evaluate(build_cluster) -> dict:
    """Score a candidate's build_cluster callable over the test set."""
    per_size = []
    for n in TEST_SIZES:
        try:
            coords = build_cluster(n)
        except Exception as exc:  # noqa: BLE001
            per_size.append({"n": n, "valid": False, "reason": f"raised: {exc}", "score": 0.0})
            continue
        per_size.append(score_configuration(n, coords))
    scores = [r["score"] for r in per_size]
    n_valid = sum(1 for r in per_size if r.get("valid"))
    combined = float(np.mean(scores)) if scores else 0.0
    return {
        "combined_score": combined,
        "valid": 1.0 if n_valid == len(TEST_SIZES) else 0.0,
        "feasibility_rate": n_valid / len(TEST_SIZES),
        "per_size": per_size,
    }
