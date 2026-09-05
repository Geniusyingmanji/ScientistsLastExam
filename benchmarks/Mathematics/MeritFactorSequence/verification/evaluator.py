"""Frozen oracle for MeritFactorSequence (hidden from the agent).

The merit factor of a binary +/-1 sequence a_0,...,a_{n-1} is F = n^2 / (2 * sum_{k=1}^{n-1}
C_k^2), where C_k = sum_i a_i*a_{i+k} is the aperiodic autocorrelation at lag k -- a measure
of how "flat" the sequence's spectrum is. The best known construction (Borwein, Choi,
Jedwab, 2004) achieves F = 9.5851 at length 191; this is the current published record for
n >= 100, and finding any valid sequence exceeding it (at any length >= 100) would be a
real, checkable new result.
"""
from __future__ import annotations

import numpy as np

MIN_N = 100
BASELINE = 0.015227653418608192  # all-ones sequence of length 100, measured
SOTA_REF = 9.5851  # Borwein, Choi, Jedwab (2004), L=191, E=1903


def _normalized(value: float, baseline: float, sota: float) -> float:
    """0 at baseline, 1 at sota, >1 beyond. `value` is the higher-is-better quantity."""
    denom = sota - baseline
    if denom <= 0:
        return 0.0
    return float(max(0.0, (value - baseline) / denom))


def merit_factor(a: np.ndarray) -> float:
    n = len(a)
    conv = np.correlate(a, a, mode="full")
    mid = n - 1
    total = float(np.sum(conv[mid + 1:] ** 2))
    if total <= 0:
        return float("inf")
    return n * n / (2 * total)


def evaluate(construct_sequence) -> dict:
    try:
        raw = construct_sequence()
    except Exception as exc:  # noqa: BLE001
        return {"combined_score": 0.0, "valid": 0.0, "reason": "raised: %s" % exc}
    if isinstance(raw, dict):
        raw = raw.get("coefficients")
    try:
        coeffs = np.asarray([float(x) for x in raw], dtype=np.float64)
    except Exception as exc:  # noqa: BLE001
        return {"combined_score": 0.0, "valid": 0.0, "reason": "not a list of numbers: %s" % exc}
    n = len(coeffs)
    if n < MIN_N:
        return {"combined_score": 0.0, "valid": 0.0, "reason": "sequence length must be >= %d" % MIN_N}
    if not np.all(np.isin(coeffs, [-1.0, 1.0])):
        return {"combined_score": 0.0, "valid": 0.0, "reason": "coefficients must be in {-1, 1}"}
    mf = merit_factor(coeffs)
    score = _normalized(mf, BASELINE, SOTA_REF)
    return {
        "combined_score": score,
        "valid": 1.0,
        "n": n,
        "merit_factor": mf,
        "sota_ref": SOTA_REF,
        "beat_sota": bool(score > 1.0),
    }
