"""Nearest observed forcing history; public data only, no mechanistic recipe."""

import math

import numpy as np

from .protocol import AXIS_FIELD, CHANNELS, number, validate_spec


def baseline(records, spec):
    query = validate_spec(spec)
    if not isinstance(records, (list, tuple)) or len(records) > 256:
        raise ValueError("records must contain at most 256 public experiments")
    candidates = []
    for record in records:
        if not isinstance(record, dict) or not {"spec", "observation"} <= set(record):
            raise ValueError("record needs spec and observation")
        source = validate_spec(record["spec"])
        obs = record["observation"]
        if not isinstance(obs, dict) or obs.get("channels") != list(CHANNELS) or obs.get("axis") != source[AXIS_FIELD]:
            raise ValueError("record channel or axis mismatch")
        raw = obs.get("values")
        if not isinstance(raw, list) or len(raw) != len(source[AXIS_FIELD]) or any(not isinstance(row, list) or len(row) != 2 for row in raw):
            raise ValueError("record value shape mismatch")
        values = np.asarray([[number(v, -math.inf, math.inf, "record value") for v in row] for row in raw])
        # Zero pad histories: no extrapolated forcing is inferred from private laws.
        a, b = np.zeros(160), np.zeros(160)
        a[:len(source["forcing_w_m2"])] = source["forcing_w_m2"]
        b[:len(query["forcing_w_m2"])] = query["forcing_w_m2"]
        distance = float(np.mean((a-b)**2)) + abs(len(source["forcing_w_m2"])-len(query["forcing_w_m2"]))/160
        candidates.append((distance, source[AXIS_FIELD], values))
    if not candidates:
        return np.zeros((len(query[AXIS_FIELD]), 2)).tolist()
    _, axis, values = min(candidates, key=lambda item: item[0])
    return np.column_stack([np.interp(query[AXIS_FIELD], axis, values[:, j]) for j in range(2)]).tolist()
