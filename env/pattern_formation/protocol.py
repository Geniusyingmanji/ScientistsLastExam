"""Public instrument contract, without private dynamics or family choices."""

import math
import numbers

import numpy as np

VERSION = "pattern_formation-0.1.0-experimental"
GRID_SIZE = 64
PROBE_COUNT = 16
CHANNELS = tuple("probe_%02d" % index for index in range(PROBE_COUNT))
SCALES = (1.0,) * PROBE_COUNT
NOISE_STD = (0.002,) * PROBE_COUNT


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
    if not isinstance(spec, dict) or set(spec) != {"length", "drive", "initial", "times"}:
        raise ValueError("expected exactly length, drive, initial and times")
    length = number(spec["length"], 12, 32, "ring length")
    drive = number(spec["drive"], -.4, .4, "drive")
    initial = spec["initial"]
    if not isinstance(initial, dict) or set(initial) != {"mean", "modes"}:
        raise ValueError("initial needs exactly mean and modes")
    mean = number(initial["mean"], -.2, .2, "initial mean")
    if not isinstance(initial["modes"], list) or len(initial["modes"]) > 3:
        raise ValueError("initial modes must be a list of at most three entries")
    modes = []
    for entry in initial["modes"]:
        if not isinstance(entry, dict) or set(entry) != {"mode", "amplitude", "phase"}:
            raise ValueError("a mode needs exactly mode, amplitude and phase")
        modes.append({"mode": integer(entry["mode"], "mode", 1, 8),
                      "amplitude": number(entry["amplitude"], -.3, .3, "amplitude"),
                      "phase": number(entry["phase"], -math.pi, math.pi, "phase")})
    if len({entry["mode"] for entry in modes}) != len(modes):
        raise ValueError("mode numbers must be unique")
    if sum(abs(entry["amplitude"]) for entry in modes) > .3 + 1e-12:
        raise ValueError("total absolute mode amplitude must not exceed 0.3")
    times = spec["times"]
    if not isinstance(times, list) or not 1 <= len(times) <= 33:
        raise ValueError("times must be a list with 1..33 entries")
    times = [number(t, 0, 60, "sample time") for t in times]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("times must be strictly increasing")
    return {"length": length, "drive": drive, "initial": {"mean": mean, "modes": sorted(modes, key=lambda entry: entry["mode"])}, "times": times}


def initial_values(spec, points=PROBE_COUNT):
    """Assigned sinusoidal reset evaluated at fixed fractional positions j/points."""
    theta = 2 * np.pi * np.arange(points) / points
    values = np.full(points, spec["initial"]["mean"], dtype=float)
    for mode in spec["initial"]["modes"]:
        values += mode["amplitude"] * np.sin(mode["mode"] * theta + mode["phase"])
    return values


def example():
    return {"length": 24., "drive": 0., "initial": {"mean": 0., "modes": [
        {"mode": 3, "amplitude": .08, "phase": 0.}, {"mode": 4, "amplitude": .06, "phase": .5}]},
            "times": [0., .25, 1., 2., 4., 8., 16., 30., 60.]}


def describe():
    return {
        "name": "pattern_formation", "version": VERSION,
        "research_prompt": "Investigate a scalar field in a closed periodic ring. Set the ring length, a uniform drive and a spatial initial pattern, then observe its evolution. Study when patterns grow, decay or persist, compare quantitative explanations and test the conditions under which your predictions remain reliable.",
        "channels": list(CHANNELS), "scales": list(SCALES), "noise_std": list(NOISE_STD),
        "axis": {"name": "time", "unit": "T", "rows": "requested times"},
        "units": {"field": "U", "length": "L", "time": "T", "drive": "dimensionless", "meaning": "Arbitrary apparatus units; not calibrated physical fluid or biological units."},
        "probe_positions": {"fractional_positions": [j / PROBE_COUNT for j in range(PROBE_COUNT)], "physical_position": "x_j=length*j/16; probe_00 stays at the apparatus origin"},
        "semantics": [
            "Every experiment resets the entire field at time zero. The properties of an instance are fixed across calls; no field state carries over. Ring length and drive remain constant during each run.",
            "The ring has periodic boundary conditions. Internally it is a fixed 64-site numerical world; the 16 probes read every fourth site. Changing length stretches this coordinate grid and keeps probe positions at the same fractions of the circumference.",
            "The reset is u(x,0)=mean+sum(amplitude*sin(2*pi*mode*x/length+phase)). A mode is an integer number of periods around the ring; the specified mean is the spatial average at reset only. This quantity need not be conserved subsequently.",
            "The clean time-zero readings are assigned by the initial controls. Predicting them alone is not evidence that an evolution law was discovered. Different initial modes can agree at the probe positions while differing between probes.",
            "The evolution is deterministic. Measurements do not perturb it, and adding sample times does not change it. No stochastic process excites an exactly zero reset. Whether a zero field remains zero must be investigated.",
            "Each probe reading has independent additive Gaussian noise with standard deviation 0.002 U, without clipping; the noise is independent across probes, times and repetitions. There is no process noise. Readings may be negative.",
            "The coordinate origin is fixed to the apparatus. Translating an initial pattern changes its position relative to that origin. Do not assume translation symmetry or that a visible persistent pattern proves spontaneous organization.",
            "There are no mid-run interventions. Compare experiments with different drive, ring length, reset mean or sinusoidal modes. Sparse probe measurements need not uniquely identify hidden spatial structure."
        ],
        "schema": {"type": "object", "required": ["length", "drive", "initial", "times"], "additional_fields": False,
                   "length": {"range": [12, 32], "unit": "L"}, "drive": {"range": [-.4, .4]},
                   "initial": {"required_fields": ["mean", "modes"], "additional_fields": False, "mean": {"range": [-.2, .2]},
                               "modes": {"type": "object array", "length": [0, 3], "required_fields": ["mode", "amplitude", "phase"], "additional_fields": False,
                                         "mode": "unique integers 1..8", "amplitude": {"range": [-.3, .3]}, "phase": {"range": [-math.pi, math.pi], "unit": "radians"}, "sum_absolute_amplitudes_maximum": .3}},
                   "times": {"length": [1, 33], "range": [0, 60], "order": "strictly increasing; time zero optional"},
                   "validation": "Finite real numbers only; booleans, unknown fields, repeated modes and oversized arrays are rejected."},
        "cost": "8 + number of requested times + 2*number of initial modes + ceil(last time / 4)",
        "examples": [example(), {"length": 20., "drive": -.3, "initial": {"mean": 0., "modes": []}, "times": [0., 1., 5., 20., 60.]}],
        "limitations": "A phenomenological numerical laboratory. It is not a high-fidelity biological or fluid simulation, a validated continuum limit or a certification that a mechanism is identifiable from finite observations."
    }
