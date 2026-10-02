"""Weak empirical transfer using public records and calibrated controls only."""

import math

import numpy as np

from .protocol import CHANNELS, number, validate_spec


def _instrument(spec):
    """Hypothesis of no unknown evolution, retaining only declared controls."""
    vector = np.asarray(spec["initial_magnetization"], float)
    anchor, cursor, rows = 0.0, 0, []

    def shift(v, ms):
        angle = 2*math.pi*spec["detuning_hz"]*ms*.001
        c, s = math.cos(angle), math.sin(angle)
        return np.asarray([c*v[0]-s*v[1], s*v[0]+c*v[1], v[2]])

    def rotate(v, event):
        n = np.asarray([math.cos(event["phase_rad"]), math.sin(event["phase_rad"]), 0.])
        c, s = math.cos(event["angle_rad"]), math.sin(event["angle_rad"])
        return c*v+s*np.cross(n,v)+(1-c)*np.dot(n,v)*n

    for target in spec["times_ms"]:
        while cursor < len(spec["pulses"]) and spec["pulses"][cursor]["time_ms"] <= target:
            event = spec["pulses"][cursor]
            vector = rotate(shift(vector, event["time_ms"]-anchor), event)
            anchor, cursor = event["time_ms"], cursor+1
        rows.append(shift(vector, target-anchor))
    return np.asarray(rows)


def _feature(spec):
    pulses = np.zeros(36)
    for i, p in enumerate(spec["pulses"]):
        pulses[3*i:3*i+3] = [p["time_ms"]/250, p["angle_rad"]/math.pi, p["phase_rad"]/math.pi]
    return np.r_[spec["initial_magnetization"], spec["detuning_hz"]/40, len(spec["pulses"]), pulses]


def baseline(records, spec):
    query = validate_spec(spec)
    if not isinstance(records, (tuple, list)) or len(records) > 256:
        raise ValueError("records must contain at most 256 public experiments")
    options = []
    for record in records:
        if not isinstance(record, dict) or not {"spec", "observation"} <= set(record):
            raise ValueError("every record needs spec and observation")
        source = validate_spec(record["spec"])
        observation = record["observation"]
        if not isinstance(observation, dict) or observation.get("channels") != list(CHANNELS):
            raise ValueError("record channels do not match")
        axis, raw = observation.get("axis"), observation.get("values")
        if not isinstance(axis, list) or not isinstance(raw, list) or len(axis) != len(source["times_ms"]) or len(raw) != len(axis):
            raise ValueError("record axis or row count mismatch")
        axis = [number(t, 0, 250, "record time") for t in axis]
        if axis != source["times_ms"]:
            raise ValueError("record axis does not match its spec")
        if any(not isinstance(row, list) or len(row) != 3 for row in raw):
            raise ValueError("record values must have three channels")
        values = np.asarray([[number(v, -math.inf, math.inf, "record value") for v in row] for row in raw])
        options.append((float(np.linalg.norm(_feature(source)-_feature(query))), axis, values-_instrument(source)))
    result = _instrument(query)
    if options:
        _, axis, residual = min(options, key=lambda item: item[0])
        result += np.column_stack([np.interp(query["times_ms"], axis, residual[:, i]) for i in range(3)])
    if query["times_ms"][0] == 0:
        result[0] = query["initial_magnetization"]
    if not np.isfinite(result).all():
        raise ValueError("baseline prediction became nonfinite")
    return result.tolist()
