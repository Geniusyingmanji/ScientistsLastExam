"""Reference for JuntaVariableDiscovery: pivotal influence with a family-wise margin.

Truth-blind. It reads only the public problem and the answers `query` returns, and it works in
three stages.

- **Pivotal pairs.** The only way to read a variable's influence through the parity and the gates
  is to flip it against a background that is otherwise fixed and see whether the answer changes.
  For each variable it draws the same number of random backgrounds, queries each background and
  its flip, and records how often the two answers disagree. The budget is split evenly over the
  variables, at ninety per cent of it so a malformed count never overspends.

- **The noise floor.** Two answers, each flipped with probability eta, disagree with probability
  base = 2 eta (1 - eta) when the variable is irrelevant, and base + Inf (1 - 2 eta)^2 when its
  influence is Inf. So an irrelevant variable's disagreement rate sits at base up to binomial
  noise, and a relevant one sits above it by an amount that shrinks with eta.

- **The family-wise test.** A variable is named relevant when its disagreement rate is above base
  by more than z standard errors, z the normal quantile of delta / n, so that under the null the
  chance any irrelevant variable is named is at most delta by a union bound. When more than
  max_junta_size variables clear the bar, no junta of the published size explains the answers and
  it declines.

delta is 10^-3 per world.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm

DELTA = 1e-3
BUDGET_FRACTION = 0.9


def identify(problem, query):
    n = problem["n"]
    K = problem["max_junta_size"]
    eta = problem["noise_rate"]
    budget = problem["budget"]
    rng = np.random.default_rng(12345)

    base = 2.0 * eta * (1.0 - eta)                 # disagreement floor for an irrelevant variable
    per = max(4, int(budget * BUDGET_FRACTION) // (2 * n))
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

    if len(significant) > K:
        return {"verdict": "no_junta", "confidence": 0.9}
    return {"verdict": "junta", "relevant": sorted(significant), "confidence": 0.6}
