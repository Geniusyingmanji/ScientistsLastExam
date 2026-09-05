"""Weak valid baseline: one potential step, uniform family probabilities, no refusal.

It charges one legal step, splits probability evenly across the six families and
guesses mid-range parameters — confident in exactly the way the audit should punish,
since it never distinguishes a family and never refuses the unmodellable worlds.
"""

from __future__ import annotations

import numpy as np


def identify_current_law(problem, step, budget_units):
    del budget_units
    step(0.5)
    bounds = np.asarray(problem["parameter_bounds"], dtype=float)
    parameters = list(0.5 * (bounds[:, 0] + bounds[:, 1]))
    probabilities = {name: 1.0 / len(problem["families"])
                     for name in problem["families"]}
    return {"family_probabilities": probabilities, "parameters": parameters,
            "abstain": False, "confidence": 0.5}
