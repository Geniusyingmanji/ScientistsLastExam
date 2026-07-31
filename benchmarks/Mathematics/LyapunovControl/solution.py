"""Baseline: zero control (no intervention, chaos persists)."""
import numpy as np
def design_controller(sigma, rho, beta):
    def controller(state):
        return np.zeros(3)  # no control
    return controller
