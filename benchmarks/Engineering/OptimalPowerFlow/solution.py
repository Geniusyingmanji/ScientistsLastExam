"""Weak valid baseline: proportional dispatch across generator headroom."""

import numpy as np


def solve_opf(n_bus, generator_buses, demand, p_min, p_max, cost_quadratic,
              cost_linear, lines, susceptances, line_limits):
    del n_bus, generator_buses, cost_quadratic, cost_linear, lines, susceptances, line_limits
    p_min = np.asarray(p_min, dtype=float)
    p_max = np.asarray(p_max, dtype=float)
    remaining = float(np.sum(demand) - np.sum(p_min))
    headroom = p_max - p_min
    return p_min + remaining * headroom / np.sum(headroom)
