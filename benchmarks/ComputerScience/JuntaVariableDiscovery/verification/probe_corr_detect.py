"""Declared shortcut: correlation for the claims, a pivotal pass only for the refusal.

It spends half the budget on degree-one correlation to name variables and half on a pivotal pass
used only to decide whether to decline. Correlation cannot see a variable that acts through a
parity or a gate, so its recall on the junta worlds is low even though the pivotal pass declines
the big parities.
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
    rng = np.random.default_rng(999)
    base = 2.0 * eta * (1.0 - eta)
    z = norm.isf(DELTA / n)

    half = budget // 2
    X = rng.integers(0, 2, size=(half, n))
    Y = (2 * query(X) - 1).astype(float)
    chi = (2 * X - 1).astype(float)
    coef = (chi * Y[:, None]).mean(0)
    claims = [i for i in range(n) if abs(coef[i]) - z * math.sqrt(max(1.0 - coef[i] ** 2, 1e-9) / half) > 0]

    per = max(4, (budget - half) // (2 * n))
    significant = []
    for i in range(n):
        Xp = rng.integers(0, 2, size=(per, n))
        Xp2 = Xp.copy()
        Xp2[:, i] ^= 1
        disagree = float(np.mean(query(Xp) != query(Xp2)))
        se = math.sqrt(max(disagree * (1.0 - disagree), 1e-9) / per)
        if disagree - z * se > base:
            significant.append(i)
    if len(significant) > K:
        return {"verdict": "no_junta", "confidence": 0.5}
    return {"verdict": "junta", "relevant": sorted(claims), "confidence": 0.5}
