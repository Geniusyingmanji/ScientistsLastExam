"""Declared shortcut: the pivotal test without the refusal.

It runs the reference's pivotal pass but never declines; it truncates the significant set to the
junta size and always claims it. On a big parity it names variables and takes the false discovery,
so it scores zero on the unsupported worlds and cannot rise above the junta worlds' share.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm

DELTA = 1e-3


def identify(problem, query):
    n = problem["n"]
    K = problem["max_junta_size"]
    eta = problem["noise_rate"]
    budget = problem["budget"]
    rng = np.random.default_rng(12345)
    base = 2.0 * eta * (1.0 - eta)
    per = max(4, int(budget * 0.9) // (2 * n))
    z = norm.isf(DELTA / n)
    significant = []
    for i in range(n):
        X = rng.integers(0, 2, size=(per, n))
        X2 = X.copy()
        X2[:, i] ^= 1
        disagree = float(np.mean(query(X) != query(X2)))
        se = math.sqrt(max(disagree * (1.0 - disagree), 1e-9) / per)
        if disagree - z * se > base:
            significant.append(i)
    return {"verdict": "junta", "relevant": sorted(significant)[:K], "confidence": 0.5}
