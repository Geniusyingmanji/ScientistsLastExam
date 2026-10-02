"""Public instrument contract, without a hidden circuit menu."""

import math
import numbers

import numpy as np

VERSION = "electrical_impedance-0.1.0"
CHANNELS = ("voltage_real", "voltage_imag")
SCALES = (1.0, 1.0)
NOISE_STD = (.001, .001)
AXIS_FIELD = "frequencies_hz"


def integer(value, name, low=0, high=2**63-1):
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
    if not isinstance(spec, dict) or set(spec) != {AXIS_FIELD, "source_ohm", "load_ohm", "amplitude_v"}:
        raise ValueError("expected exactly frequencies_hz, source_ohm, load_ohm and amplitude_v")
    frequencies = spec[AXIS_FIELD]
    if not isinstance(frequencies, list) or not 1 <= len(frequencies) <= 65:
        raise ValueError("frequencies_hz must be a list of 1..65 entries")
    frequencies = [number(f, 2, 5000, "frequency") for f in frequencies]
    if any(b <= a for a, b in zip(frequencies, frequencies[1:])):
        raise ValueError("frequencies_hz must be strictly increasing")
    return {AXIS_FIELD: frequencies,
            "source_ohm": number(spec["source_ohm"], 100, 2000, "source resistance"),
            "load_ohm": number(spec["load_ohm"], 200, 20000, "load resistance"),
            "amplitude_v": number(spec["amplitude_v"], .25, 2, "source peak voltage")}


def example():
    return {AXIS_FIELD: [2., 10., 30., 100., 300., 1000., 3000., 5000.],
            "source_ohm": 500., "load_ohm": 5000., "amplitude_v": 1.}


def describe():
    return {
        "name": "electrical_impedance", "version": VERSION,
        "research_prompt": "Investigate a sealed passive linear electrical one-port. Measure its steady-state response, develop quantitative accounts of its frequency dependence, and test where those accounts succeed or fail as frequency and external apparatus settings change. Distinct internal circuits can have identical terminal behavior.",
        "channels": list(CHANNELS), "scales": list(SCALES), "noise_std": list(NOISE_STD),
        "axis": {"name": "frequency", "unit": "Hz", "rows": "requested frequencies_hz"},
        "units": {"voltage_real": "V", "voltage_imag": "V", "source_ohm": "ohm", "load_ohm": "ohm", "amplitude_v": "V peak"},
        "semantics": [
            "An ideal voltage source drives a known series source_ohm resistor, then the black-box terminal. A known load_ohm resistor connects that terminal to ground in parallel with the black box. The source, load and black box share the same ground; measured voltage is terminal relative to ground. The voltmeter draws no current.",
            "The source phasor is real positive amplitude_v. Physical voltage is Re(V*exp(+i*2*pi*f*t)); channels report the real and imaginary parts of the terminal phasor, using peak, not RMS, amplitudes. A negative imaginary part means terminal voltage lags this reference.",
            "Each row is an independent sinusoidal steady-state experiment, with no switching transient or carried state. Frequencies and measurement order do not perturb the device. Device properties remain fixed across calls.",
            "The black box is passive, stable and linear over the allowed settings. It contains no independent sources. Doubling the applied amplitude therefore doubles the clean phasor; this publicly assigned scaling alone is not discovery of the device's frequency dependence.",
            "Real and imaginary measurements have independent additive Gaussian noise, standard deviation 0.001 V each, without clipping. Noise is independent across rows, channels and repeated experimental readings. There is no process noise.",
            "Explore frequency, source resistance, external parallel load and source amplitude within the stated ranges. Changing the external load changes the voltage divider and need not distinguish devices that already have the same terminal impedance. Known apparatus changes alone are not evidence for an internal mechanism.",
            "Finite noisy frequency measurements may fail to distinguish different devices. Even exact full-band terminal behavior need not uniquely determine an internal topology. No time-domain control or response is exposed by this prototype."
        ],
        "schema": {"type": "object", "required": [AXIS_FIELD, "source_ohm", "load_ohm", "amplitude_v"], "additional_fields": False,
                   AXIS_FIELD: {"range": [2, 5000], "length": [1, 65], "order": "strictly increasing", "unit": "Hz"},
                   "source_ohm": {"range": [100, 2000]}, "load_ohm": {"range": [200, 20000]},
                   "amplitude_v": {"range": [.25, 2]},
                   "validation": "Finite real numbers only; booleans, unknown fields, repeated frequencies and oversized arrays are rejected."},
        "cost": "8 + 2*number of frequencies + ceil(log10(last frequency / first frequency)); maximum 142",
        "examples": [example()],
        "limitations": "An ideal lumped-element numerical apparatus with a finite frequency range. It does not model component tolerances drifting in time, parasitics beyond its hidden construction, nonlinear heating, a validated physical instrument, or unique topology recovery."
    }
