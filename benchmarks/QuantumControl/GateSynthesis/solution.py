"""Weak valid baseline: free evolution with all control channels off."""

import numpy as np


def design_pulse(drift, controls, target, n_steps, dt, amplitude_limit):
    del drift, target, dt, amplitude_limit
    return np.zeros((int(n_steps), len(controls)), dtype=float)
