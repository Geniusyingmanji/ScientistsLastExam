"""Weak valid baseline: a conservative background-doping archive."""

import numpy as np


def design_doping_archive(problem):
    bounds = np.asarray(problem["design_bounds"], dtype=float)
    rows = []
    for background in np.linspace(16.4, 17.0, 8):
        row = np.asarray(
            [background, 15.3, 15.3, 0.16, 0.84, 0.08], dtype=float
        )
        rows.append(np.clip(row, bounds[:, 0], bounds[:, 1]))
    return np.asarray(rows, dtype=float)
