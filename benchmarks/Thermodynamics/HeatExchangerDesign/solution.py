"""Weak valid baseline: a conservative one-pass geometry sweep."""

import numpy as np


def design_exchanger(problem):
    diameter_low, diameter_high = problem["tube_inner_diameter_bounds_m"]
    length_low, length_high = problem["tube_length_bounds_m"]
    count_low, count_high = problem["tube_count_bounds"]
    baffle_low, baffle_high = problem["baffle_spacing_bounds_m"]
    rows = []
    for fraction in np.linspace(0.18, 0.78, 12):
        rows.append((
            diameter_low + 0.72 * (diameter_high - diameter_low),
            length_low + fraction * (length_high - length_low),
            int(round(count_low + fraction * 0.62 * (count_high - count_low))),
            baffle_low + 0.78 * (baffle_high - baffle_low),
            1,
        ))
    return np.asarray(rows, dtype=float)
