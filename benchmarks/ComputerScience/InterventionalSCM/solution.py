"""Weak valid baseline: calibrated abstention from unsupported causal claims."""

import numpy as np


def discover_mechanism(n_variables, observe, intervene, budget_units):
    """Return the null mechanism after one small observational check.

    This baseline deliberately makes no directed causal claim. It is valid and scientifically
    conservative, but it cannot recover the non-null hidden mechanisms.
    """
    n = int(n_variables)
    # Exercise the laboratory contract without trying to infer direction from correlation.
    observe(min(32, max(8, int(budget_units) * 2)))
    return {
        "adjacency": np.zeros((n, n), dtype=int),
        "coefficients": np.zeros((n, n), dtype=float),
        "confidence": 0.0,
        "abstain": True,
    }

