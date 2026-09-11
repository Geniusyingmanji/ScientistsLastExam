"""Weak valid baseline: one protocol, mid-range parameters, never refuses.

It charges a legal voltage step, guesses the centre of every public bound and
claims the three-current family on every membrane — including the ones carrying an
extra current.
"""

from __future__ import annotations

import numpy as np


def recover_channel_parameters(problem, voltage_step, budget_units):
    del budget_units
    voltage_step(0.0, 20.0)
    bounds = np.asarray(problem["parameter_bounds"], dtype=float)
    parameters = list(0.5 * (bounds[:, 0] + bounds[:, 1]))
    return {"parameters": parameters, "abstain": False, "confidence": 0.5}
