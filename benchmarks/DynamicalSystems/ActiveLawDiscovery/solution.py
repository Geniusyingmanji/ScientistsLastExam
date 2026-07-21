"""Weak valid baseline: one check followed by calibrated abstention."""

import numpy as np


def discover_law(n_states, term_names, experiment, budget_units):
    n_states = int(n_states)
    n_terms = len(term_names)
    # Exercise the laboratory contract but make no unsupported mechanistic claim.
    experiment(np.zeros(n_states), np.zeros(8), 8)
    return {
        "coefficients": np.zeros((n_terms, n_states), dtype=float),
        "support": np.zeros((n_terms, n_states), dtype=int),
        "confidence": 0.0,
        "abstain": True,
    }
