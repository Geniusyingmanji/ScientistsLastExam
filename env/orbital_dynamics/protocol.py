"""Public apparatus contract. No private force law or instance generation."""

import math
import numbers

import numpy as np


VERSION = "orbital_dynamics-0.1.0-experimental"
CHANNELS = ("x", "y", "vx", "vy")
SCALES = (2.0, 2.0, 1.5, 1.5)
NOISE_STD = (0.0015, 0.0015, 0.002, 0.002)
RESOLUTION_RADIUS = 0.25


def integer(value, name, low=0, high=2**63 - 1):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral) or not low <= int(value) <= high:
        raise ValueError("%s must be an integer in [%d, %d]" % (name, low, high))
    return int(value)


def number(value, low, high, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise ValueError("%s must be a finite real number" % name)
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ValueError("%s must be a finite real number" % name) from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError("%s must lie in [%g, %g]" % (name, low, high))
    return value


def vector(value, bound, name):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("%s must contain two numbers" % name)
    result = [number(v, -bound, bound, name) for v in value]
    if math.hypot(*result) > bound + 1e-12:
        raise ValueError("%s Euclidean norm exceeds %g" % (name, bound))
    return result


def validate_spec(spec):
    if (not isinstance(spec, dict) or not {"position", "velocity", "times"} <= set(spec) or
            set(spec) - {"position", "velocity", "times", "impulses"}):
        raise ValueError("expected position, velocity, times and optional impulses")
    position = vector(spec["position"], 2.0, "position")
    if math.hypot(*position) < 0.75 - 1e-12:
        raise ValueError("initial position radius must be at least 0.75")
    velocity = vector(spec["velocity"], 1.5, "velocity")
    times = spec["times"]
    if not isinstance(times, list) or not 1 <= len(times) <= 65:
        raise ValueError("times must contain 1..65 samples")
    times = [number(t, 0, 12, "sample time") for t in times]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("times must be strictly increasing")
    raw = spec.get("impulses", [])
    if not isinstance(raw, list) or len(raw) > 3:
        raise ValueError("impulses must contain 0..3 events")
    impulses = []
    for event in raw:
        if not isinstance(event, dict) or set(event) != {"time", "delta_v"}:
            raise ValueError("each impulse requires exactly time and delta_v")
        t = number(event["time"], 0, times[-1], "impulse time")
        if t <= 0:
            raise ValueError("impulse time must be strictly positive")
        impulses.append({"time": t, "delta_v": vector(event["delta_v"], 0.5, "delta_v")})
    if any(b["time"] <= a["time"] for a, b in zip(impulses, impulses[1:])):
        raise ValueError("impulse times must be strictly increasing")
    if sum(math.hypot(*event["delta_v"]) for event in impulses) > 0.8 + 1e-12:
        raise ValueError("sum of impulse magnitudes must not exceed 0.8")
    return {"position": position, "velocity": velocity, "times": times, "impulses": impulses}


def example():
    return {"position": [1.2, 0.0], "velocity": [0.0, 0.8],
            "times": [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0],
            "impulses": [{"time": 3.0, "delta_v": [0.18, -0.08]}]}


def describe():
    return {
        "name": "orbital_dynamics", "version": VERSION,
        "research_prompt": "Investigate a planar test particle in an unfamiliar, fixed, isotropic apparatus centered at the origin. Infer quantitative motion laws from trajectories, design perturbations that compare explanations, and state the range of conditions your evidence supports.",
        "channels": list(CHANNELS), "scales": list(SCALES), "noise_std": list(NOISE_STD),
        "units": {"x": "L", "y": "L", "vx": "L/T", "vy": "L/T", "time": "T",
                  "meaning": "L and T are apparatus units, not astronomical units or seconds."},
        "axis": {"name": "time", "unit": "T", "rows": "requested times"},
        "semantics": [
            "Every experiment resets one noninteracting test particle at time zero to the specified position and velocity. The apparatus properties stay fixed within an instance; no particle state carries between calls.",
            "The Cartesian frame is inertial and centered at the apparatus origin. It has no preferred in-plane orientation. Motion is deterministic between interventions. A finite center resolution of 0.25 L removes singular behavior at the origin; trajectories may pass through this region.",
            "At an impulse, position is continuous and delta_v is added exactly to the current Cartesian velocity. Impulses do not reset other state. A sample at the same time reports the state AFTER the impulse. Impulses are strictly positive-time events.",
            "Measurements do not alter motion. Adding sample times does not alter the trajectory. All four channels are always observed; acceleration, force and energy are not directly measured.",
            "Independent additive Gaussian measurement noise uses the stated per-channel standard deviations without clipping. There is no process noise. Noise also applies at time zero and at impulse times.",
            "The time-zero clean state is assigned by the controls. The instantaneous velocity jump at a specified impulse is also assigned by the controls. Reproducing these facts alone is not evidence of an inferred motion law. A post-impulse absolute velocity still depends on the unknown pre-impulse trajectory.",
            "The finite time horizon bounds an experiment, not the particle's radius throughout it. Both returning and outward-moving trajectories can occur. No boundary wall, trajectory clipping or escape termination is imposed."
        ],
        "schema": {
            "type": "object", "required": ["position", "velocity", "times"], "optional": ["impulses"], "additional_fields": False,
            "position": {"type": "two-number Cartesian array", "unit": "L", "Euclidean_norm": [0.75, 2.0]},
            "velocity": {"type": "two-number Cartesian array", "unit": "L/T", "Euclidean_norm": [0, 1.5]},
            "times": {"type": "number array", "length": [1, 65], "range": [0, 12], "unit": "T", "order": "strictly increasing; time zero optional"},
            "impulses": {"type": "object array", "length": [0, 3], "default": [], "required_fields": ["time", "delta_v"], "additional_fields": False,
                         "time": "strictly increasing, strictly positive, at most last requested time", "delta_v": {"type": "two-number Cartesian array", "unit": "L/T", "maximum_norm": 0.5}, "sum_of_norms_maximum": 0.8},
            "validation": "Only finite real numbers; booleans, unknown fields, zero-time impulses and oversized arrays are rejected."
        },
        "examples": [example(), {"position": [1.6, 0], "velocity": [0, -0.6], "times": [0, 0.5, 1, 2, 4, 6, 8], "impulses": []}],
        "cost": "8 + number of samples + 4*number of impulses + ceil(last sample time / 2)",
        "limitations": "Synthetic center-of-influence laboratory, not a validated celestial ephemeris. A finite set of trajectories need not uniquely identify its governing law; check extrapolation and alternative accounts."
    }
