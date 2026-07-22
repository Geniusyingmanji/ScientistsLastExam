"""Weak baseline: one legal sounding followed by calibrated abstention."""

import numpy as np


def discover_atmosphere(public_model, observe, budget_units):
    del public_model, budget_units
    observe(np.asarray((0, 6, 12, 18)), 1.0)
    return {
        "temperature_anomaly_knots_K": np.zeros(4),
        "optical_depth_scale": 1.0,
        "support": np.zeros(5, dtype=int),
        "confidence": 0.0,
        "abstain": True,
    }
