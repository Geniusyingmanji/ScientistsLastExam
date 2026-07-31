"""Weak valid baseline: make one admissible query and refuse the model library."""

import numpy as np


def calibrate_forcefield(problem, query):
    minimum = float(problem["distance_bounds_a"][0])
    side = min(max(1.35 * minimum, 3.2), 4.4)
    height = (3.0 ** 0.5) * side / 2.0
    coordinates = np.asarray([
        [[-0.5 * side, 0.0, 0.0], [0.5 * side, 0.0, 0.0],
         [0.0, height, 0.0]],
    ], dtype=float)
    observation = query(
        coordinates,
        float(problem["first_query_temperature_k"]),
        {
            "weights": {"mie": 1.0 / 3.0, "morse": 1.0 / 3.0,
                        "unsupported": 1.0 / 3.0},
            "retained": ["mie", "morse", "unsupported"],
        },
    )
    return {
        "hypothesis_weights": {
            "mie": 0.0, "morse": 0.0, "unsupported": 1.0,
        },
        "retained_hypotheses": ["unsupported"],
        "selected_model": "unsupported",
        "parameters": {},
        "parameter_intervals": {},
        "second_virial_cm3_mol_by_temperature": {},
        "boyle_temperature_k": None,
        "boyle_temperature_above_threshold": None,
        "confidence": 0.0,
        "abstain": True,
        "evidence_ids": [observation["observation_id"]] + list(
            observation["configuration_ids"]
        ),
    }
