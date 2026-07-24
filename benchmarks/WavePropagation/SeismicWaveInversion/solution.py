"""Weak valid baseline: acquire a small near-offset gather and make no claim."""

import numpy as np


def discover_layered_velocity(
    midpoint_bounds_m,
    offset_bounds_m,
    frequency_bounds_hz,
    parameter_names,
    parameter_bounds,
    acquire,
    budget_units,
):
    del frequency_bounds_hz, parameter_names, parameter_bounds, budget_units
    offsets = np.linspace(offset_bounds_m[0], min(600.0, offset_bounds_m[1]), 4)
    midpoint = 0.5 * (midpoint_bounds_m[0] + midpoint_bounds_m[1])
    acquire(np.full(4, midpoint), offsets, 12.0)
    return {
        "parameters": np.zeros(9),
        "confidence": 0.0,
        "abstain": True,
    }
