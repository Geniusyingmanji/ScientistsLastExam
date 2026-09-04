"""Weak, valid baseline: a conservative constant-current charge."""
import numpy as np

def charge_policy(problem):
    return np.full(problem["time_steps"], 0.5, dtype=float)
