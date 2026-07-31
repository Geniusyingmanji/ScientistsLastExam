"""Baseline: unit circle (C_D = 1.0 by definition)."""
import numpy as np
def optimize_shape(n_modes, area_target):
    """Return Fourier coefficients [a0, a1, b1, a2, b2, ...] for r(theta)."""
    coeffs = np.zeros(2 * n_modes + 1)
    coeffs[0] = 1.0  # a0 = radius of circle
    return coeffs
