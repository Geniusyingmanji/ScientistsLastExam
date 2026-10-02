"""Private design-only pure schema. Contains no scattering implementation."""
from copy import deepcopy
import math
import random

NAME = "optical_diffraction"
STATUS = "private_unregistered_prototype"
AXIS_FIELD = "angles_rad"
CHANNELS = ["normalized_intensity"]
SCALES = [1.0]
NOISE_STD = [0.002]


def _number(value, low, high, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(field + " must be a JSON number")
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(field + " must be finite") from exc
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(field + " out of bounds")
    return result


def normalize_spec(spec):
    if not isinstance(spec, dict):
        raise ValueError("spec must be an object")
    if not {"angles_rad", "wavelength_um"} <= set(spec) or not set(spec) <= {"angles_rad", "wavelength_um", "contrast_b"}:
        raise ValueError("missing or unknown fields")
    raw = spec["angles_rad"]
    if not isinstance(raw, list) or not 1 <= len(raw) <= 65:
        raise ValueError("angles_rad must contain 1 to 65 angles")
    angles = [_number(x, -.4, .4, "angles_rad") for x in raw]
    if any(right <= left for left, right in zip(angles, angles[1:])):
        raise ValueError("angles_rad must be strictly increasing")
    return {
        "angles_rad": angles,
        "wavelength_um": _number(spec["wavelength_um"], .5, 1.5, "wavelength_um"),
        "contrast_b": _number(spec.get("contrast_b", 1), -1, 1, "contrast_b"),
    }


def cost(spec):
    return 8 + len(normalize_spec(spec)[AXIS_FIELD])


def public_description():
    return {
        "name": NAME,
        "status": STATUS,
        "axis_field": AXIS_FIELD,
        "axis_unit": "rad",
        "axis_kind": "angle",
        "channels": list(CHANNELS),
        "scales": list(SCALES),
        "noise_std": list(NOISE_STD),
        "noise_model": "iid additive Gaussian instrument noise, zero bias, no clipping; not shot noise",
        "normalization": "dimensionless intensity relative to a calibrated unit-amplitude point scatterer at the same angle and wavelength",
        "model": "At most seven fixed, weak scalar point scatterers; coherent single scattering in the far field; unknown positive normalized real amplitudes and A/B actuator tags.",
        "actuator": "contrast_b attenuates B amplitude by its magnitude and applies a pi phase inversion when negative; it does not create gain or negative absorption",
        "known_facts": [
            "q=(2*pi/wavelength_um)*sin(angles_rad), in inverse micrometres",
            "intensity is even in q and invariant under a common translation or reflection",
            "same absolute q and contrast has the same clean response",
            "zero angle with contrast_b=1 has clean normalized intensity one",
            "intensity is quadratic in contrast_b with unknown q-dependent coefficients",
        ],
        "spec_fields": {
            "angles_rad": {"required": True, "type": "strictly increasing array", "min_items": 1, "max_items": 65, "minimum": -.4, "maximum": .4},
            "wavelength_um": {"required": True, "type": "number", "minimum": .5, "maximum": 1.5, "unit": "micrometre"},
            "contrast_b": {"required": False, "type": "number", "minimum": -1, "maximum": 1, "default": 1},
        },
        "cost": "8 + number of angles",
    }


def public_panel(panel_seed):
    """Public-domain-only proposed panel; no instance/label access or responses."""
    if type(panel_seed) is not int or not 0 <= panel_seed < 2**63:
        raise ValueError("panel_seed must be a nonnegative 63-bit integer")
    rng = random.Random(panel_seed)
    angles = sorted(x / 10000 for x in rng.sample(range(-4000, 4001), 17))
    contrasts = [-1.0, 0.0, 1.0]
    rng.shuffle(contrasts)
    wavelength = rng.choice([.5, .75, 1.0, 1.25, 1.5])
    return [normalize_spec({"angles_rad": deepcopy(angles), "wavelength_um": wavelength, "contrast_b": c}) for c in contrasts]

VERSION = "optical_diffraction-0.1.0-private-prototype"
validate_spec = normalize_spec


def integer(value, name="seed", low=0, high=2**63-1):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(name + " must be an integer in the stated range")
    return value


def describe():
    result = public_description()
    result["version"] = VERSION
    result["research_prompt"] = "Investigate this ideal coherent scattering instrument. Develop predictive accounts from observations and interventions, and describe remaining ambiguities. A unique geometry is not promised."
    result["axis"] = {"name": "angle", "unit": "rad", "rows": "requested angles"}
    result["limitations"] = "Fixed scalar single-scattering model only: no polarization, near field, multiple scattering, finite site extent, pixel averaging, dispersion, motion, partial coherence or photon-counting noise."
    return result
