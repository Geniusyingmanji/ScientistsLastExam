"""Weak valid baseline: uniform-amplitude steering toward the requested direction."""

import numpy as np


def design_array(positions_lambda, steering_angle_deg, interference_angles_deg,
                 mainlobe_half_width_sine, angle_limit_deg, null_half_width_deg,
                 null_weight, l2_norm_limit, element_amplitude_limit):
    del interference_angles_deg, mainlobe_half_width_sine, angle_limit_deg
    del null_half_width_deg, null_weight, l2_norm_limit, element_amplitude_limit
    positions = np.asarray(positions_lambda, dtype=float)
    target = np.exp(
        1j * 2.0 * np.pi * positions
        * np.sin(np.deg2rad(float(steering_angle_deg)))
    )
    return np.conj(target) / len(positions)
