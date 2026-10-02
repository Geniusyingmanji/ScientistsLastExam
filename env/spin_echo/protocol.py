"""Public instrument contract, without the private dynamics or family menu."""

import math
import numbers

import numpy as np

VERSION = "spin_echo-0.1.0-experimental"
AXIS_FIELD = "times_ms"
CHANNELS = ("magnetization_x", "magnetization_y", "magnetization_z")
SCALES = (1.0, 1.0, 1.0)
NOISE_STD = (0.002, 0.002, 0.002)


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


def validate_spec(spec):
    required = {"initial_magnetization", AXIS_FIELD}
    if not isinstance(spec, dict) or not required <= set(spec) or set(spec) - required - {"detuning_hz", "pulses"}:
        raise ValueError("expected initial_magnetization, times_ms and optional detuning_hz, pulses")
    initial = spec["initial_magnetization"]
    if not isinstance(initial, list) or len(initial) != 3:
        raise ValueError("initial_magnetization must contain three real numbers")
    initial = [number(v, -1, 1, "initial magnetization") for v in initial]
    if math.sqrt(sum(v*v for v in initial)) > 1 + 1e-12:
        raise ValueError("initial magnetization norm must not exceed 1")
    raw_times = spec[AXIS_FIELD]
    if not isinstance(raw_times, list) or not 1 <= len(raw_times) <= 129:
        raise ValueError("times_ms must contain 1..129 samples")
    times = [number(t, 0, 250, "sample time_ms") for t in raw_times]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("times_ms must be strictly increasing")
    raw_pulses = spec.get("pulses", [])
    if not isinstance(raw_pulses, list) or len(raw_pulses) > 12:
        raise ValueError("pulses must be a list of 0..12 events")
    pulses = []
    for event in raw_pulses:
        if not isinstance(event, dict) or set(event) != {"time_ms", "angle_rad", "phase_rad"}:
            raise ValueError("each pulse needs exactly time_ms, angle_rad, phase_rad")
        pulses.append({"time_ms": number(event["time_ms"], .1, times[-1], "pulse time_ms"),
                       "angle_rad": number(event["angle_rad"], -2*math.pi, 2*math.pi, "pulse angle_rad"),
                       "phase_rad": number(event["phase_rad"], -math.pi, math.pi, "pulse phase_rad")})
    if any(b["time_ms"] - a["time_ms"] < .1 - 1e-12 for a, b in zip(pulses, pulses[1:])):
        raise ValueError("pulse times must increase by at least 0.1 ms; simultaneous pulses are rejected")
    return {"initial_magnetization": initial, "detuning_hz": number(spec.get("detuning_hz", 0), -40, 40, "detuning_hz"),
            AXIS_FIELD: times, "pulses": pulses}


def example():
    return {"initial_magnetization": [1.0, 0.0, 0.0], "detuning_hz": 0.0,
            AXIS_FIELD: [0.0, 5.0, 10.0, 20.0, 39.9, 40.0, 40.1, 60.0, 80.0, 120.0, 160.0],
            "pulses": [{"time_ms": 40.0, "angle_rad": math.pi, "phase_rad": 0.0}]}


def describe():
    return {"name": "spin_echo", "version": VERSION,
            "research_prompt": "Investigate a sealed, repeatable magnetic ensemble in a rotating reference frame. Measure its vector response to preparation, waiting, calibrated rotations and a uniform frequency shift. Develop quantitative accounts, choose controls that distinguish plausible explanations, and state what your finite observations leave unresolved.",
            "channels": list(CHANNELS), "scales": list(SCALES), "noise_std": list(NOISE_STD),
            "axis": {"name": "time", "unit": "ms", "rows": "requested times_ms"},
            "units": {"magnetization": "normalized classical ensemble magnetization", "detuning_hz": "cycles per second", "pulse_angle_and_phase": "radians"},
            "semantics": [
                "Every call freshly prepares the specified initial_magnetization vector; its Euclidean norm is at most 1. Apparatus properties remain fixed within an instance. No state carries between calls.",
                "The x,y,z frame is right handed; z is the reference-field axis. Positive detuning_hz adds a known uniform phase rate: in the absence of other evolution it rotates +x toward +y at 2*pi*detuning_hz radians per second. One millisecond is 0.001 second.",
                "Each pulse is an ideal instantaneous active right-handed rotation by angle_rad about the transverse unit axis (cos(phase_rad), sin(phase_rad), 0), equally for the entire ensemble. For example a +pi/2 pulse about +x maps +y to +z. There is no pulse-width, amplitude-calibration or off-resonance pulse error in this apparatus.",
                "Pulses occur at strictly ordered times at least 0.1 ms apart. Their first time is at least 0.1 ms; zero-time and simultaneous pulses are rejected, not silently ordered or combined. A sample exactly at a pulse time reports AFTER that pulse. The initial preparation is specified directly, not implemented by an unlisted pulse.",
                "Samples do not alter the underlying trajectory. Inserting extra sample times has no physical effect. The measurement reports mean magnetization components, not individual magnetic moments or quantum projective outcomes.",
                "Independent additive Gaussian readout noise has standard deviation 0.002 on each component, including at time zero and pulse timestamps. It is not clipped; noisy values may exceed the clean vector norm. There is no process noise or quantum shot noise. Repeated measurements receive fresh noise.",
                "Longitudinal thermal recovery is neglected over this short observation window (R1=0): during waits, the z component of each magnetic component is constant. Rotations can move magnetization into or out of that direction. This is an explicit apparatus idealization, not a measured discovery. A zero initial vector stays zero in clean measurements under all allowed waits and rotations, and provides no information about the unknown response.",
                "The clean time-zero vector and the instantaneous rotation rule are assigned by the controls. Reproducing those facts alone does not identify the unknown between-pulse response. A finite set of mean-vector observations need not identify a unique microscopic ensemble."
            ],
            "schema": {"type": "object", "required": ["initial_magnetization", AXIS_FIELD],
                       "optional": {"detuning_hz": 0.0, "pulses": []}, "additional_fields": False,
                       "initial_magnetization": {"length": 3, "order": ["x", "y", "z"], "component_range": [-1, 1], "Euclidean_norm_max": 1, "norm_float_tolerance": 1e-12},
                       AXIS_FIELD: {"length": [1, 129], "range": [0, 250], "unit": "ms", "order": "strictly increasing; zero optional"},
                       "detuning_hz": {"range": [-40, 40], "unit": "Hz"},
                       "pulses": {"length": [0, 12], "required": ["time_ms", "angle_rad", "phase_rad"], "additional_fields": False,
                                  "time_ms": "at least 0.1, at most last sample; consecutive gap >=0.1 ms (1e-12 rounding tolerance)",
                                  "angle_rad_range": [-2*math.pi, 2*math.pi], "phase_rad_range": [-math.pi, math.pi]},
                       "validation": "Finite real numbers only. Booleans, unknown fields, unordered/duplicate times and oversized arrays are rejected."},
            "cost": "8 + number of samples + 3*number of pulses + ceil(last time_ms/25); maximum 183",
            "examples": [example(), {"initial_magnetization": [1.0, 0.0, 0.0], AXIS_FIELD: [0.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0]}],
            "limitations": "Synthetic classical magnetization instrument, not a calibrated NMR/MRI scanner. Ideal instantaneous rotations and negligible longitudinal recovery omit finite-pulse, diffusion, exchange, interaction-spectroscopy and heating effects. Finite-horizon response agreement does not prove a unique microscopic explanation or quantum discovery."}
