"""Weak empirical residual transfer using public records, without a simulator."""

import math

import numpy as np

from .protocol import CHANNELS, assigned_initial, number, validate_spec


def _feature(spec):
    return np.asarray([spec["population_size"]/32, spec["initial_A"]/spec["population_size"],
                       spec["selection_bias"]/.5, spec["newborn_flip_probability"]/.1])


def baseline(records, spec):
    query = validate_spec(spec)
    if not isinstance(records, (tuple, list)) or len(records) > 256:
        raise ValueError("records must contain at most256 public experiments")
    options = []
    for record in records:
        if not isinstance(record, dict) or not {"spec", "observation"} <= set(record):
            raise ValueError("every record needs spec and observation")
        source = validate_spec(record["spec"])
        observation = record["observation"]
        if not isinstance(observation, dict) or observation.get("channels") != list(CHANNELS):
            raise ValueError("record channels do not match")
        axis, rows = observation.get("axis"), observation.get("values")
        if not isinstance(axis, list) or not isinstance(rows, list) or len(axis) != len(source["times"]) or len(rows) != len(axis):
            raise ValueError("record axis or row count mismatch")
        axis = [number(t, 0, 60, "record time") for t in axis]
        if axis != source["times"] or any(not isinstance(row, list) or len(row) != 4 for row in rows):
            raise ValueError("record axis or shape mismatch")
        values = np.asarray([[number(v, -math.inf, math.inf, "record value") for v in row] for row in rows])
        options.append((float(np.linalg.norm(_feature(source)-_feature(query))), axis, values-assigned_initial(source)))
    result = np.tile(assigned_initial(query), (len(query["times"]), 1))
    if options:
        _, axis, residual = min(options, key=lambda item: item[0])
        result += np.column_stack([np.interp(query["times"], axis, residual[:, c]) for c in range(4)])
    if query["times"][0] == 0:
        result[0] = assigned_initial(query)
    if not np.isfinite(result).all():
        raise ValueError("baseline prediction became nonfinite")
    return result.tolist()
