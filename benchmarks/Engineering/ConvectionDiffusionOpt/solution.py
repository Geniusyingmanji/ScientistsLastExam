"""Weak valid baseline: exercise the active laboratory and make no scientific claim."""

import numpy as np


def design_thermal_policy(
    grid_shape, parameter_names, parameter_bounds, design_specification,
    experiment, budget_units,
):
    del grid_shape, parameter_bounds, design_specification, budget_units
    experiment(
        np.asarray(((0.25, 0.25),)),
        np.asarray((1.0,)),
        np.asarray(((0.25, 0.25), (0.25, 0.75), (0.75, 0.25), (0.75, 0.75))),
    )
    return {
        "parameters": np.zeros(len(parameter_names)),
        "source_positions": np.zeros((4, 2)),
        "source_strengths": np.zeros(4),
        "confidence": 0.0,
        "abstain": True,
    }
