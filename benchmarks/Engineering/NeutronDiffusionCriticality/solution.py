"""Baseline: uniform enrichment at the maximum average allowed."""
import numpy as np
def optimize_enrichment(n_zones, avg_max):
    return np.full(n_zones, avg_max)
