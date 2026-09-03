"""Truth-blind reference for ForcedSignalAttribution: EOF-truncated fingerprinting by total least
squares, a control-based null distribution, and a residual consistency check that accounts for
the fingerprint's own noise.

Reads only the public problem and the charged control runs. Deliberately not at the ceiling: it
spends the whole budget on segments the length of the record, estimates the null spread of the
detection statistic from overlapping windows of the pooled control years, fixes the EOF
truncation by a variance fraction, and uses a fixed 95th-percentile residual test. A truncation
chosen for the fingerprint, a bootstrap that respects the window overlap, and a sharper
consistency test are the headroom a searcher is meant to claim.
"""
from __future__ import annotations

import numpy as np

VARIANCE_FRACTION = 0.9
MAX_MODES = 8
WINDOW_STEP = 5
RESIDUAL_PERCENTILE = 95.0
ONE_SIDED_Z = 1.645


def _whitener(control_pool):
    centered = control_pool - control_pool.mean(axis=0, keepdims=True)
    cov = centered.T @ centered / max(1, centered.shape[0] - 1)
    values, vectors = np.linalg.eigh(cov)
    order = np.argsort(values)[::-1]
    values, vectors = values[order], vectors[:, order]
    cumulative = np.cumsum(values) / np.sum(values)
    k = int(min(MAX_MODES, max(2, np.searchsorted(cumulative, VARIANCE_FRACTION) + 1)))
    return vectors[:, :k] / np.sqrt(np.maximum(values[:k], 1e-12))


def _tls(y, f, noise_ratio):
    """Total least squares for y = beta * f when f carries noise_ratio times the noise variance
    of y (both in whitened units): scale f so its noise is unit, take the smallest right singular
    vector of [f', y], and undo the scale."""
    scale = 1.0 / np.sqrt(noise_ratio)
    stacked = np.column_stack([f * scale, y])
    _u, _s, vt = np.linalg.svd(stacked, full_matrices=False)
    v = vt[-1]
    if abs(v[1]) < 1e-12:
        return float(y @ f / (f @ f))
    return float(-v[0] / v[1] * scale)


def attribute(problem, run_control):
    years = int(problem["years"])
    budget = int(problem["control_budget_years"])
    ensemble = int(problem["forced_ensemble_size"])
    observations = np.asarray(problem["observations"], dtype=float)
    fingerprint = np.asarray(problem["fingerprint"], dtype=float)
    segments = []
    remaining = budget
    while remaining >= years:
        segments.append(np.asarray(run_control(years), dtype=float))
        remaining -= years
    if remaining >= int(problem["min_segment_years"]):
        segments.append(np.asarray(run_control(remaining), dtype=float))
    pool = np.vstack(segments)
    W = _whitener(pool)
    Y, F = (observations @ W).ravel(), (fingerprint @ W).ravel()
    noise_ratio = 1.0 / ensemble
    beta = _tls(Y, F, noise_ratio)
    null, residual_null = [], []
    for start in range(0, pool.shape[0] - years + 1, WINDOW_STEP):
        window = (pool[start:start + years] @ W).ravel()
        b = _tls(window, F, noise_ratio)
        null.append(b)
        residual_null.append(float(np.sum((window - b * F) ** 2)) / (1.0 + b * b * noise_ratio))
    sigma = float(np.std(null, ddof=1)) if len(null) > 2 else float("inf")
    # The residual of the fit carries the fingerprint's noise scaled by beta; the control windows
    # carry it scaled by their own (near-zero) fits, so both are normalised by the expected
    # inflation before they are compared.
    residual = float(np.sum((Y - beta * F) ** 2)) / (1.0 + beta * beta * noise_ratio)
    if residual > float(np.percentile(residual_null, RESIDUAL_PERCENTILE)):
        return {"abstain": True, "confidence": 0.7}
    low, high = beta - ONE_SIDED_Z * sigma, beta + ONE_SIDED_Z * sigma
    return {"detected": bool(low > 0.0), "scaling_factor": beta, "interval": [low, high],
            "abstain": False, "confidence": 0.7}
