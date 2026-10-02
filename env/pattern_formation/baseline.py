"""Weak nearest-experiment transfer, using only public controls and readouts."""

import numpy as np

from .protocol import CHANNELS, initial_values, validate_spec


def _feature(spec):
    coefficients = np.zeros(16)
    for mode in spec["initial"]["modes"]:
        # Separate sine and cosine coefficients retain between-probe resets too.
        k = 2*(mode["mode"]-1)
        coefficients[k:k+2] = [mode["amplitude"]*np.cos(mode["phase"]), mode["amplitude"]*np.sin(mode["phase"])]
    return np.concatenate(([spec["length"]/32, spec["drive"], spec["initial"]["mean"]], coefficients))


def baseline(records, spec):
    query = validate_spec(spec)
    if not isinstance(records, (list, tuple)) or len(records) > 256:
        raise ValueError("records must contain at most 256 public experiments")
    options = []
    for record in records:
        if not isinstance(record, dict) or not {"spec", "observation"} <= set(record):
            raise ValueError("each record needs spec and observation")
        source = validate_spec(record["spec"])
        observation = record["observation"]
        if not isinstance(observation, dict) or observation.get("channels") != list(CHANNELS):
            raise ValueError("record channels do not match the apparatus")
        axis, raw = observation.get("axis"), observation.get("values")
        if (not isinstance(axis, list) or len(axis) != len(source["times"]) or
                not isinstance(raw, list) or len(raw) != len(axis) or
                any(not isinstance(row, list) or len(row) != len(CHANNELS) for row in raw)):
            raise ValueError("record shape mismatch")
        try:
            values, axis = np.asarray(raw, dtype=float), np.asarray(axis, dtype=float)
        except (ValueError, TypeError, OverflowError):
            raise ValueError("record arrays must be finite numbers") from None
        if not np.isfinite(values).all() or not np.array_equal(axis, source["times"]):
            raise ValueError("record arrays must be finite and match its spec")
        options.append((float(np.linalg.norm(_feature(source)-_feature(query))), axis, values-initial_values(source)))
    prediction = np.tile(initial_values(query), (len(query["times"]), 1))
    if options:
        _, axis, residual = min(options, key=lambda item: item[0])
        prediction += np.column_stack([np.interp(query["times"], axis, residual[:, j]) for j in range(len(CHANNELS))])
    if query["times"][0] == 0:
        prediction[0] = initial_values(query)
    if not np.isfinite(prediction).all():
        raise ValueError("prediction is nonfinite")
    return prediction.tolist()
