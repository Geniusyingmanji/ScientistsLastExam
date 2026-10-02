"""Weak transfer from public records; no circuit family, parameters or seed."""

import numpy as np

from .protocol import AXIS_FIELD, CHANNELS, validate_spec


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
        if (not isinstance(axis, list) or len(axis) != len(source[AXIS_FIELD]) or
                not isinstance(raw, list) or len(raw) != len(axis) or
                any(not isinstance(row, list) or len(row) != 2 for row in raw)):
            raise ValueError("record shape mismatch")
        try:
            values, frequencies = np.asarray(raw, dtype=float), np.asarray(axis, dtype=float)
        except (ValueError, TypeError, OverflowError):
            raise ValueError("record arrays must be finite numbers") from None
        if not np.isfinite(values).all() or not np.array_equal(frequencies, source[AXIS_FIELD]):
            raise ValueError("record arrays must be finite and match its spec")
        distance = sum(np.log(source[key]/query[key])**2 for key in ("source_ohm", "load_ohm"))
        options.append((distance, np.log(frequencies), values/source["amplitude_v"]))
    if options:
        _, axis, values = min(options, key=lambda item: item[0])
        prediction = query["amplitude_v"]*np.column_stack([
            np.interp(np.log(query[AXIS_FIELD]), axis, values[:, column]) for column in range(2)])
    else:
        # Known external source/load divider, ignoring current into the sealed box.
        prediction = np.tile([query["amplitude_v"]/(1+query["source_ohm"]/query["load_ohm"]), 0.],
                             (len(query[AXIS_FIELD]), 1))
    if not np.isfinite(prediction).all():
        raise ValueError("prediction is nonfinite")
    return prediction.tolist()

