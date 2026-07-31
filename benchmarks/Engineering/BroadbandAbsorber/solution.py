"""Weak valid baseline: identical cells tuned near the geometric band center."""

import math

import numpy as np


def design_absorber(problem):
    n_resonators = int(problem["n_resonators"])
    low_frequency, high_frequency = map(float, problem["frequency_band_hz"])
    target_frequency = math.sqrt(low_frequency * high_frequency)
    radius = np.full(n_resonators, 0.003, dtype=float)
    length = np.full(n_resonators, 0.010, dtype=float)
    opening_fraction = (
        np.pi * radius**2 / float(problem["cell_side_m"]) ** 2
    )
    effective_length = length + 1.70 * radius
    depth = (
        opening_fraction * float(problem["sound_speed_m_s"]) ** 2
        / ((2.0 * np.pi * target_frequency) ** 2 * effective_length)
    )
    depth = np.clip(
        depth,
        float(problem["cavity_depth_bounds_m"][0]),
        float(problem["maximum_total_depth_m"]) - length - 0.002,
    )
    return np.column_stack((depth, length, radius))
