"""Legal weak baseline: aligned half-duty dielectric layers."""

import numpy as np


def design_grating(problem):
    period = float(problem["period_um"])
    depth = min(float(problem["depth_bounds_um"][1]), 0.11 * period)
    design = np.zeros((int(problem["layer_count"]), 3), dtype=float)
    design[:, 0] = depth
    design[:, 1] = 0.5
    design[:, 2] = 0.5
    return design
