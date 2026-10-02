"""Public-record neighbor interpolation; no equations, structures or private state."""

import numpy as np

from .protocol import CHANNELS, validate_spec


def _feature(spec):
    initial = spec["initial"]
    inputs = [initial[key] for key in ("A", "B", "C")] + [initial["nutrient"] / 5, spec["temperature_c"] / 10]
    event_features = np.zeros(8)
    for event in spec["events"]:
        timing = 1.0 - event["time_h"] / 144.0
        if "deplete" in event:
            index = CHANNELS[4:].index(event["deplete"]["channel"])
            event_features[index] += event["deplete"]["fraction"] * timing
            event_features[index + 3] += event["time_h"] / 72.0
        elif "feed" in event:
            event_features[6] += event["feed"] * timing / 3.0
        else:
            event_features[7] += (event["temperature_c"] - spec["temperature_c"]) * timing / 10.0
    return np.concatenate((inputs, event_features))


def baseline(records, spec):
    query = validate_spec(spec)
    if not isinstance(records, (list, tuple)) or len(records) > 256:
        raise ValueError("records must contain at most 256 public experiments")
    if not records:
        rows = []
        for time in query["times_h"]:
            initial = [query["initial"][key] for key in ("A", "B", "C", "nutrient")] + [0.0] * 3
            initial[3] += sum(event["feed"] for event in query["events"] if "feed" in event and event["time_h"] <= time)
            rows.append(initial)
        return rows
    options = []
    for record in records:
        if not isinstance(record, dict) or not {"spec", "observation"} <= set(record):
            raise ValueError("records require spec and observation")
        observed = validate_spec(record["spec"])
        observation = record["observation"]
        if not isinstance(observation, dict) or observation.get("channels") != list(CHANNELS):
            raise ValueError("record channel mismatch")
        raw_values = observation.get("values")
        raw_axis = observation.get("axis")
        if (not isinstance(raw_axis, list) or len(raw_axis) != len(observed["times_h"]) or
                not isinstance(raw_values, list) or len(raw_values) != len(observed["times_h"]) or
                any(not isinstance(row, list) or len(row) != 7 for row in raw_values)):
            raise ValueError("record matrix shape mismatch")
        try:
            values = np.asarray(raw_values, dtype=float)
            axis = np.asarray(observation["axis"], dtype=float)
        except (ValueError, TypeError, OverflowError, KeyError):
            raise ValueError("record arrays must be finite numbers") from None
        if not np.isfinite(values).all() or not np.array_equal(axis, observed["times_h"]):
            raise ValueError("record arrays do not match its public spec")
        options.append((float(np.linalg.norm(_feature(query) - _feature(observed))), axis, values))
    _, axis, values = min(options, key=lambda item: item[0])
    prediction = np.asarray([np.interp(query["times_h"], axis, values[:, j]) for j in range(7)]).T
    if not np.isfinite(prediction).all():
        raise ValueError("public record interpolation failed")
    return prediction.tolist()
