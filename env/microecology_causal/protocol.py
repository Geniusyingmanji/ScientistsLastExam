"""Public batch apparatus only; no private ecological structures or parameters."""

import math
import numbers

import numpy as np


VERSION = "microecology_causal-0.1.0-experimental"
CHANNELS = ("A", "B", "C", "nutrient", "peak-01", "peak-02", "peak-03")
SCALES = (1.0, 1.0, 1.0, 5.0, 1.0, 1.0, 1.0)
NOISE_STD = (0.002, 0.002, 0.002, 0.004, 0.004, 0.004, 0.004)


def integer(value, name, low=0, high=2**63 - 1):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral) or not low <= int(value) <= high:
        raise ValueError("%s must be an integer in [%d, %d]" % (name, low, high))
    return int(value)


def number(value, low, high, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise ValueError("%s must be a finite real number" % name)
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise ValueError("%s must be a finite real number" % name) from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError("%s must be in [%g, %g]" % (name, low, high))
    return value


def validate_spec(spec):
    if not isinstance(spec, dict) or not {"initial", "times_h"} <= set(spec) or set(spec) - {"initial", "times_h", "temperature_c", "events"}:
        raise ValueError("expected initial, times_h and optional temperature_c, events")
    initial = spec["initial"]
    if not isinstance(initial, dict) or set(initial) != {"A", "B", "C", "nutrient"}:
        raise ValueError("initial requires exactly A, B, C, nutrient")
    initial = {key: number(initial[key], 0, 10 if key == "nutrient" else 1, key) for key in ("A", "B", "C", "nutrient")}
    temperature = number(spec.get("temperature_c", 30), 20, 40, "temperature_c")
    times = spec["times_h"]
    if not isinstance(times, list) or not 1 <= len(times) <= 32:
        raise ValueError("times_h requires 1..32 times")
    times = [number(time, 0, 72, "time") for time in times]
    if any(right <= left for left, right in zip(times, times[1:])):
        raise ValueError("times_h must be strictly increasing")
    events = spec.get("events", [])
    if not isinstance(events, list) or len(events) > 4:
        raise ValueError("events requires 0..4 events")
    canonical = []
    for event in events:
        if not isinstance(event, dict) or len(event) != 2 or "time_h" not in event:
            raise ValueError("each event needs time_h and exactly one action")
        row = {"time_h": number(event["time_h"], 0, times[-1], "event time")}
        if "deplete" in event:
            depletion = event["deplete"]
            if (not isinstance(depletion, dict) or set(depletion) != {"channel", "fraction"} or
                    not isinstance(depletion["channel"], str) or depletion["channel"] not in CHANNELS[4:]):
                raise ValueError("deplete needs a public peak channel and fraction")
            row["deplete"] = {"channel": depletion["channel"], "fraction": number(depletion["fraction"], 0, 1, "depletion fraction")}
        elif "feed" in event:
            row["feed"] = number(event["feed"], 0, 3, "feed")
        elif "temperature_c" in event:
            row["temperature_c"] = number(event["temperature_c"], 20, 40, "event temperature_c")
        else:
            raise ValueError("event action must be deplete, feed or temperature_c")
        canonical.append(row)
    if any(right["time_h"] < left["time_h"] for left, right in zip(canonical, canonical[1:])):
        raise ValueError("events must be sorted by time_h")
    return {"initial": initial, "temperature_c": temperature, "times_h": times, "events": canonical}


def example():
    return {"initial": {"A": 0.05, "B": 0.05, "C": 0.05, "nutrient": 5.0},
            "temperature_c": 30.0, "times_h": [0.0, 6.0, 12.0, 18.0, 24.0, 48.0, 72.0],
            "events": [{"time_h": 12.0, "deplete": {"channel": "peak-01", "fraction": 0.8}}]}


def describe():
    return {
        "name": "microecology_causal", "version": VERSION,
        "research_prompt": "Study three unfamiliar microbial strains and three anonymous extracellular fractions. Use observations and perturbations to investigate quantitative relationships, compare explanations, and delimit what your evidence identifies.",
        "channels": list(CHANNELS), "scales": list(SCALES), "noise_std": list(NOISE_STD),
        "units": "All measured concentrations are mmol carbon/L; time is hours; temperature is Celsius.",
        "axis": {"name": "time", "unit": "h", "rows": "requested times_h"},
        "semantics": [
            "Every call starts a fresh closed batch vessel with the same fixed material properties. No clock, cells or material carry between experiments.",
            "A/B/C distinguish three strains. peak-01/02/03 are consistently labeled anonymous extracellular fractions within an instance; the labels do not reveal molecular identity or biological role.",
            "Initial extracellular fractions are zero. A strain with zero initial inoculum remains absent. Initial living biomass and nutrient are the only initial carbon pools.",
            "Deterministic dynamics conserve total carbon including an unobserved inert pool. Feed adds carbon and selective depletion removes carbon; the seven measured channels alone need not sum to the total carbon.",
            "Measurement noise is independent additive Gaussian noise with the stated standard deviations, clipped at zero. There is no process noise. Noisy measured sums need not conserve carbon.",
            "Events occur before measurements at the same time. Equal-time events execute in the supplied order. Depletion removes only the named extracellular fraction. Feed adds nutrient with negligible volume change. Temperature changes persist until changed again.",
            "Observations do not perturb the vessel. Adding extra observation times does not change the underlying trajectory."
        ],
        "schema": {
            "type": "object", "required": ["initial", "times_h"], "optional": ["temperature_c", "events"], "additional_fields": False,
            "initial": {"required": ["A", "B", "C", "nutrient"], "additional_fields": False,
                        "A": [0, 1], "B": [0, 1], "C": [0, 1], "nutrient": [0, 10], "unit": "mmol carbon/L"},
            "temperature_c": {"range": [20, 40], "default": 30},
            "times_h": {"type": "number array", "length": [1, 32], "range": [0, 72], "order": "strictly increasing"},
            "events": {"type": "object array", "length": [0, 4], "default": [], "order": "nondecreasing time_h",
                       "time_h": "in [0, last requested observation]", "one_action_only": True,
                       "deplete": {"required": ["channel", "fraction"], "additional_fields": False,
                                   "channel": list(CHANNELS[4:]), "fraction": [0, 1]},
                       "feed": {"range": [0, 3], "unit": "mmol carbon/L added nutrient"},
                       "temperature_c": {"range": [20, 40]}},
            "validation": "Finite real numbers only; booleans, unknown fields and oversized arrays are rejected."
        },
        "examples": [example(), {"initial": {"A": 0.1, "B": 0.04, "C": 0.08, "nutrient": 3},
                                  "temperature_c": 28, "times_h": [0, 8, 16, 24, 48],
                                  "events": [{"time_h": 16, "feed": 1}]}],
        "cost": "8 + number of times + 2*number of events + ceil(last time_h / 12)",
        "limitations": "Experimental synthetic carbon-balanced ecology, not calibrated organisms. No direct fraction additions, cell additions after inoculation, supernatant transfers or molecular identity measurements are exposed. A predictive fit or one replicated effect does not certify a unique causal mechanism."
    }
