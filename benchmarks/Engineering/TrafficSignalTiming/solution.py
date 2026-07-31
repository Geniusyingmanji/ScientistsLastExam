"""Baseline: equal green split, zero offsets."""
import numpy as np
def optimize_signals(n_intersections, cycle_length, demands):
    return {
        "green_times": np.full(n_intersections, cycle_length / 2),
        "offsets": np.zeros(n_intersections),
    }
