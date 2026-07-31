"""Weak valid baseline: coast without thrust on every transfer."""

import numpy as np


def design_guidance(initial_elements, target_elements, initial_mass_kg,
                    maximum_thrust_n, specific_impulse_s, duration_s, n_segments):
    del (
        initial_elements, target_elements, initial_mass_kg, maximum_thrust_n,
        specific_impulse_s, duration_s,
    )
    return np.zeros((int(n_segments), 7), dtype=float)
