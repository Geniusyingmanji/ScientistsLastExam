"""Valid weak baseline: make no experiments and abstain on every world."""

import numpy as np


def identify_climate_response(
    parameter_names, parameter_bounds, experiment, budget_units
):
    del parameter_bounds, experiment, budget_units
    return {
        "parameters": np.zeros(len(parameter_names), dtype=float),
        "confidence": 0.0,
        "abstain": True,
    }
