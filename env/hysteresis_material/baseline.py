"""Empirical history-neighbor baseline using public records only.

No differential equation, hidden family, private parameter or seed is used. The
baseline transfers a nearby observed trajectory after rescaling elapsed time.
"""

import numpy as np

from .protocol import CHANNELS, MAX_ROWS, validate_spec


def _features(spec):
    horizon = max(spec["times"][-1], 0.05)
    fractions = np.linspace(0.0, 1.0, 25)
    knots = spec["protocol"]
    fields = np.interp(fractions * horizon, [k["time"] for k in knots], [k["field"] for k in knots]) / 1.5
    preparation = spec["preparation"]
    total = sum(step["duration"] for step in preparation)
    if preparation:
        ends = np.cumsum([step["duration"] for step in preparation])
        indices = np.searchsorted(ends, np.linspace(0.0, total, 12), side="right")
        prep_fields = np.asarray([preparation[min(int(i), len(preparation) - 1)]["field"] for i in indices]) / 1.5
    else:
        prep_fields = np.full(12, -1.0 if spec["reset"] == "negative" else 1.0)
    return np.concatenate((fields / np.sqrt(len(fields)), prep_fields / np.sqrt(len(prep_fields)),
                           [np.log1p(horizon) / 3.0, np.log1p(total) / 3.0,
                            -1.0 if spec["reset"] == "negative" else 1.0]))


def baseline(records, spec):
    canonical = validate_spec(spec)
    if not isinstance(records, (list, tuple)) or len(records) > 256:
        raise ValueError("records must be an array with at most 256 records")
    candidates = []
    query_feature = _features(canonical)
    for record in records:
        if not isinstance(record, dict) or not {"spec", "observation"}.issubset(record):
            raise ValueError("each record needs spec and observation")
        observed_spec = validate_spec(record["spec"])
        observation = record["observation"]
        if not isinstance(observation, dict) or observation.get("channels") != list(CHANNELS):
            raise ValueError("record observation channels must match the public channel")
        row_count = len(observed_spec["times"])
        raw_axis, raw_values = observation.get("axis"), observation.get("values")
        if (not isinstance(raw_axis, (list, tuple)) or len(raw_axis) != row_count or
                not isinstance(raw_values, (list, tuple)) or len(raw_values) != row_count or
                any(not isinstance(row, (list, tuple)) or len(row) != 1 for row in raw_values)):
            raise ValueError("record observation arrays must match its spec")
        try:
            axes = np.asarray(observation["axis"], dtype=float)
            values = np.asarray(observation["values"], dtype=float)
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ValueError("record observation must contain finite arrays") from None
        if (axes.shape != (len(observed_spec["times"]),) or
                values.shape != (len(axes), 1) or len(axes) > MAX_ROWS or
                not np.array_equal(axes, observed_spec["times"]) or
                not np.isfinite(values).all()):
            raise ValueError("record observation arrays must match its spec")
        distance = float(np.linalg.norm(_features(observed_spec) - query_feature))
        candidates.append((distance, observed_spec, axes, values[:, 0]))
    if not candidates:
        return [[0.0] for _ in canonical["times"]]
    # A single neighbor preserves observed loop branches instead of averaging
    # opposite histories; stable sorting resolves equal distances by record order.
    _, neighbor_spec, axes, values = min(candidates, key=lambda item: item[0])
    query_horizon = max(canonical["times"][-1], 0.05)
    neighbor_horizon = max(neighbor_spec["times"][-1], 0.05)
    locations = np.asarray(canonical["times"]) * neighbor_horizon / query_horizon
    prediction = np.interp(locations, axes, values).reshape(-1, 1)
    if not np.isfinite(prediction).all():
        raise ValueError("record interpolation produced nonfinite values")
    return prediction.tolist()
