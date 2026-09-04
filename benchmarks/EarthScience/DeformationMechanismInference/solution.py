"""Weak valid baseline: one coarse GNSS survey followed by abstention."""

import numpy as np


def infer_deformation_source(survey_bounds_m, model_library, measure, budget_units):
    del model_library, budget_units
    low, high = map(float, survey_bounds_m)
    axis = np.linspace(low, high, 3)
    stations = np.asarray([(x, y) for x in axis for y in axis], dtype=float)
    measure(stations, "gnss")
    return {
        "mechanism_probabilities": {"mogi": 1 / 3, "sill": 1 / 3, "dike": 1 / 3},
        "parameters": [], "confidence": 0.0, "abstain": True,
    }
