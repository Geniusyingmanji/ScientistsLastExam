"""Weak valid baseline: make one reconnaissance survey and claim no geology."""

import numpy as np


def discover_bodies(profile_bounds_m, depth_bounds_m, measure, budget_units):
    del depth_bounds_m, budget_units
    stations = np.linspace(profile_bounds_m[0], profile_bounds_m[1], 8)
    measure(stations, 500.0)
    return {"bodies": [], "confidence": 0.0, "abstain": True}
