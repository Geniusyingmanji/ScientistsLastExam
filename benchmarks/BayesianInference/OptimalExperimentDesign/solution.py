"""Weak valid baseline: spend the budget on the first candidate experiments."""

import numpy as np


def select_designs(candidate_points, feature_matrix, n_measurements):
    """Return integer indices into candidate_points; repeated indices are allowed."""
    del feature_matrix
    count = min(int(n_measurements), len(candidate_points))
    return np.arange(count, dtype=int)
