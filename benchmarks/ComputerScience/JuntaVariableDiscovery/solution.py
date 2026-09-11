"""Weak but valid baseline for JuntaVariableDiscovery.

Degree-one correlation, the textbook first move. It draws one random point per query, spends the
whole budget on single points, and estimates each variable's correlation with the answer, the
degree-one Fourier coefficient chi_i(x) f(x) averaged over the sample. A variable whose
coefficient is more than a family-wise margin from zero is named relevant; if more than
max_junta_size clear the bar it declines.

Two things are wrong with it. A variable can matter only through a parity or a gate, where its
single-variable correlation with the answer is exactly zero, so correlation never sees it and
misses true relevant variables. And a parity of many variables also has every degree-one
coefficient zero, so correlation sees nothing to decline and claims the unsupported worlds. It
misses offsets where the model holds and makes a false discovery where it does not.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm

DELTA = 1e-3


def identify(problem, query):
    n = problem["n"]
    K = problem["max_junta_size"]
    budget = problem["budget"]
    rng = np.random.default_rng(999)

    X = rng.integers(0, 2, size=(budget, n))
    Y = (2 * query(X) - 1).astype(float)
    chi = (2 * X - 1).astype(float)
    coef = (chi * Y[:, None]).mean(0)             # degree-one Fourier coefficients
    z = norm.isf(DELTA / n)

    claims = []
    for i in range(n):
        se = math.sqrt(max(1.0 - coef[i] ** 2, 1e-9) / budget)
        if abs(coef[i]) - z * se > 0:
            claims.append(i)

    if len(claims) > K:
        return {"verdict": "no_junta", "confidence": 0.5}
    return {"verdict": "junta", "relevant": sorted(claims), "confidence": 0.5}
