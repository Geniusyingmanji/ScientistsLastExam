"""Valid weak baseline: perform no sequencing and abstain on every world."""

import numpy as np


def infer_demography(
    parameter_names, parameter_bounds, allowed_sample_sizes, sequence,
    budget_units,
):
    del parameter_bounds, allowed_sample_sizes, sequence, budget_units
    return {
        "parameters": np.zeros(len(parameter_names), dtype=float),
        "confidence": 0.0,
        "abstain": True,
    }
