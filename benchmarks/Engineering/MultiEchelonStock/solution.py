"""Baseline: large buffer stocks (safe but expensive)."""
import numpy as np
def optimize_inventory(n_stages, lead_times, holding_costs, backorder_costs, service_target):
    return np.array([80, 60, 40])  # over-stocked
