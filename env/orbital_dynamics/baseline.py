"""Weak trajectory transfer using only public observations and instrument rules."""

import math

import numpy as np

from .protocol import CHANNELS, validate_spec


def _rotation(spec):
    x, y = spec["position"]
    radius = math.hypot(x, y)
    return np.asarray([[x / radius, -y / radius], [y / radius, x / radius]])


def _ballistic(spec):
    times = np.asarray(spec["times"])
    position, velocity = np.asarray(spec["position"]), np.asarray(spec["velocity"])
    values = np.column_stack((position + times[:, None] * velocity,
                              np.tile(velocity, (len(times), 1))))
    for event in spec["impulses"]:
        after = times >= event["time"]
        values[after, :2] += (times[after] - event["time"])[:, None] * event["delta_v"]
        values[after, 2:] += event["delta_v"]
    return values


def _frame(values, rotation):
    return np.column_stack((values[:, :2].dot(rotation), values[:, 2:].dot(rotation)))


def _feature(spec):
    rotation = _rotation(spec)
    velocity = np.asarray(spec["velocity"]).dot(rotation)
    impulses = np.zeros(9)
    for index, event in enumerate(spec["impulses"]):
        impulses[index*3:index*3 + 3] = [event["time"] / 12] + np.asarray(event["delta_v"]).dot(rotation).tolist()
    return np.concatenate(([math.hypot(*spec["position"]) / 2], velocity, [spec["times"][-1] / 12], impulses))


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
                any(not isinstance(row, list) or len(row) != 4 for row in raw)):
            raise ValueError("record axis or values shape mismatch")
        try:
            values, axis = np.asarray(raw, dtype=float), np.asarray(axis, dtype=float)
        except (ValueError, TypeError, OverflowError):
            raise ValueError("record arrays must be finite numbers") from None
        if not np.isfinite(values).all() or not np.array_equal(axis, source["times"]):
            raise ValueError("record arrays must be finite and match its spec")
        rotation = _rotation(source)
        residual = _frame(values - _ballistic(source), rotation)
        options.append((float(np.linalg.norm(_feature(source) - _feature(query))), axis, residual))
    prediction = _ballistic(query)
    if options:
        _, axis, residual = min(options, key=lambda row: row[0])
        interpolated = np.column_stack([np.interp(query["times"], axis, residual[:, j]) for j in range(4)])
        prediction += _frame(interpolated, _rotation(query).T)
    if query["times"][0] == 0:
        prediction[0] = query["position"] + query["velocity"]
    if not np.isfinite(prediction).all():
        raise ValueError("trajectory transfer was not finite")
    return prediction.tolist()
