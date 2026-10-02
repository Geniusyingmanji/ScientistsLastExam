"""Public apparatus specification; contains no instance dynamics or family menu."""

import math
import numbers

import numpy as np


CHANNELS = ("response",)
SCALES = (1.0,)
NOISE_STD = (0.006,)
VERSION = "hysteresis_material-0.1.0"
RESET_SECONDS = 300.0
FIELD_LIMIT = 1.5
MAX_TIME = 3600.0
MAX_ROWS = 129
MAX_KNOTS = 20
MIN_SEGMENT = 0.05


def number(value, name, lower, upper):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise ValueError("%s must be a finite real number" % name)
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise ValueError("%s must be a finite real number" % name) from None
    if not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError("%s must be in [%g, %g]" % (name, lower, upper))
    return value


def sequence(value, name, low, high):
    if not isinstance(value, (list, tuple)) or not low <= len(value) <= high:
        raise ValueError("%s must be an array of length %d to %d" % (name, low, high))
    return value


def integer(value, name, low, high):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral):
        raise ValueError("%s must be an integer" % name)
    if not low <= int(value) <= high:
        raise ValueError("%s must be in [%d, %d]" % (name, low, high))
    return int(value)


def validate_spec(spec):
    fields = {"reset", "preparation", "protocol", "times"}
    if not isinstance(spec, dict) or set(spec) != fields:
        raise ValueError("spec must contain exactly reset, preparation, protocol, times")
    reset = spec["reset"]
    if not isinstance(reset, str) or reset not in ("negative", "positive"):
        raise ValueError("reset must be negative or positive")
    times = [number(t, "times entry", 0.0, MAX_TIME)
             for t in sequence(spec["times"], "times", 1, MAX_ROWS)]
    if any(right <= left for left, right in zip(times, times[1:])):
        raise ValueError("times must be strictly increasing")
    preparation = []
    for step in sequence(spec["preparation"], "preparation", 0, 6):
        if not isinstance(step, dict) or set(step) != {"field", "duration"}:
            raise ValueError("each preparation step must contain exactly field, duration")
        preparation.append({"field": number(step["field"], "preparation field", -FIELD_LIMIT, FIELD_LIMIT),
                            "duration": number(step["duration"], "preparation duration", MIN_SEGMENT, 300.0)})
    if sum(step["duration"] for step in preparation) > 600.0:
        raise ValueError("total preparation duration must be at most 600 s")
    protocol = []
    for knot in sequence(spec["protocol"], "protocol", 1, MAX_KNOTS):
        if not isinstance(knot, dict) or set(knot) != {"time", "field"}:
            raise ValueError("each protocol knot must contain exactly time, field")
        protocol.append({"time": number(knot["time"], "protocol time", 0.0, MAX_TIME),
                         "field": number(knot["field"], "protocol field", -FIELD_LIMIT, FIELD_LIMIT)})
    if protocol[0]["time"] != 0.0:
        raise ValueError("the first protocol knot must be at time 0")
    if any(right["time"] - left["time"] < MIN_SEGMENT - 1e-12
           for left, right in zip(protocol, protocol[1:])):
        raise ValueError("protocol knot times must increase by at least 0.05 s")
    if protocol[-1]["time"] > times[-1]:
        raise ValueError("all protocol knots must occur by the last requested observation")
    return {"reset": reset, "preparation": preparation, "protocol": protocol, "times": times}


def example():
    return {"reset": "negative", "preparation": [],
            "protocol": [{"time": 0.0, "field": -1.2},
                         {"time": 30.0, "field": 1.2},
                         {"time": 60.0, "field": -1.2}],
            "times": [0.0, 5.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0]}


def describe():
    return {
        "name": "hysteresis_material", "version": VERSION,
        "description": "A repeatable field-controlled material experiment. Infer how response depends on the field history, preparation, dwell duration and sweep rate.",
        "channels": list(CHANNELS), "channel_units": ["normalized response unit"],
        "axis": {"name": "time", "unit": "s", "rows": "requested times, measured after preparation"},
        "scales": list(SCALES), "noise_std": list(NOISE_STD),
        "noise": "Independent additive Gaussian measurement noise in the response channel; no clipping or process noise. The ideal response lies within [-2.5, 2.5].",
        "cost": "One unit per valid experiment. Every call starts a fresh experiment with the same fixed material and a new reset history.",
        "apparatus": {
            "field_unit": "normalized field unit",
            "reset": "Each call begins from the same reproducible reference condition, then holds the field at -1.5 (negative reset) or +1.5 (positive reset) for exactly 300 s. This specifies a fixed history, not an assertion of exact equilibrium or an assigned numerical response.",
            "preparation": "After reset, apply the listed constant-field steps in order. Each step changes the field immediately and holds it for its duration. This time is before the observation clock starts.",
            "protocol": "At t=0 apply the first field immediately. Interpolate the field linearly between successive knots; hold the final field thereafter. Equal neighboring fields make a dwell. Changing direction makes a reversal. Field changes never directly assign the measured response.",
            "observation": "Observe one material response; the applied field is a control, not a measured output. Response is continuous through all field changes. The t=0 response is the result of reset and preparation, before any subsequent evolution.",
            "repeatability": "Material properties remain fixed within an instance. No state is carried between calls. Reusing an observation time or adding later observation times does not change the underlying earlier trajectory.",
            "resolution": "Protocol segments must last at least 0.05 s; observations may be requested at any strictly increasing times within the legal horizon."
        },
        "schema": {
            "type": "object", "required": ["reset", "preparation", "protocol", "times"], "additional_fields": False,
            "reset": {"type": "string", "enum": ["negative", "positive"]},
            "preparation": {"type": "object array", "length": [0, 6], "required": ["field", "duration"],
                            "additional_fields": False, "field": {"range": [-1.5, 1.5], "unit": "normalized field unit"},
                            "duration": {"range": [0.05, 300.0], "unit": "s"}, "total_duration_max_s": 600.0},
            "protocol": {"type": "object array", "length": [1, MAX_KNOTS], "required": ["time", "field"],
                         "additional_fields": False, "field": {"range": [-1.5, 1.5], "unit": "normalized field unit"},
                         "time": {"range": [0.0, MAX_TIME], "unit": "s"}, "first_time": 0.0,
                         "minimum_time_gap_s": MIN_SEGMENT, "last_time_max": "last requested observation time"},
            "times": {"type": "number array", "length": [1, MAX_ROWS], "range": [0.0, MAX_TIME],
                      "unit": "s", "order": "strictly increasing"},
            "validation": "All numeric entries must be finite real numbers, not booleans. Unknown fields are rejected."
        },
        "examples": [example(), {"reset": "positive", "preparation": [{"field": 0.0, "duration": 120.0}],
                                  "protocol": [{"time": 0.0, "field": 0.0}],
                                  "times": [0.0, 0.5, 2.0, 10.0, 60.0, 180.0]}],
        "discovery": "Compare preparations, opposite field histories, long dwells, sweep durations and reversal paths. A loop seen at one finite sweep rate alone does not establish persistent memory. Quantitative prediction does not by itself certify a unique mechanism."
    }
