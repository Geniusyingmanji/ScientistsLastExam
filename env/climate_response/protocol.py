"""Apparatus-only public controls and measurement contract."""

import math
import numbers

import numpy as np

VERSION = "climate_response-0.1.0-experimental"
AXIS_FIELD = "times_years"
CHANNELS = ("surface_temperature_anomaly_k", "toa_imbalance_w_m2")
SCALES = (4.0, 8.0)
NOISE_STD = (0.06, 0.14)


def integer(value, name, low=0, high=2**63-1):
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
        raise ValueError("%s must lie in [%g, %g]" % (name, low, high))
    return value


def validate_spec(spec):
    if not isinstance(spec, dict) or "forcing_w_m2" not in spec or set(spec) - {"forcing_w_m2", AXIS_FIELD}:
        raise ValueError("expected forcing_w_m2 and optional times_years only")
    raw = spec["forcing_w_m2"]
    if not isinstance(raw, list) or not 1 <= len(raw) <= 160:
        raise ValueError("forcing_w_m2 must contain 1..160 annual values")
    forcing = [number(v, -1, 8, "forcing_w_m2 value") for v in raw]
    raw_times = spec.get(AXIS_FIELD, list(range(1, len(forcing)+1)))
    if not isinstance(raw_times, list) or not 1 <= len(raw_times) <= 160:
        raise ValueError("times_years must contain 1..160 samples")
    # Whole-valued floats are legal JSON coordinates, matching other time axes.
    times = [number(v, 1, len(forcing), "sample year") for v in raw_times]
    if any(t != int(t) for t in times):
        raise ValueError("sample years must be whole years")
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("times_years must be strictly increasing")
    if times[-1] != len(forcing):
        raise ValueError("last sample year must equal the forcing history length")
    return {"forcing_w_m2": forcing, AXIS_FIELD: [int(t) for t in times]}


def example():
    return {"forcing_w_m2": [4.0]*20+[0.0]*20,
            AXIS_FIELD: [1, 2, 5, 10, 20, 21, 25, 30, 40]}


def describe():
    return {
        "name": "climate_response", "version": VERSION,
        "research_prompt": "Investigate a repeatable synthetic climate apparatus. Choose external heating histories, observe surface warming and net energy uptake, develop quantitative explanations, and test predictions on fresh experiments. State what the measurements do and do not identify.",
        "channels": list(CHANNELS), "scales": list(SCALES), "noise_std": list(NOISE_STD),
        "axis": {"name": "time", "unit": "year", "rows": "requested times_years"},
        "units": {CHANNELS[0]: "kelvin relative to the freshly prepared reference", CHANNELS[1]: "W m^-2, positive into the system", "forcing_w_m2": "externally commanded W m^-2"},
        "semantics": [
            "Each call starts a new preparation at the same zero-temperature-anomaly reference. All internal thermal stores start at this reference; apparatus properties stay fixed within an instance. There is no state carried between calls.",
            "forcing_w_m2[i] is held constant during year interval (i, i+1], with zero-based array indexing. A row at year k reports temperature at the end of that interval and net energy uptake under forcing_w_m2[k-1], before the next annual switch. A switch can change net energy uptake immediately; temperature is continuous.",
            "You control the commanded forcing history, not the actual measured net energy uptake. The relation between the command and the response is unknown. Net uptake and surface temperature are distinct measured quantities; neither is assigned directly by a command at positive time.",
            "Samples are nondestructive and do not affect evolution. Extra sample years do not alter existing clean outputs. The last requested year must equal the history length, preventing unused future commands.",
            "Independent zero-mean additive Gaussian readout noise has standard deviation 0.06 K for temperature and 0.14 W m^-2 for net energy uptake, independently across rows, channels and repeated calls. Values are not clipped. There is no stochastic process forcing.",
            "The instrument measures annual endpoints only, not annual means. It does not reveal internal thermal-store temperatures or total stored heat. Time-zero preparation is known but is not an available measurement row."
        ],
        "schema": {"type": "object", "required": ["forcing_w_m2"], "additional_fields": False,
                   "forcing_w_m2": {"length": [1, 160], "value_range": [-1, 8], "interval_years": 1},
                   AXIS_FIELD: {"optional": True, "default": "all annual endpoints 1..history length", "length": [1, 160], "range": "1..history length", "order": "strictly increasing whole years", "last": "must equal history length"},
                   "validation": "Finite real numbers; booleans, unknown fields, duplicate/fractional times and oversized histories are rejected."},
        "cost": "8 + number of measured years + ceil(history length/10); maximum 184",
        "examples": [example(), {"forcing_w_m2": [1.0]*10, AXIS_FIELD: [1, 2, 5, 10]}],
        "limitations": "A controlled low-dimensional synthetic thermal emulator, not a calibrated model of Earth. Annual finite-horizon observations can admit multiple effective explanations. Successful fresh predictions do not by themselves identify unique internal structure or real-world climate sensitivity."
    }
