"""Baseline: uniform geometry (no optimization across flexion zones)."""
import numpy as np
def design_joint(n_params):
    return np.array([30, 30, 30, 30, 50, 50, 50, 50], dtype=float)
